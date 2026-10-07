from __future__ import annotations

import pytest

from testo_core.history.views import CompletedRunView, RunSessionView
from testo_core.repository.models import RunStatus
from testo_core.services.dashboard_service import DashboardService
from testo_core.services.delta_service import DeltaComparisonService


def _completed(
    *,
    run_id: str,
    health_pct: float,
    failed: int,
    wall_duration_ms: float,
    passed: int = 10,
) -> CompletedRunView:
    return CompletedRunView(
        run_id=run_id,
        status=RunStatus.COMPLETED,
        created_at=1.0,
        started_at=1.0,
        finished_at=2.0,
        test_kind="pytest",
        returncode=0,
        wall_duration_ms=wall_duration_ms,
        metrics_duration_ms=900,
        total_tests=10,
        passed=passed,
        failed=failed,
        broken=0,
        skipped=0,
        avg_case_ms=90.0,
        health_pct=health_pct,
        target_repo="/tmp/repo",
        snapshot_dir=None,
        audit_json=None,
    )


def _session(
    *, run_id: str, created_at: float, returncode: int, status: RunStatus, cycle: str | None = None
) -> RunSessionView:
    return RunSessionView(
        run_id=run_id,
        created_at=created_at,
        returncode=returncode,
        health_pct=99.0,
        total_tests=10,
        passed=10,
        failed=0,
        skipped=0,
        broken=0,
        status=status,
        links_under_static={
            "behavex": "/history/run-x/allure_reports/behavex/index.html",
        },
        cycle=cycle,
    )


def test_dashboard_overview_uses_existing_run_and_delta_services(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALLURE_SERVER_URL", "http://allure.local")
    sessions = [
        _session(run_id="run-current", created_at=2.0, returncode=0, status=RunStatus.COMPLETED),
        _session(run_id="run-baseline", created_at=1.0, returncode=1, status=RunStatus.FAILED),
    ]
    runs = {
        "run-current": _completed(
            run_id="run-current", health_pct=98.0, failed=1, wall_duration_ms=900.0, passed=9
        ),
        "run-baseline": _completed(
            run_id="run-baseline", health_pct=93.0, failed=3, wall_duration_ms=1200.0, passed=7
        ),
    }
    service = DashboardService(
        run_sessions_loader=lambda limit: sessions[:limit],
        run_lookup=lambda run_id: runs.get(run_id),
        delta_service_factory=lambda: DeltaComparisonService(
            run_lookup=lambda run_id: runs.get(run_id)
        ),
    )

    overview = service.get_overview(recent_limit=2)

    assert overview.headline_kpis.latest_run_id == "run-current"
    assert overview.headline_kpis.health_pct == 98.0
    assert overview.trend_health.direction == "up"
    assert overview.trend_failed_count.direction == "down"
    assert overview.trend_duration.direction == "down"
    assert overview.reliability_rollup.status_summary.improvements >= 1
    assert overview.performance_rollup.status_summary.improvements >= 1
    assert overview.report_links.allure.state == "available"
    assert overview.report_links.allure.url is not None
    assert overview.report_links.behave.state == "available"
    assert len(overview.recent_runs) == 2
    assert (
        overview.recent_runs[0].compare_url
        == "/compare?current_run_id=run-current&baseline_run_id=run-baseline"
    )
    assert overview.data_freshness.degraded is False


def test_dashboard_overview_degrades_when_runs_missing() -> None:
    service = DashboardService(run_sessions_loader=lambda limit: [], run_lookup=lambda _: None)
    overview = service.get_overview()
    assert overview.headline_kpis.latest_run_id is None
    assert overview.trend_health.direction == "unknown"
    assert overview.reliability_rollup.status_summary.unknown == 0
    assert overview.report_links.allure.state in {"missing", "unknown"}
    assert overview.data_freshness.degraded is True
    assert "no_runs_available" in overview.data_freshness.notes


def test_dashboard_recent_runs_validates_limit() -> None:
    service = DashboardService(run_sessions_loader=lambda limit: [], run_lookup=lambda _: None)
    with pytest.raises(ValueError):
        service.get_recent_runs(limit=0)


def test_dashboard_baseline_and_compare_links_stay_within_the_same_cycle() -> None:
    sessions = [
        _session(run_id="a-2", created_at=3.0, returncode=0, status=RunStatus.COMPLETED, cycle="a"),
        _session(run_id="b-1", created_at=2.0, returncode=0, status=RunStatus.COMPLETED, cycle="b"),
        _session(run_id="a-1", created_at=1.0, returncode=0, status=RunStatus.COMPLETED, cycle="a"),
    ]
    completed = {
        s.run_id: _completed(run_id=s.run_id, health_pct=100.0, failed=0, wall_duration_ms=1000.0)
        for s in sessions
    }
    looked_up: list[str] = []

    def _lookup(run_id: str) -> CompletedRunView:
        looked_up.append(run_id)
        return completed[run_id]

    service = DashboardService(
        run_sessions_loader=lambda limit: sessions[:limit],
        run_lookup=_lookup,
        delta_service_factory=lambda: DeltaComparisonService(run_lookup=_lookup),
    )
    overview = service.get_overview()

    assert looked_up[:2] == ["a-2", "a-1"]
    assert [r.compare_url for r in overview.recent_runs] == [
        "/compare?current_run_id=a-2&baseline_run_id=a-1",
        None,
        None,
    ]
