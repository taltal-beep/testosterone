from __future__ import annotations

import builtins
import json
import time
import uuid
from pathlib import Path

from testo_core.command_builders import BuiltCommand
from testo_core.run_history import RunSyncStatus, SyncOperationStatus
from testo_core.runners import LogEvent, RunResult
from testo_core.services.headless_engine import HeadlessEngineService


def test_cli_ghost_auto_detect_smoke_with_mocked_sync(monkeypatch, capsys) -> None:  # noqa: ANN001
    from testo_core import cli

    fixture = Path("tests/fixtures/ci/ghost_minimal.yml").resolve()
    create_calls: list[dict] = []
    complete_calls: list[dict] = []
    streamlit_import_attempted = {"value": False}
    original_import = builtins.__import__

    def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):  # noqa: ANN001,A002
        if str(name).startswith("streamlit"):
            streamlit_import_attempted["value"] = True
            raise AssertionError("Streamlit must not be imported in ghost-mode CLI execution.")
        return original_import(name, globals, locals, fromlist, level)

    def fake_create_run(*, status, metadata):  # noqa: ANN001
        create_calls.append({"status": status, "metadata": dict(metadata or {})})
        return uuid.uuid4()

    def fake_record_completed_run(*, rr, artifacts_root, test_kind, metadata_context, audit_health_pct=None, db_path=None):  # noqa: ANN001
        del rr, artifacts_root, test_kind, audit_health_pct, db_path
        complete_calls.append(dict(metadata_context or {}))
        return RunSyncStatus(
            run_id="rid-smoke",
            db_finalize=SyncOperationStatus(status="success", attempts=1),
            artifact_upload=SyncOperationStatus(status="success", attempts=1),
        )

    def fake_streaming(cfg, **kwargs):  # noqa: ANN001
        del kwargs
        yield LogEvent(ts=time.time(), stream="stdout", line="smoke\n")
        cmd = BuiltCommand(
            argv=["pytest", "-q"],
            cwd=cfg.target_repo,
            env={
                "UQO_RUN_ID": str(cfg.run_id or "rid-smoke"),
                "UQO_LAST_TEST_TYPE": cfg.test_type.value,
                "UQO_ARTIFACTS_ROOT": str((cfg.artifacts_root or Path("artifacts")).resolve()),
            },
        )
        return RunResult(
            returncode=0,
            started_at=time.time() - 1.0,
            finished_at=time.time(),
            command=cmd,
        )

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    monkeypatch.setattr("testo_core.services.headless_engine.create_run", fake_create_run)
    monkeypatch.setattr("testo_core.services.headless_engine.record_completed_run", fake_record_completed_run)
    monkeypatch.setattr(
        cli,
        "HeadlessEngineService",
        lambda: HeadlessEngineService(run_streaming_fn=fake_streaming),
    )
    monkeypatch.setattr(cli.os, "environ", {"GITHUB_ACTIONS": "true", "GITHUB_RUN_ID": "777", "GITHUB_JOB": "smoke"})

    code = cli.main(["run", "--config", str(fixture), "--stream-json"])
    captured = capsys.readouterr()
    lines = [line for line in captured.out.splitlines() if line.strip()]
    summary = json.loads(lines[-1])

    assert code == 0
    assert streamlit_import_attempted["value"] is False
    assert create_calls
    assert complete_calls
    assert complete_calls[0]["execution_mode"] == "ghost"
    assert summary["execution_mode"] == "ghost"
    assert summary["sync"]["status"] == "success"
