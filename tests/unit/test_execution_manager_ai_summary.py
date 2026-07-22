from __future__ import annotations

from pathlib import Path

from testo_api.execution_manager import ExecutionManager, ExecutionState
from testo_api.models import CreateExecutionRequest, RunSpecRequest
from testo_core.command_builders import BuiltCommand
from testo_core.runners import RunResult
from testo_core.services.headless_engine import EngineEvent, EngineSummary


class _RecordingFailureService:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def generate_summary(self, *, run_id: str, force_refresh: bool = False):  # noqa: ANN202
        self.calls.append(f"{run_id}:{force_refresh}")
        return None


def test_execution_manager_generates_ai_summary_for_failed_run() -> None:
    service = _RecordingFailureService()
    manager = ExecutionManager(failure_analysis_service=service)  # type: ignore[arg-type]
    state = ExecutionState(execution_id="exec-1")
    req = CreateExecutionRequest(
        runs=[RunSpecRequest(test_type="pytest", target_repo=".")],
        persist=True,
        trigger_source="ui",
        ci_mode=False,
    )
    run_result = RunResult(
        returncode=1,
        started_at=1.0,
        finished_at=2.0,
        command=BuiltCommand(
            argv=["pytest"],
            cwd=Path("."),
            env={"UQO_RUN_ID": "run-1", "UQO_LAST_TEST_TYPE": "pytest"},
        ),
    )

    def _stream(_request):  # noqa: ANN001, ANN202
        yield EngineEvent(kind="run_result", payload=run_result)
        return EngineSummary(
            schema_version="1",
            trigger_source="ui",
            ci_mode=False,
            persist=True,
            exit_code=1,
            aggregate_returncode=1,
            started_at=1.0,
            finished_at=2.0,
            runs=(),
            error=None,
            execution_mode="headless",
            failure_type="test_failure",
            sync={"status": "success", "runs": []},
        )

    manager._engine.stream = _stream  # type: ignore[assignment]
    manager._run_execution(state, req)

    assert service.calls == ["run-1:False"]


def test_execution_manager_skips_ai_summary_for_passing_run() -> None:
    service = _RecordingFailureService()
    manager = ExecutionManager(failure_analysis_service=service)  # type: ignore[arg-type]
    state = ExecutionState(execution_id="exec-1")
    req = CreateExecutionRequest(
        runs=[RunSpecRequest(test_type="pytest", target_repo=".")],
        persist=True,
        trigger_source="ui",
        ci_mode=False,
    )
    run_result = RunResult(
        returncode=0,
        started_at=1.0,
        finished_at=2.0,
        command=BuiltCommand(
            argv=["pytest"],
            cwd=Path("."),
            env={"UQO_RUN_ID": "run-1", "UQO_LAST_TEST_TYPE": "pytest"},
        ),
    )

    def _stream(_request):  # noqa: ANN001, ANN202
        yield EngineEvent(kind="run_result", payload=run_result)
        return EngineSummary(
            schema_version="1",
            trigger_source="ui",
            ci_mode=False,
            persist=True,
            exit_code=0,
            aggregate_returncode=0,
            started_at=1.0,
            finished_at=2.0,
            runs=(),
            error=None,
            execution_mode="headless",
            failure_type=None,
            sync={"status": "success", "runs": []},
        )

    manager._engine.stream = _stream  # type: ignore[assignment]
    manager._run_execution(state, req)

    assert service.calls == []
