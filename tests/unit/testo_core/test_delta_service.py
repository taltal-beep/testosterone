from __future__ import annotations

import pytest

from testo_core.repository.models import RunStatus
from testo_core.run_history import CompletedRunView
from testo_core.services.delta_service import (
    DeltaComparisonService,
    IncompatibleRunDataError,
    InvalidRunIdError,
    RunNotFoundComparisonError,
)


def _view(
    *,
    run_id: str,
    test_kind: str = "pytest",
    total_tests: int | None = 10,
    passed: int | None = 10,
    failed: int | None = 0,
    broken: int | None = 0,
    skipped: int | None = 0,
    health_pct: float | None = 100.0,
    wall_duration_ms: float = 1000.0,
    metrics_duration_ms: int | None = 900,
    avg_case_ms: float | None = 100.0,
    stage_health: list[dict] | None = None,
) -> CompletedRunView:
    return CompletedRunView(
        run_id=run_id,
        status=RunStatus.COMPLETED,
        created_at=1.0,
        started_at=1.0,
        finished_at=2.0,
        test_kind=test_kind,
        returncode=0,
        wall_duration_ms=wall_duration_ms,
        metrics_duration_ms=metrics_duration_ms,
        total_tests=total_tests,
        passed=passed,
        failed=failed,
        broken=broken,
        skipped=skipped,
        avg_case_ms=avg_case_ms,
        health_pct=health_pct,
        target_repo="/tmp/repo",
        snapshot_dir=None,
        audit_json=None,
        stage_health=stage_health or [],
    )


def _service(rows: dict[str, CompletedRunView | None]) -> DeltaComparisonService:
    return DeltaComparisonService(run_lookup=lambda run_id: rows.get(run_id))


def test_compare_runs_classifies_regressions_and_improvements() -> None:
    service = _service(
        {
            "current": _view(run_id="current", failed=3, broken=1, wall_duration_ms=1300.0, health_pct=90.0),
            "baseline": _view(run_id="baseline", failed=1, broken=0, wall_duration_ms=1000.0, health_pct=96.0),
        }
    )
    result = service.compare_runs(current_run_id="current", baseline_run_id="baseline")

    metrics = {metric.metric_key: metric for metric in result.metrics}
    assert metrics["failed"].classification == "regression"
    assert metrics["failed"].absolute_delta == 2.0
    assert metrics["wall_duration_ms"].classification == "regression"
    assert metrics["health_pct"].classification == "regression"
    assert "failed" in result.status_summary.regressions
    assert result.highlights


def test_compare_runs_supports_improvement_and_neutral() -> None:
    service = _service(
        {
            "current": _view(run_id="current", failed=0, wall_duration_ms=900.0, passed=9),
            "baseline": _view(run_id="baseline", failed=2, wall_duration_ms=1200.0, passed=9),
        }
    )
    result = service.compare_runs(current_run_id="current", baseline_run_id="baseline")
    metrics = {metric.metric_key: metric for metric in result.metrics}

    assert metrics["failed"].classification == "improvement"
    assert metrics["passed"].classification == "neutral"
    assert metrics["wall_duration_ms"].classification == "improvement"
    assert "passed" in result.status_summary.unchanged


def test_compare_runs_marks_unknown_for_missing_metrics() -> None:
    service = _service(
        {
            "current": _view(run_id="current", metrics_duration_ms=None),
            "baseline": _view(run_id="baseline", metrics_duration_ms=1000),
        }
    )
    result = service.compare_runs(current_run_id="current", baseline_run_id="baseline")
    metrics = {metric.metric_key: metric for metric in result.metrics}

    assert metrics["metrics_duration_ms"].classification == "unknown"
    assert metrics["metrics_duration_ms"].reason == "missing_current_metric"
    assert "metrics_duration_ms" in result.status_summary.unknown


def test_compare_runs_sets_relative_reason_when_baseline_zero() -> None:
    service = _service(
        {
            "current": _view(run_id="current", failed=1),
            "baseline": _view(run_id="baseline", failed=0),
        }
    )
    result = service.compare_runs(current_run_id="current", baseline_run_id="baseline")
    metrics = {metric.metric_key: metric for metric in result.metrics}

    assert metrics["failed"].absolute_delta == 1.0
    assert metrics["failed"].relative_delta_pct is None
    assert metrics["failed"].reason == "zero_baseline_for_relative"


def test_compare_runs_rejects_incompatible_test_kinds() -> None:
    service = _service(
        {
            "current": _view(run_id="current", test_kind="pytest"),
            "baseline": _view(run_id="baseline", test_kind="behavex"),
        }
    )
    with pytest.raises(IncompatibleRunDataError):
        service.compare_runs(current_run_id="current", baseline_run_id="baseline")


def test_compare_runs_rejects_invalid_run_id() -> None:
    service = _service({})
    with pytest.raises(InvalidRunIdError):
        service.compare_runs(current_run_id=" ", baseline_run_id="baseline")


def test_compare_runs_raises_when_run_missing() -> None:
    service = _service({"baseline": _view(run_id="baseline")})
    with pytest.raises(RunNotFoundComparisonError):
        service.compare_runs(current_run_id="current", baseline_run_id="baseline")


def test_compare_runs_matches_stage_deltas_by_name() -> None:
    service = _service(
        {
            "current": _view(
                run_id="current",
                stage_health=[
                    {"name": "pytest-sample", "framework": "pytest", "total_tests": 10, "passed": 8, "health_pct": 80.0}
                ],
            ),
            "baseline": _view(
                run_id="baseline",
                stage_health=[
                    {"name": "pytest-sample", "framework": "pytest", "total_tests": 10, "passed": 10, "health_pct": 100.0}
                ],
            ),
        }
    )
    result = service.compare_runs(current_run_id="current", baseline_run_id="baseline")

    assert len(result.stage_deltas) == 1
    stage = result.stage_deltas[0]
    assert stage.stage_name == "pytest-sample"
    assert stage.health_pct_delta == -20.0
    assert stage.classification == "regression"


def test_compare_runs_stage_delta_unknown_when_stage_missing_on_one_side() -> None:
    service = _service(
        {
            "current": _view(
                run_id="current",
                stage_health=[{"name": "new-stage", "total_tests": 5, "passed": 5, "health_pct": 100.0}],
            ),
            "baseline": _view(run_id="baseline", stage_health=[]),
        }
    )
    result = service.compare_runs(current_run_id="current", baseline_run_id="baseline")

    assert len(result.stage_deltas) == 1
    stage = result.stage_deltas[0]
    assert stage.stage_name == "new-stage"
    assert stage.baseline_health_pct is None
    assert stage.current_health_pct == 100.0
    assert stage.classification == "unknown"


def test_compare_runs_no_stage_deltas_when_no_stage_health() -> None:
    service = _service(
        {
            "current": _view(run_id="current"),
            "baseline": _view(run_id="baseline"),
        }
    )
    result = service.compare_runs(current_run_id="current", baseline_run_id="baseline")
    assert result.stage_deltas == ()

