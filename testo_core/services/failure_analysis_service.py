from __future__ import annotations

import time
from dataclasses import asdict, dataclass
from typing import Any, Callable, Literal

from testo_core.run_history import CompletedRunView, get_run, get_run_metadata, upsert_run_metadata
from testo_core.security.redaction import redact_error_message
from testo_core.services.ai import (
    AiGenerationRequest,
    AiProviderError,
    AiProviderConfig,
    ProviderMisconfiguredError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    ProviderUnavailableError,
    UnsupportedProviderModelError,
    build_ai_provider,
)
from testo_core.services.ai.integration_settings import InMemoryAiSettingsStore

from .failure_context_builder import FailureContextBudget, build_failure_context

SummaryStatus = Literal["available", "no_summary_generated"]


@dataclass(frozen=True)
class FailureAnalysisSummary:
    schema_version: Literal["v1"]
    run_id: str
    status: SummaryStatus
    summary_text: str | None
    confidence: Literal["low", "medium", "high"] | None
    limitations: tuple[str, ...]
    provider: str | None
    model: str | None
    generated_at: float
    context_stats: dict[str, int]
    error_code: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["limitations"] = list(self.limitations)
        return payload


class FailureAnalysisService:
    def __init__(
        self,
        *,
        settings_store: InMemoryAiSettingsStore,
        run_lookup: Callable[[str], CompletedRunView | None] = lambda run_id: get_run(run_id=run_id),
        metadata_lookup: Callable[[str], dict[str, Any] | None] = lambda run_id: get_run_metadata(run_id=run_id),
        metadata_upsert: Callable[[str, dict[str, Any]], bool] = lambda run_id, patch: upsert_run_metadata(
            run_id=run_id, metadata_patch=patch
        ),
    ) -> None:
        self._settings_store = settings_store
        self._run_lookup = run_lookup
        self._metadata_lookup = metadata_lookup
        self._metadata_upsert = metadata_upsert

    def get_summary(self, *, run_id: str) -> FailureAnalysisSummary:
        metadata = self._metadata_lookup(run_id) or {}
        stored = metadata.get("ai_summary_v1")
        if isinstance(stored, dict):
            return _summary_from_stored(stored, run_id=run_id)
        return self._fallback(run_id=run_id, error_code="summary_not_available", limitations=("summary_not_generated",))

    def generate_summary(self, *, run_id: str, force_refresh: bool = False) -> FailureAnalysisSummary:
        run = self._run_lookup(run_id)
        if run is None:
            return self._fallback(run_id=run_id, error_code="summary_not_available", limitations=("run_not_found",))
        if run.returncode == 0:
            return self._fallback(run_id=run_id, error_code="summary_not_available", limitations=("run_not_failed",))

        existing = self.get_summary(run_id=run_id)
        if existing.status == "available" and not force_refresh:
            return existing

        settings = self._settings_store.get()
        if not settings.enabled:
            return self._fallback(run_id=run_id, error_code="ai_feature_disabled", limitations=("feature_disabled",))
        cfg: AiProviderConfig = settings.to_provider_config()
        metadata = self._metadata_lookup(run_id) or {}
        context = build_failure_context(run=run, metadata=metadata, budget=FailureContextBudget(max_total_chars=cfg.max_input_chars))
        try:
            provider = build_ai_provider(config=cfg, runtime_api_key=settings.runtime_api_key)
            result = provider.generate(
                AiGenerationRequest(
                    prompt=context.prompt,
                    max_output_tokens=cfg.max_output_tokens,
                    temperature=0.1,
                )
            )
            summary = FailureAnalysisSummary(
                schema_version="v1",
                run_id=run_id,
                status="available",
                summary_text=result.text,
                confidence="medium",
                limitations=context.limitations,
                provider=result.provider,
                model=result.model,
                generated_at=time.time(),
                context_stats=context.context_stats,
                error_code=None,
            )
        except ProviderMisconfiguredError:
            summary = self._fallback(run_id=run_id, error_code="provider_misconfigured", limitations=context.limitations)
        except ProviderTimeoutError:
            summary = self._fallback(run_id=run_id, error_code="provider_timeout", limitations=context.limitations)
        except ProviderRateLimitError:
            summary = self._fallback(run_id=run_id, error_code="provider_rate_limited", limitations=context.limitations)
        except UnsupportedProviderModelError:
            summary = self._fallback(run_id=run_id, error_code="unsupported_provider_model", limitations=context.limitations)
        except (ProviderUnavailableError, AiProviderError) as exc:
            summary = self._fallback(
                run_id=run_id,
                error_code="summary_not_available",
                limitations=(*context.limitations, redact_error_message(exc)),
            )
        if summary.status == "available" or existing.status != "available":
            self._metadata_upsert(run_id, {"ai_summary_v1": summary.to_dict()})
        return summary

    @staticmethod
    def _fallback(*, run_id: str, error_code: str, limitations: tuple[str, ...]) -> FailureAnalysisSummary:
        return FailureAnalysisSummary(
            schema_version="v1",
            run_id=run_id,
            status="no_summary_generated",
            summary_text=None,
            confidence=None,
            limitations=limitations,
            provider=None,
            model=None,
            generated_at=time.time(),
            context_stats={},
            error_code=error_code,
        )


def _summary_from_stored(payload: dict[str, Any], *, run_id: str) -> FailureAnalysisSummary:
    return FailureAnalysisSummary(
        schema_version="v1",
        run_id=run_id,
        status="available" if payload.get("status") == "available" else "no_summary_generated",
        summary_text=payload.get("summary_text"),
        confidence=payload.get("confidence"),
        limitations=tuple(payload.get("limitations") or ()),
        provider=payload.get("provider"),
        model=payload.get("model"),
        generated_at=float(payload.get("generated_at") or time.time()),
        context_stats=dict(payload.get("context_stats") or {}),
        error_code=payload.get("error_code"),
    )
