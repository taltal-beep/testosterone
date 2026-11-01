"""Compare two archived Allure cycles (per-test and aggregate metrics)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from testo_core.reporting.allure_cases import case_key, case_stage, label_value, load_cases
from testo_core.reporting.paths import plan_artifacts_dir
from testo_core.repository.models import ReportArchive

# The parser lives in reporting.allure_cases; these names stay for the modules that import them.
_case_key = case_key
_case_stage = case_stage
_label_value = label_value
_load_cases = load_cases


CaseChangeKind = Literal["added", "removed", "regression", "fix", "status_change"]


@dataclass(frozen=True)
class CaseChange:
    key: str
    name: str
    group: str
    baseline_status: str | None
    current_status: str | None
    kind: CaseChangeKind
    duration_delta_ms: int | None


def diff_case_maps(
    base_cases: dict[str, dict[str, Any]], cur_cases: dict[str, dict[str, Any]]
) -> list[CaseChange]:
    """Match two ``_load_cases()`` maps by key and classify each case's change.

    Shared by both ``diff_archives`` (ReportArchive zips, ``testo diff``) and
    ``run_snapshot_diff.diff_run_snapshots`` (live run snapshot dirs, the API).
    """
    changes: list[CaseChange] = []
    all_keys = sorted(set(base_cases) | set(cur_cases))
    for key in all_keys:
        b = base_cases.get(key)
        c = cur_cases.get(key)
        bs = b["status"] if b else None
        cs = c["status"] if c else None
        name = (c or b or {}).get("name", key) if (c or b) else key
        group = str((c or b or {}).get("group") or "(ungrouped)")
        bd = (b or {}).get("duration_ms") if b else None
        cd = (c or {}).get("duration_ms") if c else None
        delta = None
        if isinstance(bd, int) and isinstance(cd, int):
            delta = cd - bd

        kind: CaseChangeKind | None
        if b is None and c is not None:
            kind = "added"
        elif b is not None and c is None:
            kind = "removed"
        else:
            assert b is not None and c is not None
            if bs == cs:
                kind = None
            elif bs in {"passed"} and cs in {"failed", "broken"}:
                kind = "regression"
            elif bs in {"failed", "broken"} and cs in {"passed"}:
                kind = "fix"
            else:
                kind = "status_change"

        if kind is not None:
            changes.append(
                CaseChange(
                    key=key[:80],
                    name=str(name)[:120],
                    group=group[:100],
                    baseline_status=bs,
                    current_status=cs,
                    kind=kind,
                    duration_delta_ms=delta,
                )
            )
    return changes


def diff_archives(
    *, baseline: ReportArchive, current: ReportArchive, tmp: Path
) -> tuple[list[CaseChange], dict[str, Any]]:
    """Extract both zips under ``tmp`` and return case-level changes plus metrics row dict."""
    from testo_core.services.report_archive import extract_archive_to_plan_dir

    extract_archive_to_plan_dir(
        zip_bytes=baseline.artifact_bytes,
        dest_artifacts_root=tmp / "a",
        plan_name=baseline.cycle_name,
    )
    extract_archive_to_plan_dir(
        zip_bytes=current.artifact_bytes,
        dest_artifacts_root=tmp / "b",
        plan_name=current.cycle_name,
    )
    base_root = plan_artifacts_dir(tmp / "a", baseline.cycle_name)
    cur_root = plan_artifacts_dir(tmp / "b", current.cycle_name)
    base_cases = _load_cases(base_root)
    cur_cases = _load_cases(cur_root)
    changes = diff_case_maps(base_cases, cur_cases)

    metrics = {
        "baseline_id": str(baseline.id),
        "current_id": str(current.id),
        "baseline_total_tests": baseline.total_tests,
        "current_total_tests": current.total_tests,
        "baseline_passed": baseline.passed,
        "current_passed": current.passed,
        "baseline_failed": baseline.failed,
        "current_failed": current.failed,
        "baseline_plan_duration_ms": baseline.plan_duration_ms,
        "current_plan_duration_ms": current.plan_duration_ms,
    }
    return changes, metrics


def parse_archive_uuid(value: str) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(value).strip())
    except (ValueError, TypeError):
        return None
