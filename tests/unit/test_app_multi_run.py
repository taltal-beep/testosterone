from __future__ import annotations

import time
from pathlib import Path

from testo_core.command_builders import BuiltCommand, RunConfig, TestType
from testo_core.runners import UQO_DONE_MARKER, LogEvent, RunResult
from testo_core.services.multi_run import advance_after_run_result, stream_multi_run


def _run_result(run_id: str, returncode: int) -> RunResult:
    cmd = BuiltCommand(
        argv=["pytest"],
        cwd=Path("/tmp/target"),
        env={"UQO_RUN_ID": run_id},
    )
    return RunResult(
        returncode=returncode,
        started_at=time.time(),
        finished_at=time.time(),
        command=cmd,
    )


def _config(run_id: str) -> RunConfig:
    return RunConfig(
        test_type=TestType.PYTEST,
        target_repo=Path("/tmp/target"),
        shared_allure_results_dir=Path("/tmp/allure") / run_id,
        run_id=run_id,
    )


def test_multi_run_suppresses_per_config_done_markers() -> None:
    seen_emit_done_values: list[bool] = []

    def fake_run_streaming(cfg, *, artifacts_root, emit_done_marker=True, **kwargs):
        seen_emit_done_values.append(bool(emit_done_marker))
        yield LogEvent(ts=time.time(), stream="stdout", line=f"{cfg.run_id} output\n")
        return _run_result(str(cfg.run_id), 0)

    items = list(
        stream_multi_run(
            [_config("run-1"), _config("run-2")],
            artifacts_root=Path("/tmp/artifacts"),
            db_run_ids=["run-1", "run-2"],
            run_streaming_fn=fake_run_streaming,
            update_run_status_fn=lambda *_, **__: None,
        )
    )

    assert seen_emit_done_values == [False, False]
    log_lines = [item.line for item in items if isinstance(item, LogEvent)]
    done_lines = [line for line in log_lines if UQO_DONE_MARKER in line]
    assert len(done_lines) == 1
    assert "run-1 output\n" in log_lines
    assert "run-2 output\n" in log_lines
    assert [item.command.env["UQO_RUN_ID"] for item in items if isinstance(item, RunResult)] == ["run-1", "run-2"]


def test_multi_run_result_keeps_polling_until_last_result() -> None:
    state = advance_after_run_result(multi_run_active=True, multi_runs_remaining=2)

    assert state.running is True
    assert state.run_completed is False
    assert state.multi_run_active is True
    assert state.multi_runs_remaining == 1

    state = advance_after_run_result(
        multi_run_active=state.multi_run_active,
        multi_runs_remaining=state.multi_runs_remaining,
    )

    assert state.running is False
    assert state.run_completed is True
    assert state.multi_run_active is False
    assert state.multi_runs_remaining == 0
