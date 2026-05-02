from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Literal

from uqo_core.run_history import CompletedRunView, get_run
from uqo_core.services.delta_models import (
    DeltaClassification,
    DeltaComparisonResult,
    DeltaDirection,
    DeltaStatusSummary,
    MetricDelta,
)


class DeltaComparisonError(ValueError):
    """Base domain exception for delta comparison failures."""


class InvalidRunIdError(DeltaComparisonError):
    """Raised when one of the run ids is invalid."""


class RunNotFoundComparisonError(DeltaComparisonError):
    """Raised when a requested run id does not exist."""

    def __init__(self, run_id: str) -> None:
        super().__init__(f"Run not found: {run_id}")
        self.run_id = run_id


class IncompatibleRunDataError(DeltaComparisonError):
    """Raised when a pair of runs cannot be compared safely."""


@dataclass(frozen=True)
class _MetricPolicy:
    key: str
    label: str
    group: Literal["reliability", "performance"]
    direction: DeltaDirection
    unit: Literal["ms", "pct", "tests"]


class DeltaComparisonService:
    _METRIC_POLICY: tuple[_MetricPolicy, ...] = (
        _MetricPolicy("total_tests", "Total tests", "reliability", "higher_is_better", "tests"),
        _MetricPolicy("passed", "Passed tests", "reliability", "higher_is_better", "tests"),
        _MetricPolicy("failed", "Failed tests", "reliability", "lower_is_better", "tests"),
        _MetricPolicy("broken", "Broken tests", "reliability", "lower_is_better", "tests"),
        _MetricPolicy("skipped", "Skipped tests", "reliability", "lower_is_better", "tests"),
        _MetricPolicy("health_pct", "Health percentage", "reliability", "higher_is_better", "pct"),
        _MetricPolicy("wall_duration_ms", "Wall duration", "performance", "lower_is_better", "ms"),
        _MetricPolicy("metrics_duration_ms", "Metrics duration", "performance", "lower_is_better", "ms"),
        _MetricPolicy("avg_case_ms", "Average case duration", "performance", "lower_is_better", "ms"),
    )

    def __init__(
        self,
        *,
        run_lookup: Callable[[str], CompletedRunView | None] | None = None,
    ) -> None:
        self._run_lookup = run_lookup or (lambda run_id: get_run(run_id=run_id))

    def compare_runs(self, *, current_run_id: str, baseline_run_id: str) -> DeltaComparisonResult:
        cur_id = self._validate_run_id(current_run_id, label="current_run_id")
        base_id = self._validate_run_id(baseline_run_id, label="baseline_run_id")

        current = self._run_lookup(cur_id)
        if current is None:
            raise RunNotFoundComparisonError(cur_id)
        baseline = self._run_lookup(base_id)
        if baseline is None:
            raise RunNotFoundComparisonError(base_id)

        if current.test_kind != baseline.test_kind:
            raise IncompatibleRunDataError(
                "Cannot compare runs with different test kinds: "
                f"{current.test_kind!r} vs {baseline.test_kind!r}."
            )

        deltas = tuple(self._build_metric_delta(policy=policy, current=current, baseline=baseline) for policy in self._METRIC_POLICY)
        summary = self._build_status_summary(deltas)
        highlights = self._build_highlights(deltas)
        return DeltaComparisonResult(
            current_run_id=cur_id,
            baseline_run_id=base_id,
            current_test_kind=current.test_kind,
            baseline_test_kind=baseline.test_kind,
            metrics=deltas,
            status_summary=summary,
            highlights=highlights,
        )

    def _validate_run_id(self, run_id: str, *, label: str) -> str:
        cleaned = str(run_id).strip()
        if not cleaned:
            raise InvalidRunIdError(f"{label} must be a non-empty string.")
        return cleaned

    def _build_metric_delta(
        self,
        *,
        policy: _MetricPolicy,
        current: CompletedRunView,
        baseline: CompletedRunView,
    ) -> MetricDelta:
        current_value = self._to_float(getattr(current, policy.key, None))
        baseline_value = self._to_float(getattr(baseline, policy.key, None))

        if current_value is None:
            return self._unknown_delta(policy=policy, current=current_value, baseline=baseline_value, reason="missing_current_metric")
        if baseline_value is None:
            return self._unknown_delta(policy=policy, current=current_value, baseline=baseline_value, reason="missing_baseline_metric")

        absolute_delta = current_value - baseline_value
        relative_delta_pct: float | None = None
        reason: str | None = None
        if baseline_value == 0:
            reason = "zero_baseline_for_relative"
        else:
            relative_delta_pct = (absolute_delta / baseline_value) * 100.0

        classification = self._classify(absolute_delta=absolute_delta, direction=policy.direction)
        return MetricDelta(
            metric_key=policy.key,
            label=policy.label,
            group=policy.group,
            current_value=current_value,
            baseline_value=baseline_value,
            absolute_delta=absolute_delta,
            relative_delta_pct=relative_delta_pct,
            classification=classification,
            reason=reason,
            direction=policy.direction,
            unit=policy.unit,
        )

    def _unknown_delta(
        self,
        *,
        policy: _MetricPolicy,
        current: float | None,
        baseline: float | None,
        reason: str,
    ) -> MetricDelta:
        return MetricDelta(
            metric_key=policy.key,
            label=policy.label,
            group=policy.group,
            current_value=current,
            baseline_value=baseline,
            absolute_delta=None,
            relative_delta_pct=None,
            classification="unknown",
            reason=reason,
            direction=policy.direction,
            unit=policy.unit,
        )

    def _build_status_summary(self, deltas: tuple[MetricDelta, ...]) -> DeltaStatusSummary:
        regressions: list[str] = []
        improvements: list[str] = []
        unchanged: list[str] = []
        unknown: list[str] = []
        for delta in deltas:
            if delta.classification == "regression":
                regressions.append(delta.metric_key)
            elif delta.classification == "improvement":
                improvements.append(delta.metric_key)
            elif delta.classification == "neutral":
                unchanged.append(delta.metric_key)
            else:
                unknown.append(delta.metric_key)
        return DeltaStatusSummary(
            regressions=tuple(regressions),
            improvements=tuple(improvements),
            unchanged=tuple(unchanged),
            unknown=tuple(unknown),
        )

    def _build_highlights(self, deltas: tuple[MetricDelta, ...]) -> tuple[str, ...]:
        ranked = sorted(
            [d for d in deltas if d.classification in {"regression", "improvement"} and d.absolute_delta is not None],
            key=lambda d: abs(d.absolute_delta or 0.0),
            reverse=True,
        )
        highlights: list[str] = []
        for delta in ranked[:5]:
            change = delta.absolute_delta or 0.0
            magnitude = abs(change)
            verb = "worsened" if delta.classification == "regression" else "improved"
            if delta.unit == "ms":
                highlights.append(f"{delta.label} {verb} by {magnitude:.2f} ms.")
            elif delta.unit == "pct":
                highlights.append(f"{delta.label} {verb} by {magnitude:.2f} percentage points.")
            else:
                highlights.append(f"{delta.label} {verb} by {magnitude:.0f} tests.")
        return tuple(highlights)

    @staticmethod
    def _to_float(value: float | int | None) -> float | None:
        if value is None:
            return None
        return float(value)

    @staticmethod
    def _classify(*, absolute_delta: float, direction: DeltaDirection) -> DeltaClassification:
        if absolute_delta == 0:
            return "neutral"
        if direction == "higher_is_better":
            return "improvement" if absolute_delta > 0 else "regression"
        return "improvement" if absolute_delta < 0 else "regression"

