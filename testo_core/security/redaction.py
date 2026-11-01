"""Hide secrets in text before Testosterone stores it or sends it anywhere.

Two users: the AI failure context (:mod:`testo_core.services.failure_context_builder`)
and every run's artifacts on disk (:func:`redact_run_artifacts`, called by the engine
before a run is recorded), so failure messages, stack traces and logs in history,
Compare, the test page and report snapshots never keep an API key a test printed.

The built-in patterns catch common token shapes (cloud keys, GitHub, Slack, JWTs,
bearer tokens, ``password=…``, credentials in URLs, private key blocks). Add your
own regular expressions with ``TESTO_REDACT_PATTERNS`` (one per line), and turn
artifact redaction off with ``TESTO_REDACT=0``.
"""

from __future__ import annotations

import logging
import os
import re
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

REDACTED = "***REDACTED***"
_REDACTED = REDACTED

PATTERNS_ENV = "TESTO_REDACT_PATTERNS"
SWITCH_ENV = "TESTO_REDACT"

_TOKEN_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.DOTALL),
    re.compile(r"sk-[A-Za-z0-9_\-]{8,}"),
    re.compile(
        r"(?:api[_-]?key|token|secret)\s*[:=]\s*([\"'])?([A-Za-z0-9_\-]{8,})(\1)?", re.IGNORECASE
    ),
    re.compile(r"(?:password|passwd|pwd)\s*[:=]\s*([\"'])?[^\s\"',;\\]{6,}(\1)?", re.IGNORECASE),
    re.compile(r"Bearer\s+[A-Za-z0-9_\-.=]{8,}", re.IGNORECASE),
    re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
    re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{30,}\b"),
    re.compile(r"\bglpat-[A-Za-z0-9_\-]{20,}\b"),
    re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b"),
    re.compile(r"https://hooks\.slack\.com/services/[A-Za-z0-9/_\-]+"),
    re.compile(r"\beyJ[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}"),
    # user:password in a URL (keeps the scheme and host, so the message still makes sense)
    re.compile(r"(?<=://)[^/\s:@\"'\\]+:[^/\s@\"'\\]+(?=@)"),
)
_SENSITIVE_KEY_PATTERN = re.compile(
    r"(^|[_\-\s])(api[_\-\s]?key|token|secret|authorization|password)([_\-\s]|$)",
    re.IGNORECASE,
)

# Artifact files worth scanning: text a runner or importer wrote. Others (traces,
# screenshots, videos) are binary and left alone.
TEXT_SUFFIXES = frozenset(
    {".json", ".xml", ".log", ".txt", ".out", ".err", ".html", ".md", ".ndjson", ".trx", ".csv"}
)
MAX_FILE_BYTES = 50 * 1024 * 1024


def extra_patterns(env: Mapping[str, str] | None = None) -> tuple[re.Pattern[str], ...]:
    """The user's own patterns from ``TESTO_REDACT_PATTERNS`` (one regular expression per line)."""
    raw = (env if env is not None else os.environ).get(PATTERNS_ENV) or ""
    out: list[re.Pattern[str]] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(re.compile(line))
        except re.error as exc:
            logger.warning("%s: ignoring %r (%s)", PATTERNS_ENV, line, exc)
    return tuple(out)


def redact_text(text: str, patterns: Iterable[re.Pattern[str]] | None = None) -> str:
    """``text`` with every match of the built-in (and ``TESTO_REDACT_PATTERNS``) patterns hidden."""
    redacted = text
    for pattern in (*_TOKEN_PATTERNS, *(extra_patterns() if patterns is None else patterns)):
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


def artifact_redaction_enabled(env: Mapping[str, str] | None = None) -> bool:
    raw = ((env if env is not None else os.environ).get(SWITCH_ENV) or "").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def redact_run_artifacts(root: Path, env: Mapping[str, str] | None = None) -> int:
    """Rewrite the text files under ``root`` with secrets hidden; return how many changed.

    Called on a run's artifacts before it is recorded, so the stored per-test
    results (messages, stack traces), stage logs and report files never hold
    them. Files that aren't UTF-8 text, or are bigger than 50 MB, are skipped.
    Does nothing when ``TESTO_REDACT=0``.
    """
    if not artifact_redaction_enabled(env) or not root.is_dir():
        return 0
    patterns = extra_patterns(env)
    changed = 0
    for path in root.rglob("*"):
        if path.suffix.lower() not in TEXT_SUFFIXES or path.is_symlink() or not path.is_file():
            continue
        try:
            if path.stat().st_size > MAX_FILE_BYTES:
                continue
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        clean = redact_text(text, patterns)
        if clean == text:
            continue
        try:
            path.write_text(clean, encoding="utf-8")
        except OSError:
            logger.warning("could not redact %s", path, exc_info=True)
            continue
        changed += 1
    return changed
