"""Queries over stored runs, used by the API routes and the analytics services.

Every read goes through :func:`testo_core.db.get_repository`, so the read side
works the same on SQLite, Postgres and MySQL and never touches SQL directly.
"""

from __future__ import annotations

from typing import Any

from testo_core.db import get_repository
from testo_core.history.report_links import report_links
from testo_core.history.views import CompletedRunView, RunSessionView, view_from_record


def list_recent_runs(*, limit: int = 30) -> list[CompletedRunView]:
    """Up to ``limit`` runs, newest first."""
    views = (view_from_record(r) for r in get_repository().list_recent_runs(limit=limit))
    return [v for v in views if v is not None]


def get_run(*, run_id: str) -> CompletedRunView | None:
    """One run by its id, or ``None``."""
    record = get_repository().get_run(run_id)
    return view_from_record(record) if record is not None else None


def get_run_metadata(*, run_id: str) -> dict[str, Any] | None:
    """A copy of the run's raw metadata (failure context, stored AI summary, …), or ``None``."""
    record = get_repository().get_run(run_id)
    return dict(record.metadata_ or {}) if record is not None else None


def list_run_sessions(*, limit: int = 30) -> list[RunSessionView]:
    """Recent runs with the report links available for each."""
    return [
        RunSessionView(
            run_id=r.run_id,
            created_at=r.created_at,
            returncode=r.returncode,
            cycle=r.cycle,
            health_pct=r.health_pct,
            total_tests=r.total_tests,
            passed=r.passed,
            failed=r.failed,
            skipped=r.skipped,
            broken=r.broken,
            status=r.status,
            links_under_static=report_links(r),
        )
        for r in list_recent_runs(limit=limit)
    ]
