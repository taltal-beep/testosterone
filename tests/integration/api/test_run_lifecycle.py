from __future__ import annotations

import time
from pathlib import Path

from fastapi.testclient import TestClient

from uqo_api.execution_manager import ExecutionManager
from uqo_api.main import create_app
from uqo_core.command_builders import BuiltCommand
from uqo_core.runners import LogEvent, RunResult
from uqo_core.services.headless_engine import EngineEvent, EngineRunRecord, EngineSummary


class _FakeEngine:
    def stream(self, request):  # noqa: ANN001
        del request
        yield EngineEvent(kind="log", payload=LogEvent(ts=time.time(), stream="stdout", line="hello\n"))
        rr = RunResult(
            returncode=0,
            started_at=time.time() - 0.2,
            finished_at=time.time(),
            command=BuiltCommand(
                argv=["pytest", "-q"],
                cwd=Path(".").resolve(),
                env={"UQO_RUN_ID": "run-123", "UQO_LAST_TEST_TYPE": "pytest"},
            ),
        )
        yield EngineEvent(kind="run_result", payload=rr)
        return EngineSummary(
            schema_version="1",
            trigger_source="ui",
            ci_mode=False,
            persist=True,
            exit_code=0,
            aggregate_returncode=0,
            started_at=time.time() - 0.5,
            finished_at=time.time(),
            runs=(
                EngineRunRecord(
                    test_type="pytest",
                    run_id="run-123",
                    returncode=0,
                    started_at=rr.started_at,
                    finished_at=rr.finished_at,
                    duration_s=max(0.0, rr.finished_at - rr.started_at),
                    cwd=str(rr.command.cwd),
                ),
            ),
            error=None,
            execution_mode="headless",
            failure_type=None,
            sync={"status": "success", "runs": []},
        )


def test_execution_lifecycle_with_sse_events() -> None:
    app = create_app()
    manager = ExecutionManager()
    manager._engine = _FakeEngine()  # type: ignore[assignment]
    from uqo_api.dependencies import get_execution_manager

    app.dependency_overrides[get_execution_manager] = lambda: manager
    client = TestClient(app)

    create = client.post(
        "/api/v1/executions",
        json={
            "runs": [{"test_type": "pytest", "target_repo": ".", "cli_args": ["-q"]}],
            "persist": True,
            "trigger_source": "ui",
            "ci_mode": False,
        },
    )
    assert create.status_code == 202
    execution_id = create.json()["execution_id"]

    for _ in range(20):
        status_resp = client.get(f"/api/v1/executions/{execution_id}")
        assert status_resp.status_code == 200
        payload = status_resp.json()
        if payload["status"] in {"completed", "failed"}:
            break
        time.sleep(0.05)
    assert payload["status"] == "completed"
    assert payload["run_ids"] == ["run-123"]

    with client.stream("GET", f"/api/v1/executions/{execution_id}/events") as stream_resp:
        assert stream_resp.status_code == 200
        body = "".join(chunk for chunk in stream_resp.iter_text())
    assert "event: log" in body
    assert "event: run_result" in body
    assert "event: summary" in body
