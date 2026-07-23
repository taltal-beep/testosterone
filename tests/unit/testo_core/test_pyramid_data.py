from __future__ import annotations

from pathlib import Path

from testo_core.config.schema import Stage
from testo_core.reporting.pyramid_data import build_pyramid_model
from testo_core.run_history import CompletedRunView


def _run(stage_health: list[dict]) -> CompletedRunView:
    return CompletedRunView(
        run_id="run-1",
        status=None,
        created_at=0.0,
        started_at=0.0,
        finished_at=0.0,
        test_kind="pytest",
        returncode=0,
        wall_duration_ms=0.0,
        metrics_duration_ms=None,
        total_tests=None,
        passed=None,
        failed=None,
        broken=None,
        skipped=None,
        avg_case_ms=None,
        health_pct=None,
        target_repo=None,
        snapshot_dir=None,
        audit_json=None,
        cycle="sample-all-frameworks",
        stage_health=stage_health,
    )


def _stage(name: str, tier: str) -> Stage:
    return Stage(name=name, framework="pytest", target_repo=Path("."), tier=tier)


def test_build_pyramid_model_buckets_by_configured_tier() -> None:
    run = _run(
        [
            {"name": "pytest-sample", "total_tests": 100},
            {"name": "behave-features", "total_tests": 20},
            {"name": "flow-tests", "total_tests": 5},
        ]
    )
    stages = (
        _stage("pytest-sample", "unit"),
        _stage("behave-features", "integration"),
        _stage("flow-tests", "e2e"),
    )
    model = build_pyramid_model(run, stages)
    assert model.unit == 100
    assert model.integration == 20
    assert model.e2e == 5


def test_build_pyramid_model_defaults_unknown_stage_to_unit() -> None:
    run = _run([{"name": "renamed-stage", "total_tests": 7}])
    model = build_pyramid_model(run, stages=())
    assert model.unit == 7
    assert model.integration == 0
    assert model.e2e == 0


def test_build_pyramid_model_ignores_stages_without_total_tests() -> None:
    run = _run([{"name": "pytest-sample"}, {"name": "no-total", "total_tests": None}])
    model = build_pyramid_model(run, stages=(_stage("pytest-sample", "unit"),))
    assert model.unit == 0
    assert model.integration == 0
    assert model.e2e == 0
