from __future__ import annotations

from uqo_core.security.redaction import redact_text, redact_value


def test_redact_text_masks_token_patterns() -> None:
    payload = "Authorization: Bearer sk-test-abc123456789"
    assert "sk-test-abc123456789" not in redact_text(payload)


def test_redact_value_masks_nested_structures() -> None:
    payload = {
        "error": "api_key=SECRET12345678",
        "items": ["Bearer verysecret12345"],
        "metadata": {"token": "rawsecret123"},
    }
    redacted = redact_value(payload)
    assert redacted["error"] == "***REDACTED***"
    assert redacted["items"][0] == "***REDACTED***"
    assert redacted["metadata"]["token"] == "***REDACTED***"
