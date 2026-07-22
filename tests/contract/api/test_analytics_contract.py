from __future__ import annotations

from fastapi.testclient import TestClient

from testo_api.main import create_app
from testo_core.services.delta_models import DeltaComparisonResult, DeltaStatusSummary, MetricDelta
from testo_core.services.delta_service import (
    IncompatibleRunDataError,
    InvalidRunIdError,
    RunNotFoundComparisonError,
)


def _fake_result() -> DeltaComparisonResult:
    metrics = (
        MetricDelta(
            metric_key="total_tests",
            label="Total tests",
            group="reliability",
            current_value=120.0,
            baseline_value=100.0,
            absolute_delta=20.0,
            relative_delta_pct=20.0,
            classification="improvement",
            reason=None,
            direction="higher_is_better",
            unit="tests",
        ),
        MetricDelta(
            metric_key="passed",
            label="Passed tests",
            group="reliability",
            current_value=110.0,
            baseline_value=98.0,
            absolute_delta=12.0,
            relative_delta_pct=12.2449,
            classification="improvement",
            reason=None,
            direction="higher_is_better",
            unit="tests",
        ),
        MetricDelta(
            metric_key="failed",
            label="Failed tests",
            group="reliability",
            current_value=6.0,
            baseline_value=1.0,
            absolute_delta=5.0,
            relative_delta_pct=500.0,
            classification="regression",
            reason=None,
            direction="lower_is_better",
            unit="tests",
        ),
        MetricDelta(
            metric_key="broken",
            label="Broken tests",
            group="reliability",
            current_value=2.0,
            baseline_value=1.0,
            absolute_delta=1.0,
            relative_delta_pct=100.0,
            classification="regression",
            reason=None,
            direction="lower_is_better",
            unit="tests",
        ),
        MetricDelta(
            metric_key="skipped",
            label="Skipped tests",
            group="reliability",
            current_value=2.0,
            baseline_value=0.0,
            absolute_delta=2.0,
            relative_delta_pct=None,
            classification="regression",
            reason="zero_baseline_for_relative",
            direction="lower_is_better",
            unit="tests",
        ),
        MetricDelta(
            metric_key="health_pct",
            label="Health percentage",
            group="reliability",
            current_value=91.5,
            baseline_value=99.0,
            absolute_delta=-7.5,
            relative_delta_pct=-7.5757,
            classification="regression",
            reason=None,
            direction="higher_is_better",
            unit="pct",
        ),
        MetricDelta(
            metric_key="wall_duration_ms",
            label="Wall duration",
            group="performance",
            current_value=1260.0,
            baseline_value=1300.0,
            absolute_delta=-40.0,
            relative_delta_pct=-3.0769,
            classification="improvement",
            reason=None,
            direction="lower_is_better",
            unit="ms",
        ),
        MetricDelta(
            metric_key="metrics_duration_ms",
            label="Metrics duration",
            group="performance",
            current_value=1000.0,
            baseline_value=900.0,
            absolute_delta=100.0,
            relative_delta_pct=11.1111,
            classification="regression",
            reason=None,
            direction="lower_is_better",
            unit="ms",
        ),
        MetricDelta(
            metric_key="avg_case_ms",
            label="Average case duration",
            group="performance",
            current_value=10.2,
            baseline_value=11.5,
            absolute_delta=-1.3,
            relative_delta_pct=-11.3043,
            classification="improvement",
            reason=None,
            direction="lower_is_better",
            unit="ms",
        ),
    )
    return DeltaComparisonResult(
        current_run_id="run-2",
        baseline_run_id="run-1",
        current_test_kind="pytest",
        baseline_test_kind="pytest",
        metrics=metrics,
        status_summary=DeltaStatusSummary(
            regressions=("failed", "broken", "skipped", "health_pct", "metrics_duration_ms"),
            improvements=("total_tests", "passed", "wall_duration_ms", "avg_case_ms"),
            unchanged=(),
            unknown=(),
        ),
        highlights=(
            "Failed tests worsened by 5 tests.",
            "Wall duration improved by 40.00 ms.",
        ),
    )


def test_analytics_delta_contract_success(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setattr(
        "testo_api.routes.analytics.DeltaComparisonService.compare_runs",
        lambda self, **_: _fake_result(),
    )
    client = TestClient(create_app())
    resp = client.get("/api/v1/analytics/delta?current_run_id=run-2&baseline_run_id=run-1")
    assert resp.status_code == 200
    payload = resp.json()
    assert set(payload.keys()) == {"comparison", "metrics", "status_summary", "highlights"}
    assert payload["comparison"]["current_run_id"] == "run-2"
    assert set(payload["metrics"].keys()) == {"reliability", "performance"}
    assert payload["metrics"]["reliability"]["failed"]["classification"] == "regression"
    assert payload["metrics"]["performance"]["wall_duration_ms"]["classification"] == "improvement"


def test_analytics_delta_invalid_id(monkeypatch) -> None:  # noqa: ANN001
    def _raise_invalid(self, **kwargs):  # noqa: ANN001, ARG001
        raise InvalidRunIdError("current_run_id must be a non-empty string.")

    monkeypatch.setattr("testo_api.routes.analytics.DeltaComparisonService.compare_runs", _raise_invalid)
    client = TestClient(create_app())
    resp = client.get("/api/v1/analytics/delta?current_run_id=&baseline_run_id=run-1")
    assert resp.status_code == 400
    payload = resp.json()
    assert payload["error"]["code"] == "invalid_input"


def test_analytics_delta_run_not_found(monkeypatch) -> None:  # noqa: ANN001
    def _raise_not_found(self, **kwargs):  # noqa: ANN001, ARG001
        raise RunNotFoundComparisonError("missing")

    monkeypatch.setattr("testo_api.routes.analytics.DeltaComparisonService.compare_runs", _raise_not_found)
    client = TestClient(create_app())
    resp = client.get("/api/v1/analytics/delta?current_run_id=run-2&baseline_run_id=missing")
    assert resp.status_code == 404
    payload = resp.json()
    assert payload["error"]["code"] == "not_found"


def test_analytics_delta_incompatible_data(monkeypatch) -> None:  # noqa: ANN001
    def _raise_incompatible(self, **kwargs):  # noqa: ANN001, ARG001
        raise IncompatibleRunDataError("Cannot compare runs with different test kinds.")

    monkeypatch.setattr("testo_api.routes.analytics.DeltaComparisonService.compare_runs", _raise_incompatible)
    client = TestClient(create_app())
    resp = client.get("/api/v1/analytics/delta?current_run_id=run-2&baseline_run_id=run-1")
    assert resp.status_code == 422
    payload = resp.json()
    assert payload["error"]["code"] == "invalid_input"

