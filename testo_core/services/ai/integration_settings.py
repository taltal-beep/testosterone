from __future__ import annotations

from dataclasses import dataclass, replace
from threading import Lock

from .config import AiProviderConfig, ApiKeySource
from .provider_base import AiProviderName


@dataclass(frozen=True)
class AiIntegrationSettings:
    enabled: bool = False
    provider: AiProviderName = "openai"
    model: str = "gpt-4o-mini"
    api_key_source: ApiKeySource = "env"
    api_key_env_var: str | None = None
    timeout_s: float = 8.0
    retry_count: int = 1
    max_input_chars: int = 16_000
    max_output_tokens: int = 300
    runtime_api_key: str | None = None

    def to_provider_config(self) -> AiProviderConfig:
        return AiProviderConfig(
            enabled=self.enabled,
            provider=self.provider,
            model=self.model,
            api_key_source=self.api_key_source,
            api_key_env_var=self.api_key_env_var,
            timeout_s=self.timeout_s,
            retry_count=self.retry_count,
            max_input_chars=self.max_input_chars,
            max_output_tokens=self.max_output_tokens,
        )

    def to_public_status(self) -> dict[str, object]:
        key_present = bool(self.runtime_api_key) if self.api_key_source == "runtime_input" else None
        return {
            "enabled": self.enabled,
            "configured": key_present if key_present is not None else False,
            "provider": self.provider,
            "model": self.model,
            "api_key_source": self.api_key_source,
            "api_key_env_var": self.api_key_env_var,
            "key_present": key_present,
            "timeout_s": self.timeout_s,
            "retry_count": self.retry_count,
            "max_input_chars": self.max_input_chars,
            "max_output_tokens": self.max_output_tokens,
        }


class InMemoryAiSettingsStore:
    def __init__(self) -> None:
        self._settings = AiIntegrationSettings()
        self._lock = Lock()

    def get(self) -> AiIntegrationSettings:
        with self._lock:
            return self._settings

    def update(self, **kwargs: object) -> AiIntegrationSettings:
        with self._lock:
            self._settings = replace(self._settings, **kwargs)
            return self._settings
