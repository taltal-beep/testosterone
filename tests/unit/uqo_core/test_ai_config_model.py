from __future__ import annotations

import pytest

from uqo_core.services.ai import AiProviderConfig


def test_ai_config_validation_rejects_invalid_limits() -> None:
    with pytest.raises(ValueError):
        AiProviderConfig(timeout_s=0).validate()
    with pytest.raises(ValueError):
        AiProviderConfig(retry_count=-1).validate()
    with pytest.raises(ValueError):
        AiProviderConfig(max_input_chars=0).validate()
