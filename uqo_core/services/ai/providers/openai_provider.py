from __future__ import annotations

import json
import urllib.error
import urllib.request

from uqo_core.security.redaction import redact_error_message

from ..provider_base import (
    AiGenerationRequest,
    AiGenerationResult,
    AiProvider,
    ProviderRateLimitError,
    ProviderTimeoutError,
    ProviderUnavailableError,
    UnsupportedProviderModelError,
)


class OpenAiProvider(AiProvider):
    provider_name = "openai"

    def __init__(self, *, model: str, api_key: str, timeout_s: float) -> None:
        self.model = model
        self._api_key = api_key
        self._timeout_s = timeout_s

    def generate(self, request: AiGenerationRequest) -> AiGenerationResult:
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": request.prompt}],
            "max_tokens": request.max_output_tokens,
            "temperature": request.temperature,
        }
        req = urllib.request.Request(
            url="https://api.openai.com/v1/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self._timeout_s) as response:  # nosec: B310
                body = json.loads(response.read().decode("utf-8"))
        except TimeoutError as exc:
            raise ProviderTimeoutError("OpenAI request timed out.") from exc
        except urllib.error.HTTPError as exc:
            if exc.code == 429:
                raise ProviderRateLimitError("OpenAI rate limit exceeded.") from exc
            if exc.code == 400:
                raise UnsupportedProviderModelError("OpenAI model is unsupported for this key.") from exc
            raise ProviderUnavailableError(f"OpenAI HTTP error {exc.code}.") from exc
        except urllib.error.URLError as exc:
            raise ProviderUnavailableError(f"OpenAI request failed: {redact_error_message(exc)}") from exc
        text = (
            body.get("choices", [{}])[0].get("message", {}).get("content")
            if isinstance(body.get("choices"), list)
            else None
        )
        if not text:
            raise ProviderUnavailableError("OpenAI response did not include summary content.")
        usage = body.get("usage", {}) if isinstance(body.get("usage"), dict) else {}
        return AiGenerationResult(
            text=str(text).strip(),
            provider="openai",
            model=self.model,
            finish_reason=body.get("choices", [{}])[0].get("finish_reason") if isinstance(body.get("choices"), list) else None,
            usage_input_tokens=usage.get("prompt_tokens"),
            usage_output_tokens=usage.get("completion_tokens"),
        )
