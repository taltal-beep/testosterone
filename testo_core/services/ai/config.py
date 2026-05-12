from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal

from .provider_base import AiProviderName, ProviderMisconfiguredError

ApiKeySource = Literal["env", "runtime_input"]

_DEFAULT_KEY_ENV_VARS: dict[AiProviderName, str] = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
}


@dataclass(frozen=True)
class AiProviderConfig:
    enabled: bool = False
    provider: AiProviderName = "openai"
    model: str = "gpt-4o-mini"
    api_key_source: ApiKeySource = "env"
    api_key_env_var: str | None = None
    timeout_s: float = 8.0
    retry_count: int = 1
    max_input_chars: int = 16_000
    max_output_tokens: int = 300

    def resolved_api_key_env_var(self) -> str:
        return self.api_key_env_var or _DEFAULT_KEY_ENV_VARS[self.provider]

    def validate(self) -> None:
        if self.timeout_s <= 0:
            raise ValueError("timeout_s must be greater than zero.")
        if self.retry_count < 0:
            raise ValueError("retry_count cannot be negative.")
        if self.max_input_chars <= 0:
            raise ValueError("max_input_chars must be greater than zero.")
        if self.max_output_tokens <= 0:
            raise ValueError("max_output_tokens must be greater than zero.")
        if self.api_key_source == "env" and not self.resolved_api_key_env_var():
            raise ValueError("api_key_env_var must be provided when api_key_source=env.")

    def resolve_api_key(self, *, runtime_api_key: str | None = None) -> str:
        if self.api_key_source == "runtime_input":
            if runtime_api_key:
                return runtime_api_key
            raise ProviderMisconfiguredError("Runtime API key is required but missing.")
        key = os.getenv(self.resolved_api_key_env_var(), "")
        if key:
            return key
        raise ProviderMisconfiguredError(f"Environment API key is missing: {self.resolved_api_key_env_var()}")
