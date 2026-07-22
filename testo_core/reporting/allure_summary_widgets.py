"""Allure sidecar files for ``testo summary`` comparison dashboards (env, executor, categories)."""

from __future__ import annotations

import json
import uuid
from collections.abc import Sequence
from pathlib import Path

from testo_core.repository.models import ReportArchive

DEFAULT_OVERVIEW_TITLE = "Testosterone Comparison: Baseline vs Current"
EXECUTOR_BUILD_LABEL = "Quarterly Quality Comparison"


def pass_rate_delta_display(*, baseline: ReportArchive | None, current: ReportArchive) -> str:
    """Human-readable delta in pass-rate percentage points (e.g. ``-13.5%``)."""

    def _rate(row: ReportArchive) -> float | None:
        t, p = row.total_tests, row.passed
        if t is None or p is None or int(t) <= 0:
            return None
        return 100.0 * float(p) / float(t)

    if baseline is None:
        return "n/a"
    br, cr = _rate(baseline), _rate(current)
    if br is None or cr is None:
        return "n/a"
    return f"{cr - br:+.1f}%"


def comparison_delta_categories() -> list[dict[str, str | list[str]]]:
    """Categories aligned with ``[TESTO:…]`` markers in ``statusDetails.message`` (order matters)."""

    return [
        {
            "name": "Regressions (Critical)",
            "matchedStatuses": ["failed", "broken"],
            "messageRegex": ".*\\[TESTO:REGRESSION\\].*",
        },
        {
            "name": "Fixed Tests",
            "matchedStatuses": ["passed"],
            "messageRegex": ".*\\[TESTO:FIXED\\].*",
        },
        {
            "name": "New Failures",
            "matchedStatuses": ["failed", "broken"],
            "messageRegex": ".*\\[TESTO:NEW_FAILURE\\].*",
        },
        {
            "name": "Persistent Failures",
            "matchedStatuses": ["failed", "broken"],
            "messageRegex": ".*\\[TESTO:PERSISTENT\\].*",
        },
        {
            "name": "Other Status Changes",
            "matchedStatuses": ["failed", "broken", "skipped"],
            "messageRegex": ".*\\[TESTO:STATUS_CHANGE\\].*",
        },
        {
            "name": "Product Defects",
            "matchedStatuses": ["failed"],
            "messageRegex": "^((?!\\[TESTO:]).)*$",
        },
        {
            "name": "Test Defects",
            "matchedStatuses": ["broken"],
            "messageRegex": "^((?!\\[TESTO:]).)*$",
        },
    ]


def default_product_categories() -> list[dict[str, str | list[str]]]:
    return [
        {"name": "Product Defects", "matchedStatuses": ["failed"]},
        {"name": "Test Defects", "matchedStatuses": ["broken"]},
    ]


def write_summary_comparison_sidecars(
    *,
    result_dirs: Sequence[Path],
    baseline: ReportArchive | None,
    current: ReportArchive,
    regressions_found: int,
    fixes_verified: int,
    performance_summary_md: str | None = None,
) -> None:
    """Write ``environment.properties``, ``executor.json``, and ``categories.json`` into result dirs.

    When ``baseline`` is set, uses delta comparison categories and writes ``executor.json`` only
    to the first result directory to avoid duplicate Executors rows in Allure.
    """
    baseline_id = str(baseline.id) if baseline is not None else "n/a"
    current_id = str(current.id)
    quality = pass_rate_delta_display(baseline=baseline, current=current)

    env_lines = [
        "Report_Type=Delta Comparison",
        f"Baseline_Run_ID={baseline_id}",
        f"Current_Run_ID={current_id}",
        f"Quality_Change={quality}",
        f"Regressions_Found={regressions_found}",
        f"Fixes_Verified={fixes_verified}",
    ]
    if performance_summary_md and performance_summary_md.strip():
        escaped = (
            performance_summary_md.strip()
            .replace("\\", "\\\\")
            .replace("\n", "\\n")
            .replace("\r", "")
        )
        env_lines.append(f"Performance_Regressions_MD={escaped}")
    env_body = "\n".join(env_lines) + "\n"

    if baseline is not None:
        build_name = f"Diff: {baseline_id[:8]} -> {current_id[:8]}"
        categories = comparison_delta_categories()
    else:
        build_name = EXECUTOR_BUILD_LABEL
        categories = default_product_categories()

    executor: dict[str, str | int] = {
        "name": "Testosterone CLI",
        "type": "cli",
        "reportName": DEFAULT_OVERVIEW_TITLE,
        "buildName": build_name,
        "reportUrl": f"testo://report-archive/{current_id}",
    }
    uid = uuid.UUID(current_id)
    executor["buildOrder"] = int(uid.int % (10**9)) or 1
    executor_json = json.dumps(executor, indent=2, ensure_ascii=False) + "\n"
    categories_json = json.dumps(categories, indent=2, ensure_ascii=False) + "\n"

    resolved = [rd.expanduser().resolve() for rd in result_dirs if rd.is_dir()]
    for i, root in enumerate(resolved):
        (root / "environment.properties").write_text(env_body, encoding="utf-8")
        (root / "categories.json").write_text(categories_json, encoding="utf-8")
        if baseline is not None:
            ex = root / "executor.json"
            if i == 0:
                ex.write_text(executor_json, encoding="utf-8")
            elif ex.is_file():
                ex.unlink()
        else:
            (root / "executor.json").write_text(executor_json, encoding="utf-8")
