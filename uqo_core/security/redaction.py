from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

_TOKEN_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"sk-[A-Za-z0-9_\-]{8,}"),
    re.compile(r"(?:api[_-]?key|token|secret)\s*[:=]\s*([\"'])?([A-Za-z0-9_\-]{8,})(\1)?", re.IGNORECASE),
    re.compile(r"Bearer\s+[A-Za-z0-9_\-]{8,}", re.IGNORECASE),
)
_REDACTED = "***REDACTED***"


def redact_text(text: str) -> str:
    redacted = text
    for pattern in _TOKEN_PATTERNS:
        redacted = pattern.sub(_REDACTED, redacted)
    return redacted


def redact_mapping(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {str(k): redact_value(v) for k, v in payload.items()}


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
