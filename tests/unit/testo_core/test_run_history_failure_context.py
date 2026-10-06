from __future__ import annotations

import json
from pathlib import Path

from testo_core import run_history
from testo_core.command_builders import BuiltCommand
from testo_core.runners import RunResult


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

    context, trace_excerpt = run_history._extract_failure_context_from_allure(
        results_dir=results_dir
    )

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
    (logs_dir / f"{run_id}.log").write_text(
        "line1\nline2\nline3 token=abcdefghi\n", encoding="utf-8"
    )
    monkeypatch.setattr(run_history, "ORCHESTRATOR_ROOT", tmp_path)

    tail = run_history._read_run_log_tail(run_id=run_id, max_chars=12)

    assert tail is not None
    assert "line3" in tail or "line2" in tail
    assert len(tail) <= 12 + len("\n...[truncated]...")


def test_record_completed_run_persists_allure_failure_context(tmp_path: Path, monkeypatch) -> None:
    artifacts_root = tmp_path / "artifacts"
    results_dir = artifacts_root / "allure-results"
    results_dir.mkdir(parents=True, exist_ok=True)
    (results_dir / "failed-result.json").write_text(
        json.dumps(
            {
                "name": "test_checkout",
                "fullName": "tests.checkout.test_checkout",
                "status": "failed",
                "statusDetails": {
                    "message": "Checkout total mismatch",
                    "trace": "Traceback: AssertionError: Checkout total mismatch",
                },
            }
        ),
        encoding="utf-8",
    )
    captured: dict[str, object] = {}
    monkeypatch.setattr(run_history, "_snapshot_reports", lambda **_: None)
    monkeypatch.setattr(run_history, "_upload_allure_results_to_s3", lambda **_: 0)
    monkeypatch.setattr(
        run_history,
        "update_run_status",
        lambda _run_id, *, status, metadata: captured.update(metadata),
    )
    cmd = BuiltCommand(argv=["pytest"], cwd=tmp_path, env={"UQO_RUN_ID": "rid-1"})
    rr = RunResult(returncode=1, started_at=0.0, finished_at=1.0, command=cmd)

    run_history.record_completed_run(rr=rr, artifacts_root=artifacts_root, test_kind="pytest")

    assert captured["failure_context"]["captured_cases"] == 1
    assert captured["failure_context"]["failed_cases"][0]["name"] == "test_checkout"
    assert captured["error_message"] == "Checkout total mismatch"
    assert "AssertionError" in captured["traceback"]
