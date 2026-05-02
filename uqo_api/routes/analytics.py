from __future__ import annotations

from fastapi import APIRouter, HTTPException

from uqo_api.models import (
    DeltaComparisonMeta,
    DeltaComparisonResponse,
    DeltaMetricsResponse,
    DeltaMetricNode,
    DeltaPerformanceMetrics,
    DeltaReliabilityMetrics,
    DeltaStatusSummaryResponse,
)
from uqo_core.services.delta_models import MetricDelta
from uqo_core.services.delta_service import (
    DeltaComparisonService,
    IncompatibleRunDataError,
    InvalidRunIdError,
    RunNotFoundComparisonError,
)

router = APIRouter(prefix="/api/v1", tags=["analytics"])


@router.get("/analytics/delta", response_model=DeltaComparisonResponse)
def get_delta_comparison(current_run_id: str, baseline_run_id: str) -> DeltaComparisonResponse:
    service = DeltaComparisonService()
    try:
        result = service.compare_runs(current_run_id=current_run_id, baseline_run_id=baseline_run_id)
    except InvalidRunIdError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RunNotFoundComparisonError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except IncompatibleRunDataError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    metric_map = {metric.metric_key: metric for metric in result.metrics}
    return DeltaComparisonResponse(
        comparison=DeltaComparisonMeta(
            current_run_id=result.current_run_id,
            baseline_run_id=result.baseline_run_id,
            current_test_kind=result.current_test_kind,
            baseline_test_kind=result.baseline_test_kind,
        ),
        metrics=DeltaMetricsResponse(
            reliability=DeltaReliabilityMetrics(
                total_tests=_to_metric_node(metric_map["total_tests"]),
                passed=_to_metric_node(metric_map["passed"]),
                failed=_to_metric_node(metric_map["failed"]),
                broken=_to_metric_node(metric_map["broken"]),
                skipped=_to_metric_node(metric_map["skipped"]),
                health_pct=_to_metric_node(metric_map["health_pct"]),
            ),
            performance=DeltaPerformanceMetrics(
                wall_duration_ms=_to_metric_node(metric_map["wall_duration_ms"]),
                metrics_duration_ms=_to_metric_node(metric_map["metrics_duration_ms"]),
                avg_case_ms=_to_metric_node(metric_map["avg_case_ms"]),
            ),
        ),
        status_summary=DeltaStatusSummaryResponse(
            regressions=list(result.status_summary.regressions),
            improvements=list(result.status_summary.improvements),
            unchanged=list(result.status_summary.unchanged),
            unknown=list(result.status_summary.unknown),
        ),
        highlights=list(result.highlights),
    )


def _to_metric_node(metric: MetricDelta) -> DeltaMetricNode:
    return DeltaMetricNode(
        current_value=metric.current_value,
        baseline_value=metric.baseline_value,
        absolute_delta=metric.absolute_delta,
        relative_delta_pct=metric.relative_delta_pct,
        classification=metric.classification,
        reason=metric.reason,
        direction=metric.direction,
        unit=metric.unit,
    )

