"""Typed views of a stored run, decoupled from the ``RunRecord.metadata_`` JSON shape.

Records are written by :class:`~testo_core.persistence.db_backend.DbBackend`
(``exit_code``, ``duration_s``, ``stages``, ...). :func:`view_from_record` maps that
JSON onto typed fields, so nothing above this module depends on the raw keys.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from testo_core.repository.models import RunRecord, RunStatus


@dataclass(frozen=True)
class CompletedRunView:
    """Flat view of one run for the API and services."""

    run_id: str
    status: RunStatus | None
    created_at: float
    started_at: float
    finished_at: float
    test_kind: str
    returncode: int
    wall_duration_ms: float
    metrics_duration_ms: int | None
    total_tests: int | None
    passed: int | None
    failed: int | None
    broken: int | None
    skipped: int | None
    avg_case_ms: float | None
    health_pct: float | None
    target_repo: str | None
    snapshot_dir: str | None
    audit_json: str | None
    cycle: str | None = None
    stage_health: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class RunSessionView:
    """A run plus the report links available for it (dashboard and run list)."""

    run_id: str
    created_at: float
    returncode: int
    health_pct: float | None
    total_tests: int | None
    passed: int | None
    failed: int | None
    skipped: int | None
    broken: int | None
    status: RunStatus | None
    links_under_static: dict[str, str]
    cycle: str | None = None


def wall_duration_ms_from_metadata(md: dict[str, Any]) -> float:
    """``duration_s`` in milliseconds, else ``finished_at - started_at``."""
    if md.get("duration_s") is not None:
        return max(0.0, float(md["duration_s"]) * 1000.0)
    started, finished = md.get("started_at"), md.get("finished_at")
    if started is not None and finished is not None:
        return max(0.0, (float(finished) - float(started)) * 1000.0)
    return 0.0


def health_pct_from_metadata(md: dict[str, Any]) -> float | None:
    """Stored health %, else the share of stages that exited ``0``."""
    if md.get("health_pct") is not None:
        return float(md["health_pct"])
    stages = md.get("stages")
    if isinstance(stages, list) and stages:
        passed_stages = sum(1 for s in stages if isinstance(s, dict) and s.get("returncode") == 0)
        return 100.0 * passed_stages / len(stages)
    return None


def _optional_int(md: dict[str, Any], key: str) -> int | None:
    return int(md[key]) if md.get(key) is not None else None


def _optional_float(md: dict[str, Any], key: str) -> float | None:
    return float(md[key]) if md.get(key) is not None else None


def _optional_str(md: dict[str, Any], key: str) -> str | None:
    return str(md[key]) if md.get(key) else None


def view_from_record(record: RunRecord) -> CompletedRunView | None:
    """Build a :class:`CompletedRunView`; ``None`` for records without a ``run_id``."""
    md = record.metadata_ or {}
    run_id = md.get("run_id")
    if not run_id:
        return None
    return CompletedRunView(
        run_id=str(run_id),
        status=record.status,
        created_at=float(md.get("created_at") or 0.0),
        started_at=float(md.get("started_at") or 0.0),
        finished_at=float(md.get("finished_at") or 0.0),
        test_kind=str(md.get("test_kind") or "unknown"),
        cycle=_optional_str(md, "plan"),
        returncode=int(md.get("exit_code") or 0),
        wall_duration_ms=wall_duration_ms_from_metadata(md),
        metrics_duration_ms=_optional_int(md, "metrics_duration_ms"),
        total_tests=_optional_int(md, "total_tests"),
        passed=_optional_int(md, "passed"),
        failed=_optional_int(md, "failed"),
        broken=_optional_int(md, "broken"),
        skipped=_optional_int(md, "skipped"),
        avg_case_ms=_optional_float(md, "avg_case_ms"),
        health_pct=health_pct_from_metadata(md),
        target_repo=_optional_str(md, "target_repo"),
        snapshot_dir=_optional_str(md, "snapshot_dir"),
        audit_json=_optional_str(md, "audit_json"),
        stage_health=[s for s in md.get("stages") or [] if isinstance(s, dict)],
    )
