"""One run's tests as a flat map, read from the Allure ``*-result.json`` files of an artifact tree.

This is the shape the analytics share (``flaky``, per-test history, failures,
Compare, the PR comment): ``{key: {name, full_name, group, status, duration_ms,
message, stage, framework, crash}}``. Since revision ``0003`` the same rows are also
stored in the ``test_result`` table when a run is recorded
(:mod:`testo_core.repository.test_results`); this module is the parser that
fills it, and the fallback for snapshots recorded before the table existed.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from testo_core.engine.crash_signatures import crash_in_text

# Bounds for the stored columns; the files keep the full text.
NAME_LIMIT = 120
GROUP_LIMIT = 100
MESSAGE_LIMIT = 300
KEY_LIMIT = 200


def case_key(data: dict[str, Any]) -> str:
    """The id a test keeps across runs: Allure's ``historyId``, else its full name."""
    for k in ("historyId", "fullName", "uuid"):
        v = data.get(k)
        if v is not None and str(v).strip():
            return str(v).strip()
    name = data.get("name")
    return str(name) if name is not None else json.dumps(data, sort_keys=True, default=str)[:200]


def case_duration_ms(data: dict[str, Any]) -> int | None:
    start, stop = data.get("start"), data.get("stop")
    if isinstance(start, int) and isinstance(stop, int) and stop >= start:
        return int(stop - start)
    return None


def label_value(labels: Any, name: str) -> str:
    if not isinstance(labels, list):
        return ""
    for lab in labels:
        if isinstance(lab, dict) and str(lab.get("name")) == name:
            v = lab.get("value")
            return str(v).strip() if v is not None else ""
    return ""


def case_message(data: dict[str, Any]) -> str:
    """First non-empty line of the failure message (or trace), for lists and grouping."""
    details = data.get("statusDetails")
    if not isinstance(details, dict):
        return ""
    text = str(details.get("message") or details.get("trace") or "")
    line = next((ln.strip() for ln in text.splitlines() if ln.strip()), "")
    return line[:MESSAGE_LIMIT]


def case_crash(data: dict[str, Any], status: str) -> str:
    """``"stack_overflow"`` / ``"crash"`` when a failed case's message or trace shows one, else ``""``."""
    if status not in ("failed", "broken"):
        return ""
    details = data.get("statusDetails")
    if not isinstance(details, dict):
        return ""
    text = f"{details.get('message') or ''}\n{details.get('trace') or ''}"
    found = crash_in_text(text)
    return found.kind if found else ""


def case_stage(path: Path, plan_root: Path) -> str:
    """The stage a result file belongs to: the folder just above ``allure-results``."""
    parts = path.relative_to(plan_root).parts
    if "allure-results" in parts:
        idx = parts.index("allure-results")
        if idx > 0:
            return parts[idx - 1]
    return ""


def case_group(data: dict[str, Any]) -> str:
    """Stable grouping key (module / suite) for dashboard tables."""
    labels = data.get("labels") or []
    pkg = label_value(labels, "package")
    if pkg:
        return pkg[:GROUP_LIMIT]
    ps, su = label_value(labels, "parentSuite"), label_value(labels, "suite")
    if ps and su:
        return f"{ps} › {su}"[:GROUP_LIMIT]
    if ps:
        return ps[:GROUP_LIMIT]
    fn = str(data.get("fullName") or data.get("name") or "")
    if "#" in fn:
        return fn.split("#", 1)[0][:GROUP_LIMIT]
    parts = fn.rsplit(".", 1)
    if len(parts) == 2 and parts[0] and "." in parts[0]:
        return parts[0][:GROUP_LIMIT]
    return "(ungrouped)"


def load_cases(plan_root: Path) -> dict[str, dict[str, Any]]:
    """Every ``*-result.json`` under ``plan_root`` as ``{key: case}``; ``{}`` when there is none."""
    out: dict[str, dict[str, Any]] = {}
    if not plan_root.is_dir():
        return out
    # Thousands of results share a folder; working out its stage once per folder
    # instead of once per file was most of the dashboard's load time.
    stages: dict[Path, str] = {}
    for path in plan_root.rglob("*-result.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, TypeError):
            continue
        if not isinstance(data, dict):
            continue
        key = case_key(data)
        st = str(data.get("status") or "unknown").lower()
        stage = stages.get(path.parent)
        if stage is None:
            stage = stages[path.parent] = case_stage(path, plan_root)
        out[key] = {
            "name": str(data.get("name") or data.get("fullName") or key)[:NAME_LIMIT],
            "full_name": str(data.get("fullName") or ""),
            "group": case_group(data),
            "status": st,
            "duration_ms": case_duration_ms(data),
            "message": case_message(data),
            "stage": stage,
            "framework": label_value(data.get("labels"), "framework"),
            "crash": case_crash(data, st),
        }
    return out
