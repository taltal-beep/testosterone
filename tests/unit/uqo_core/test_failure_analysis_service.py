from __future__ import annotations

import pytest

from uqo_core.repository.models import RunStatus
from uqo_core.run_history import CompletedRunView
from uqo_core.services.ai import AiGenerationResult, ProviderUnavailableError
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


def test_generate_summary_redacts_provider_errors_and_persists_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    store = InMemoryAiSettingsStore()
    store.update(enabled=True, api_key_source="runtime_input", runtime_api_key="runtime-key")
    state: dict[str, dict] = {
        "md": {
            "error_message": "request failed with api_key=supersecret123",
            "traceback": "Bearer traceToken123456",
        }
    }

    class FailingProvider:
        def generate(self, _request):
            raise ProviderUnavailableError("upstream rejected sk-providersecret123")

    monkeypatch.setattr("uqo_core.services.failure_analysis_service.build_ai_provider", lambda **_: FailingProvider())
    monkeypatch.setattr("uqo_core.services.failure_analysis_service.time.time", lambda: 123.0)

    service = FailureAnalysisService(
        settings_store=store,
        run_lookup=lambda _: _failed_run(),
        metadata_lookup=lambda _: state["md"],
        metadata_upsert=lambda _, patch: state["md"].update(patch) or True,
    )

    summary = service.generate_summary(run_id="run-1")

    assert summary.status == "no_summary_generated"
    assert summary.error_code == "summary_not_available"
    assert summary.generated_at == 123.0
    assert "upstream rejected ***REDACTED***" in summary.limitations
    assert "sk-providersecret123" not in str(summary.to_dict())
    assert state["md"]["ai_summary_v1"] == summary.to_dict()


def test_generate_summary_returns_cached_available_summary_without_provider_call(monkeypatch: pytest.MonkeyPatch) -> None:
    store = InMemoryAiSettingsStore()
    store.update(enabled=True, api_key_source="runtime_input", runtime_api_key="runtime-key")
    cached = {
        "schema_version": "v1",
        "status": "available",
        "summary_text": "Known failure cause",
        "confidence": "high",
        "limitations": ["cached_context"],
        "provider": "openai",
        "model": "gpt-4o-mini",
        "generated_at": 55.0,
        "context_stats": {"prompt_chars": 42},
        "error_code": None,
    }
    state: dict[str, dict] = {"md": {"ai_summary_v1": cached}}

    def fail_provider_call(**_kwargs):
        raise AssertionError("cached summary should avoid provider creation")

    monkeypatch.setattr("uqo_core.services.failure_analysis_service.build_ai_provider", fail_provider_call)
    service = FailureAnalysisService(
        settings_store=store,
        run_lookup=lambda _: _failed_run(),
        metadata_lookup=lambda _: state["md"],
        metadata_upsert=lambda _, patch: state["md"].update(patch) or True,
    )

    summary = service.generate_summary(run_id="run-1")

    assert summary.status == "available"
    assert summary.summary_text == "Known failure cause"
    assert summary.context_stats == {"prompt_chars": 42}
    assert summary.limitations == ("cached_context",)


def test_generate_summary_force_refresh_replaces_cached_available_summary(monkeypatch: pytest.MonkeyPatch) -> None:
    store = InMemoryAiSettingsStore()
    store.update(enabled=True, api_key_source="runtime_input", runtime_api_key="runtime-key")
    state: dict[str, dict] = {
        "md": {
            "ai_summary_v1": {
                "status": "available",
                "summary_text": "stale summary",
                "confidence": "low",
                "limitations": [],
                "provider": "openai",
                "model": "old-model",
                "generated_at": 1.0,
                "context_stats": {},
                "error_code": None,
            },
            "error_message": "new failure evidence",
        }
    }

    class FreshProvider:
        def generate(self, request):
            assert "new failure evidence" in request.prompt
            return AiGenerationResult(text="fresh summary", provider="openai", model="gpt-4o-mini")

    monkeypatch.setattr("uqo_core.services.failure_analysis_service.build_ai_provider", lambda **_: FreshProvider())
    monkeypatch.setattr("uqo_core.services.failure_analysis_service.time.time", lambda: 77.0)
    service = FailureAnalysisService(
        settings_store=store,
        run_lookup=lambda _: _failed_run(),
        metadata_lookup=lambda _: state["md"],
        metadata_upsert=lambda _, patch: state["md"].update(patch) or True,
    )

    summary = service.generate_summary(run_id="run-1", force_refresh=True)

    assert summary.status == "available"
    assert summary.summary_text == "fresh summary"
    assert summary.generated_at == 77.0
    assert state["md"]["ai_summary_v1"]["summary_text"] == "fresh summary"
