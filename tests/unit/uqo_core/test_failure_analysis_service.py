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


def test_generate_summary_returns_cached_summary_without_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    state: dict[str, dict] = {
        "md": {
            "ai_summary_v1": {
                "schema_version": "v1",
                "run_id": "run-1",
                "status": "available",
                "summary_text": "Cached root cause",
                "confidence": "high",
                "limitations": ["cached"],
                "provider": "openai",
                "model": "gpt-4o-mini",
                "generated_at": 10.0,
                "context_stats": {"prompt_chars": 12},
                "error_code": None,
            }
        }
    }
    monkeypatch.setattr(
        "uqo_core.services.failure_analysis_service.build_ai_provider",
        lambda **_: (_ for _ in ()).throw(AssertionError("provider should not be built")),
    )
    service = FailureAnalysisService(
        settings_store=InMemoryAiSettingsStore(),
        run_lookup=lambda _: _failed_run(),
        metadata_lookup=lambda _: state["md"],
        metadata_upsert=lambda _, patch: state["md"].update(patch) or True,
    )

    summary = service.generate_summary(run_id="run-1")

    assert summary.status == "available"
    assert summary.summary_text == "Cached root cause"
    assert summary.limitations == ("cached",)
    assert state["md"]["ai_summary_v1"]["summary_text"] == "Cached root cause"


def test_generate_summary_force_refresh_bypasses_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    store = InMemoryAiSettingsStore()
    store.update(enabled=True, api_key_source="runtime_input", runtime_api_key="sk-test-runtime-token")
    state: dict[str, dict] = {
        "md": {
            "ai_summary_v1": {
                "schema_version": "v1",
                "run_id": "run-1",
                "status": "available",
                "summary_text": "Cached root cause",
                "confidence": "high",
                "limitations": [],
                "provider": "openai",
                "model": "gpt-4o-mini",
                "generated_at": 10.0,
                "context_stats": {},
                "error_code": None,
            }
        }
    }
    calls: list[str] = []

    class _Provider:
        def generate(self, request):  # noqa: ANN001, ANN202
            calls.append(request.prompt)
            return AiGenerationResult(text="Fresh root cause", provider="openai", model="gpt-4o-mini")

    monkeypatch.setattr("uqo_core.services.failure_analysis_service.build_ai_provider", lambda **_: _Provider())
    service = FailureAnalysisService(
        settings_store=store,
        run_lookup=lambda _: _failed_run(),
        metadata_lookup=lambda _: state["md"],
        metadata_upsert=lambda _, patch: state["md"].update(patch) or True,
    )

    summary = service.generate_summary(run_id="run-1", force_refresh=True)

    assert summary.status == "available"
    assert summary.summary_text == "Fresh root cause"
    assert len(calls) == 1
    assert state["md"]["ai_summary_v1"]["summary_text"] == "Fresh root cause"


def test_generate_summary_provider_error_redacts_exception_before_persisting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = InMemoryAiSettingsStore()
    store.update(enabled=True, api_key_source="runtime_input", runtime_api_key="sk-test-runtime-token")
    state: dict[str, dict] = {"md": {"error_message": "failed assertion"}}

    class _Provider:
        def generate(self, request):  # noqa: ANN001, ANN202
            raise ProviderUnavailableError("upstream failed with Bearer sk-test-secret-token")

    monkeypatch.setattr("uqo_core.services.failure_analysis_service.build_ai_provider", lambda **_: _Provider())
    service = FailureAnalysisService(
        settings_store=store,
        run_lookup=lambda _: _failed_run(),
        metadata_lookup=lambda _: state["md"],
        metadata_upsert=lambda _, patch: state["md"].update(patch) or True,
    )

    summary = service.generate_summary(run_id="run-1")

    persisted = state["md"]["ai_summary_v1"]
    assert summary.status == "no_summary_generated"
    assert summary.error_code == "summary_not_available"
    assert "***REDACTED***" in " ".join(summary.limitations)
    assert "sk-test-secret-token" not in " ".join(summary.limitations)
    assert "***REDACTED***" in " ".join(persisted["limitations"])
    assert "sk-test-secret-token" not in " ".join(persisted["limitations"])


def test_get_summary_loads_stored_payload() -> None:
    service = FailureAnalysisService(
        settings_store=InMemoryAiSettingsStore(),
        metadata_lookup=lambda _: {
            "ai_summary_v1": {
                "schema_version": "v1",
                "run_id": "stored-run",
                "status": "available",
                "summary_text": "Stored root cause",
                "confidence": "medium",
                "limitations": ["log_truncated"],
                "provider": "anthropic",
                "model": "claude-3-5-sonnet",
                "generated_at": 42.0,
                "context_stats": {"prompt_chars": 99},
                "error_code": None,
            }
        },
    )

    summary = service.get_summary(run_id="run-1")

    assert summary.run_id == "run-1"
    assert summary.status == "available"
    assert summary.summary_text == "Stored root cause"
    assert summary.limitations == ("log_truncated",)
    assert summary.context_stats == {"prompt_chars": 99}
