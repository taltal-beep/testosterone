from __future__ import annotations

import pytest

from testo_core.services.ai import AiProviderConfig, build_ai_provider
from testo_core.services.ai.provider_base import ProviderMisconfiguredError


def test_build_openai_provider_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-openai-token")
    config = AiProviderConfig(provider="openai", model="gpt-4o-mini", api_key_source="env")
    provider = build_ai_provider(config=config)
    assert provider.provider_name == "openai"


def test_build_anthropic_provider_from_runtime_key() -> None:
    config = AiProviderConfig(
        provider="anthropic",
        model="claude-3-5-haiku-latest",
        api_key_source="runtime_input",
    )
    provider = build_ai_provider(config=config, runtime_api_key="runtime-token")
    assert provider.provider_name == "anthropic"


def test_missing_env_key_raises_misconfigured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    config = AiProviderConfig(provider="openai", model="gpt-4o-mini", api_key_source="env")
    with pytest.raises(ProviderMisconfiguredError):
        build_ai_provider(config=config)
