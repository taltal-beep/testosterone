from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from testo_core.history.views import CompletedRunView
from testo_core.security.redaction import redact_text, redact_value


@dataclass(frozen=True)
class FailureContextBudget:
    max_total_chars: int = 16_000
    max_log_chars: int = 8_000
    max_trace_chars: int = 4_000
    max_metadata_chars: int = 4_000


@dataclass(frozen=True)
class FailureContext:
    prompt: str
    context_stats: dict[str, int]
    limitations: tuple[str, ...]


def _truncate(value: str, *, limit: int, label: str) -> tuple[str, bool]:
    if len(value) <= limit:
        return value, False
    suffix = f"\n...[truncated {label}]..."
    if limit <= len(suffix):
        return value[:limit], True
    keep = limit - len(suffix)
    return f"{value[:keep]}{suffix}", True


def _redacted_context_text(value: Any) -> str:
    if value is None:
        return ""
    redacted = redact_value(value)
    if isinstance(redacted, str):
        return redacted
    try:
        return json.dumps(redacted, sort_keys=True, default=str)
    except TypeError:
        return redact_text(str(redacted))


def build_failure_context(
    *,
    run: CompletedRunView,
    metadata: dict[str, Any],
    budget: FailureContextBudget,
) -> FailureContext:
    summary_block = (
        f"run_id={run.run_id}\n"
        f"test_kind={run.test_kind}\n"
        f"status={run.status.value if run.status else 'unknown'}\n"
        f"returncode={run.returncode}\n"
        f"failed={run.failed}\n"
        f"broken={run.broken}\n"
        f"health_pct={run.health_pct}\n"
    )
    raw_log = _redacted_context_text(metadata.get("error_message") or metadata.get("error"))
    raw_trace = _redacted_context_text(
        metadata.get("traceback") or metadata.get("stack_trace") or metadata.get("audit_json")
    )
    raw_meta = _redacted_context_text(metadata.get("sync"))

    log_section, log_truncated = _truncate(raw_log, limit=budget.max_log_chars, label="log")
    trace_section, trace_truncated = _truncate(raw_trace, limit=budget.max_trace_chars, label="trace")
    meta_section, meta_truncated = _truncate(raw_meta, limit=budget.max_metadata_chars, label="metadata")

    prompt = (
        "You are an assistant that explains CI/test failures in concise operational language.\n"
        "Provide: 1) short summary, 2) likely root cause, 3) next actions.\n"
        "State limitations when evidence is incomplete.\n\n"
        f"[Run]\n{summary_block}\n"
        f"[FailureLog]\n{log_section}\n\n"
        f"[Trace]\n{trace_section}\n\n"
        f"[Metadata]\n{meta_section}\n"
    )
    prompt, prompt_truncated = _truncate(prompt, limit=budget.max_total_chars, label="prompt")
    limitations: list[str] = []
    if log_truncated:
        limitations.append("log_truncated")
    if trace_truncated:
        limitations.append("trace_truncated")
    if meta_truncated:
        limitations.append("metadata_truncated")
    if prompt_truncated:
        limitations.append("context_budget_truncated")
    return FailureContext(
        prompt=prompt,
        context_stats={
            "prompt_chars": len(prompt),
            "log_chars": len(log_section),
            "trace_chars": len(trace_section),
            "metadata_chars": len(meta_section),
        },
        limitations=tuple(limitations),
    )
