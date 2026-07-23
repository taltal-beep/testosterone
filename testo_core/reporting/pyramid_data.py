"""Aggregate a completed run's per-stage test counts into a `PyramidModel`."""

from __future__ import annotations

from testo_core.config.schema import Stage
from testo_core.reporting.pyramid_viz import PyramidModel
from testo_core.run_history import CompletedRunView


def build_pyramid_model(run: CompletedRunView, stages: tuple[Stage, ...]) -> PyramidModel:
    """Sum each stage's ``total_tests`` into its configured tier bucket.

    Stages not found in ``stages`` (e.g. a renamed/removed stage since the run
    executed) default to the "unit" tier rather than being dropped, matching
    `Stage.tier`'s own default.
    """

    tier_by_stage_name = {stage.name: stage.tier for stage in stages}
    counts = {"unit": 0, "integration": 0, "e2e": 0}
    for stage_row in run.stage_health:
        name = stage_row.get("name")
        total = stage_row.get("total_tests")
        if name is None or not isinstance(total, int):
            continue
        tier = tier_by_stage_name.get(str(name), "unit")
        counts[tier] = counts.get(tier, 0) + total
    return PyramidModel(unit=counts["unit"], integration=counts["integration"], e2e=counts["e2e"])
