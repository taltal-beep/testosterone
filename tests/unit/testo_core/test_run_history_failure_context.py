from __future__ import annotations

import json
from pathlib import Path

from testo_core import run_history


def test_extract_failure_context_from_allure_collects_failed_cases(tmp_path: Path) -> None:
    results_dir = tmp_path / "allure-results"
    results_dir.mkdir(parents=True, exist_ok=True)
    failed_payload = {
        "name": "test_auth_expiry",
        "fullName": "tests.auth.test_auth_expiry",
        "status": "failed",
        "statusDetails": {
            "message": "API failed: token expired",
            "trace": "Traceback: AuthError: token expired",
        },
    }
    passed_payload = {
        "name": "test_ok",
        "status": "passed",
    }
    (results_dir / "a-result.json").write_text(json.dumps(failed_payload), encoding="utf-8")
    (results_dir / "b-result.json").write_text(json.dumps(passed_payload), encoding="utf-8")

    context, trace_excerpt = run_history._extract_failure_context_from_allure(results_dir=results_dir)

    assert context is not None
    assert context["schema_version"] == "v1"
    assert context["captured_cases"] == 1
    assert context["failed_cases"][0]["name"] == "test_auth_expiry"
    assert context["failed_cases"][0]["status"] == "failed"
    assert "token expired" in context["failed_cases"][0]["message"]
    assert trace_excerpt is not None
    assert "AuthError" in trace_excerpt


def test_read_run_log_tail_reads_from_orchestrator_logs(tmp_path: Path, monkeypatch) -> None:
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    run_id = "run-123"
    (logs_dir / f"{run_id}.log").write_text("line1\nline2\nline3 token=abcdefghi\n", encoding="utf-8")
    monkeypatch.setattr(run_history, "ORCHESTRATOR_ROOT", tmp_path)

    tail = run_history._read_run_log_tail(run_id=run_id, max_chars=12)

    assert tail is not None
    assert "line3" in tail or "line2" in tail
    assert len(tail) <= 12 + len("\n...[truncated]...")
