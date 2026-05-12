from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from testo_core.command_builders import BuiltCommand, TestType
from testo_core.runners import LogEvent, RunResult
from testo_core.services.headless_engine import EngineEvent, EngineRunSpec, EngineSummary


@pytest.mark.contract
def test_ghost_mode_stream_json_emits_ndjson_then_summary(monkeypatch, capsys, tmp_path: Path) -> None:  # noqa: ANN001
    from testo_core import cli

    target = tmp_path / "repo"
    target.mkdir()
    monkeypatch.setattr(
        cli,
        "load_run_specs_from_yaml",
        lambda _path: (EngineRunSpec(test_type=TestType.PYTEST, target_repo=target),),
    )

    cmd = BuiltCommand(
        argv=["pytest", "-q"],
        cwd=target,
        env={"UQO_RUN_ID": "rid-ndjson", "UQO_LAST_TEST_TYPE": "pytest"},
    )
    rr = RunResult(returncode=0, started_at=time.time() - 1.0, finished_at=time.time(), command=cmd)

    class FakeEngine:
        def stream(self, request):  # noqa: ANN001
            del request
            yield EngineEvent(kind="log", payload=LogEvent(ts=time.time(), stream="stdout", line="ok\n"))
            yield EngineEvent(kind="run_result", payload=rr)
            return EngineSummary(
                schema_version="1",
                trigger_source="ci",
                ci_mode=True,
                persist=True,
                exit_code=0,
                aggregate_returncode=0,
                started_at=time.time() - 1.0,
                finished_at=time.time(),
                runs=(),
                execution_mode="ghost",
                sync={"status": "success", "runs": []},
            )

    monkeypatch.setattr(cli, "HeadlessEngineService", FakeEngine)
    code = cli.main(["run", "--config", "ghost.yml", "--ghost", "--stream-json"])
    captured = capsys.readouterr()

    assert code == 0
    assert captured.err == ""
    lines = [line for line in captured.out.splitlines() if line.strip()]
    assert len(lines) == 3
    event = json.loads(lines[0])
    run_event = json.loads(lines[1])
    summary = json.loads(lines[2])
    assert event["event"] == "log"
    assert run_event["event"] == "run_result"
    assert summary["execution_mode"] == "ghost"
    assert summary["sync"]["status"] == "success"
