from __future__ import annotations

import pytest

from testo_core.security.redaction import redact_text, redact_value


def test_redact_text_masks_token_patterns() -> None:
    payload = "Authorization: Bearer sk-test-abc123456789"
    assert "sk-test-abc123456789" not in redact_text(payload)


def test_redact_value_masks_nested_structures() -> None:
    payload = {
        "error": "api_key=SECRET12345678",
        "items": ["Bearer verysecret12345"],
    }
    redacted = redact_value(payload)
    assert redacted["error"] == "***REDACTED***"
    assert redacted["items"][0] == "***REDACTED***"


def test_redact_value_masks_sensitive_mapping_keys() -> None:
    payload = {
        "api_key": "SECRET12345678",
        "nested": {
            "authorization": "Bearer runtime-token-123456",
            "safe": "diagnostic evidence",
        },
    }

    redacted = redact_value(payload)

    assert redacted["api_key"] == "***REDACTED***"
    assert redacted["nested"]["authorization"] == "***REDACTED***"
    assert redacted["nested"]["safe"] == "diagnostic evidence"


@pytest.mark.parametrize(
    "secret",
    [
        "github_pat_11ABCDEFG0123456789_abcdefghijklmnopqrstuvwxyz",
        "ghp_abcdefghijklmnopqrstuvwxyz0123456789",
        "glpat-abcdefghij1234567890",
        "npm_abcdefghijklmnopqrstuvwxyz0123456789",
        "xoxb-123456789012-abcdefghijkl",
        "AKIAIOSFODNN7EXAMPLE",
        "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
        "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.abcDEF123",
        "dXNlcjpwYXNzd29yZA==",
        "hunter22",
        "MIIEowIBAAKCAQEA",
        "AIzaSyA-abcdefghijklmnopqrstuvwxyz12345",
        "abcdefghijk123",
    ],
)
def test_common_secret_formats_are_masked(secret: str) -> None:
    text = "\n".join(
        [
            "AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
            "Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.abcDEF123",
            "Authorization: Basic dXNlcjpwYXNzd29yZA==",
            "GET https://ci:hunter22@git.example.com/repo.git",
            "-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA\n-----END RSA PRIVATE KEY-----",
            '{"access_token": "abcdefghijk123"}',
            "tokens: github_pat_11ABCDEFG0123456789_abcdefghijklmnopqrstuvwxyz "
            "ghp_abcdefghijklmnopqrstuvwxyz0123456789 glpat-abcdefghij1234567890 "
            "npm_abcdefghijklmnopqrstuvwxyz0123456789 xoxb-123456789012-abcdefghijkl "
            "AKIAIOSFODNN7EXAMPLE AIzaSyA-abcdefghijklmnopqrstuvwxyz12345",
        ]
    )
    assert secret not in redact_text(text)


def test_url_keeps_the_user_name_and_ordinary_text_survives() -> None:
    assert redact_text("postgresql://u:pw123456@db/t") == "postgresql://u:***REDACTED***@db/t"
    for text in ("assert 1 == 2", "https://example.com/pkg@v1", "http://localhost:8000/api"):
        assert redact_text(text) == text


def test_more_sensitive_mapping_keys() -> None:
    redacted = redact_value({"password": "p", "DATABASE_URL": "d", "privateKey": "k", "name": "n"})
    assert redacted == {
        "password": "***REDACTED***",
        "DATABASE_URL": "***REDACTED***",
        "privateKey": "***REDACTED***",
        "name": "n",
    }
