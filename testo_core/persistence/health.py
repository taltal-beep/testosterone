"""Real per-stage + overall health % for a completed :class:`PlanResult`.

Reuses the Allure-parsing machinery the reporting pipeline already has
(:func:`testo_core.reporting.allure_results.parse_collected_results`) instead
of approximating health from stage subprocess return codes.
"""

from __future__ import annotations

from pathlib import Path

from testo_core.engine.result import PlanResult
from testo_core.reporting.allure_results import parse_collected_results
from testo_core.reporting.collector import CollectedResults, StageCollection


def _pct(passed: int, total: int) -> float | None:
    return 100.0 * passed / total if total else None


def compute_stage_health(result: PlanResult, artifacts_root: Path) -> tuple[list[dict], float | None]:
    """Return (per-stage health dicts, overall weighted health_pct).

    Each stage dict has ``total_tests``/``passed``/``failed``/``broken``/
    ``skipped``/``health_pct`` keyed by ``name`` so callers can merge it into
    their existing per-stage metadata. The overall figure is a single
    weighted pass rate (sum of passed / sum of total across every stage),
    not an average of per-stage percentages. Returns ``(per_stage, None)``
    when no stage produced any parseable Allure results, so callers can fall
    back to a returncode-based estimate instead of reporting a misleading 0%.
    """
    collected = CollectedResults(
        artifacts_root=artifacts_root,
        stages=[
            StageCollection(
                plan=result.plan_name,
                stage=s.stage_name,
                framework=s.framework,
                # Layout written by executor.run_stage(): <stage_dir>/allure-results/<framework>/*-result.json
                results_dir=s.artifacts_dir / "allure-results" / s.framework,
                log_path=s.log_path,
            )
            for s in result.stages
        ],
    )
    aggregate = parse_collected_results(collected)

    per_stage: list[dict] = [
        {
            "name": s.stage,
            "total_tests": s.total,
            "passed": s.passed,
            "failed": s.failed,
            "broken": s.broken,
            "skipped": s.skipped,
            "health_pct": _pct(s.passed, s.total),
        }
        for s in aggregate.stages
    ]
    overall_health_pct = _pct(aggregate.passed, aggregate.total)
    return per_stage, overall_health_pct
