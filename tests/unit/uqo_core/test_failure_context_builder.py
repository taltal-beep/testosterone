from __future__ import annotations

from uqo_core.repository.models import RunStatus
from uqo_core.run_history import CompletedRunView
from uqo_core.services.failure_context_builder import FailureContextBudget, build_failure_context


def _run() -> CompletedRunView:
    return CompletedRunView(
        run_id="run-1",
        status=RunStatus.FAILED,
        created_at=1.0,
        started_at=1.0,
        finished_at=2.0,
        test_kind="pytest",
        returncode=1,
        wall_duration_ms=100.0,
        metrics_duration_ms=90,
        total_tests=10,
        passed=8,
        failed=2,
        broken=0,
        skipped=0,
        avg_case_ms=10.0,
        health_pct=80.0,
        target_repo=".",
        snapshot_dir=None,
        audit_json=None,
    )


def test_failure_context_applies_budget_truncation() -> None:
    context = build_failure_context(
        run=_run(),
        metadata={"error_message": "x" * 200},
        budget=FailureContextBudget(max_total_chars=120, max_log_chars=40, max_trace_chars=20, max_metadata_chars=20),
    )
    assert context.context_stats["prompt_chars"] <= 120
    assert "log_truncated" in context.limitations or "context_budget_truncated" in context.limitations


def test_failure_context_redacts_secrets_from_all_prompt_sections() -> None:
    context = build_failure_context(
        run=_run(),
        metadata={
            "error_message": "request failed with api_key=logsecret123",
            "traceback": "Trace included Bearer traceToken123456",
            "sync": {"token": "metasecret123", "status": "failed"},
        },
        budget=FailureContextBudget(max_total_chars=2_000),
    )

    assert "***REDACTED***" in context.prompt
    assert "logsecret123" not in context.prompt
    assert "traceToken123456" not in context.prompt
    assert "metasecret123" not in context.prompt


def test_failure_context_uses_primary_metadata_keys_before_fallbacks() -> None:
    context = build_failure_context(
        run=_run(),
        metadata={
            "error_message": "primary log",
            "error": "fallback log",
            "traceback": "primary trace",
            "stack_trace": "fallback trace",
            "audit_json": "fallback audit",
        },
        budget=FailureContextBudget(max_total_chars=2_000),
    )

    assert "primary log" in context.prompt
    assert "primary trace" in context.prompt
    assert "fallback log" not in context.prompt
    assert "fallback trace" not in context.prompt
    assert "fallback audit" not in context.prompt
