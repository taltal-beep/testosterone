from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

_TOKEN_PATTERNS: tuple[re.Pattern[str], ...] = (
    # Private key blocks first, before anything inside them matches on its own.
    re.compile(
        r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----.*?(?:-----END [A-Z0-9 ]*PRIVATE KEY-----|$)",
        re.DOTALL,
    ),
    # Well-known token formats: OpenAI/Anthropic, GitHub, GitLab, npm, Slack, AWS, Google.
    re.compile(r"sk-[A-Za-z0-9_\-]{8,}"),
    re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})"),
    re.compile(r"\bglpat-[A-Za-z0-9_\-]{16,}"),
    re.compile(r"\bnpm_[A-Za-z0-9]{30,}"),
    re.compile(r"\bxox[abposr]-[A-Za-z0-9\-]{10,}"),
    re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    re.compile(r"\bAIza[A-Za-z0-9_\-]{30,}"),
    # JSON Web Tokens (three base64url parts).
    re.compile(r"\beyJ[A-Za-z0-9_\-]{5,}\.[A-Za-z0-9_\-]{5,}\.[A-Za-z0-9_\-]*"),
    # key=value / key: value / "key": "value" for secret-sounding keys.
    re.compile(
        r"(?:api[_-]?key|access[_-]?key|token|secret|passw(?:or)?d|passwd|credentials?)"
        r"[\"']?\s*[:=]\s*([\"'])?([^\s\"',;]{6,})(\1)?",
        re.IGNORECASE,
    ),
    re.compile(r"(?:Bearer|Basic)\s+[A-Za-z0-9_\-.~+/=]{8,}", re.IGNORECASE),
)
_SENSITIVE_KEY_PATTERN = re.compile(
    r"(^|[_\-\s])(api[_\-\s]?key|token|secret|authorization|passw(or)?d|passwd|"
    r"credentials?|private[_\-\s]?key|privatekey|cookie|database[_\-\s]?url|dsn)([_\-\s]|$)",
    re.IGNORECASE,
)
_REDACTED = "***REDACTED***"


# Passwords in URLs: scheme://user:password@host keeps the user name.
_URL_PASSWORD = re.compile(r"(?<=://)([^/\s:@]+):[^/\s@]+(?=@)")


def redact_text(text: str) -> str:
    redacted = _URL_PASSWORD.sub(lambda m: f"{m.group(1)}:{_REDACTED}", text)
    for pattern in _TOKEN_PATTERNS:
        redacted = pattern.sub(_REDACTED, redacted)
    return redacted


def redact_mapping(payload: Mapping[str, Any]) -> dict[str, Any]:
    redacted: dict[str, Any] = {}
    for key, value in payload.items():
        key_text = str(key)
        redacted[key_text] = (
            _REDACTED if _SENSITIVE_KEY_PATTERN.search(key_text) else redact_value(value)
        )
    return redacted


def redact_sequence(payload: Sequence[Any]) -> list[Any]:
    return [redact_value(item) for item in payload]


def redact_value(value: Any) -> Any:
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, Mapping):
        return redact_mapping(value)
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray, str)):
        return redact_sequence(value)
    return value


def redact_error_message(exc: Exception) -> str:
    return redact_text(str(exc))
