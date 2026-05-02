from __future__ import annotations

import os

from fastapi import APIRouter, Depends, HTTPException

from uqo_api.dependencies import get_ai_settings_store, get_failure_analysis_service
from uqo_api.models import AiConfigStatusResponse, AiConfigUpdateRequest, AiSummaryResponse, GenerateAiSummaryRequest
from uqo_core.services.ai import AiProviderConfig, ProviderMisconfiguredError
from uqo_core.services.ai.integration_settings import InMemoryAiSettingsStore
from uqo_core.services.failure_analysis_service import FailureAnalysisService

router = APIRouter(prefix="/api/v1", tags=["ai"])


def _config_status_payload(store: InMemoryAiSettingsStore) -> dict[str, object]:
    settings = store.get()
    status = settings.to_public_status()
    if settings.api_key_source == "env":
        env_name = settings.to_provider_config().resolved_api_key_env_var()
        status["configured"] = bool(os.getenv(env_name, ""))
        status["key_present"] = status["configured"]
    return status


@router.get("/ai/config/status", response_model=AiConfigStatusResponse)
def get_ai_config_status(store: InMemoryAiSettingsStore = Depends(get_ai_settings_store)) -> AiConfigStatusResponse:
    return AiConfigStatusResponse(**_config_status_payload(store))


@router.put("/ai/config", response_model=AiConfigStatusResponse)
def update_ai_config(
    payload: AiConfigUpdateRequest,
    store: InMemoryAiSettingsStore = Depends(get_ai_settings_store),
) -> AiConfigStatusResponse:
    try:
        AiProviderConfig(
            enabled=payload.enabled,
            provider=payload.provider,
            model=payload.model,
            api_key_source=payload.api_key_source,
            api_key_env_var=payload.api_key_env_var,
            timeout_s=payload.timeout_s,
            retry_count=payload.retry_count,
            max_input_chars=payload.max_input_chars,
            max_output_tokens=payload.max_output_tokens,
        ).validate()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    settings = store.update(
        enabled=payload.enabled,
        provider=payload.provider,
        model=payload.model,
        api_key_source=payload.api_key_source,
        api_key_env_var=payload.api_key_env_var,
        timeout_s=payload.timeout_s,
        retry_count=payload.retry_count,
        max_input_chars=payload.max_input_chars,
        max_output_tokens=payload.max_output_tokens,
        runtime_api_key=payload.api_key_input or store.get().runtime_api_key,
    )
    status = settings.to_public_status()
    if payload.api_key_source == "env":
        try:
            env_name = settings.to_provider_config().resolved_api_key_env_var()
            status["configured"] = bool(os.getenv(env_name, ""))
            status["key_present"] = status["configured"]
        except ProviderMisconfiguredError:
            status["configured"] = False
            status["key_present"] = False
    else:
        status["configured"] = bool(settings.runtime_api_key)
        status["key_present"] = bool(settings.runtime_api_key)
    return AiConfigStatusResponse(**status)


@router.get("/runs/{run_id}/ai-summary", response_model=AiSummaryResponse)
def get_run_ai_summary(
    run_id: str,
    failure_service: FailureAnalysisService = Depends(get_failure_analysis_service),
) -> AiSummaryResponse:
    return AiSummaryResponse(**failure_service.get_summary(run_id=run_id).to_dict())


@router.post("/runs/{run_id}/ai-summary:generate", response_model=AiSummaryResponse)
def generate_run_ai_summary(
    run_id: str,
    payload: GenerateAiSummaryRequest,
    failure_service: FailureAnalysisService = Depends(get_failure_analysis_service),
) -> AiSummaryResponse:
    summary = failure_service.generate_summary(run_id=run_id, force_refresh=payload.force_refresh)
    return AiSummaryResponse(**summary.to_dict())
