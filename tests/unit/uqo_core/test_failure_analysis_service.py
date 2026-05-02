from __future__ import annotations

from uqo_core.repository.models import RunStatus
from uqo_core.run_history import CompletedRunView
from uqo_core.services.ai.integration_settings import InMemoryAiSettingsStore
from uqo_core.services.failure_analysis_service import FailureAnalysisService


def _failed_run() -> CompletedRunView:
    return CompletedRunView(
        run_id="run-1",
        status=RunStatus.FAILED,
        created_at=1.0,
        started_at=1.0,
        finished_at=2.0,
        test_kind="pytest",
        returncode=1,
        wall_duration_ms=100.0,
        metrics_duration_ms=90,
        total_tests=10,
        passed=8,
        failed=2,
        broken=0,
        skipped=0,
        avg_case_ms=10.0,
        health_pct=80.0,
        target_repo=".",
        snapshot_dir=None,
        audit_json=None,
    )


def test_generate_summary_returns_disabled_fallback() -> None:
    store = InMemoryAiSettingsStore()
    state: dict[str, dict] = {"md": {}}
    service = FailureAnalysisService(
        settings_store=store,
        run_lookup=lambda _: _failed_run(),
        metadata_lookup=lambda _: state["md"],
        metadata_upsert=lambda _, patch: state["md"].update(patch) or True,
    )
    summary = service.generate_summary(run_id="run-1")
    assert summary.status == "no_summary_generated"
    assert summary.error_code == "ai_feature_disabled"
