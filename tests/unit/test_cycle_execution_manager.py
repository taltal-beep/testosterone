"""``CycleExecutionManager`` — API cycle runs go through ``CycleRunService``."""

from __future__ import annotations

import asyncio
import json
import threading
import time
from collections.abc import AsyncIterator
from pathlib import Path

import pytest

from testo_api.cycle_execution_manager import (
    DEFAULT_MAX_FINISHED_EXECUTIONS,
    CycleExecutionManager,
    CycleExecutionState,
    iter_execution_sse,
    iter_sse_from_ndjson_file,
)
from testo_core.services import cycle_run as cycle_run_mod
from testo_core.triggers import TriggerResult
from tests.fixtures.engine import (
    read_artifact_events,
    stage_spec,
    use_echo_adapter,
    write_cycles_config,
    write_minimal_config,
)

pytestmark = [pytest.mark.unit, pytest.mark.tier_fast]


def _wait(state: CycleExecutionState, timeout_s: float = 20.0) -> None:
    deadline = time.monotonic() + timeout_s
    while not state.done:
        assert time.monotonic() < deadline, "cycle execution did not finish"
        time.sleep(0.05)


def test_execution_runs_cycle_and_writes_events(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    adapter = use_echo_adapter(monkeypatch)
    config = write_minimal_config(tmp_path)

    state = CycleExecutionManager().create_execution(
        cycle="smoke", config_path=config, report_db=False
    )
    _wait(state)

    assert state.status == "completed", state.error
    assert len(adapter.calls) == 1
    kinds = [e["event"] for e in read_artifact_events(tmp_path / "artifacts", "smoke")]
    assert kinds[-1] == "plan_finished"


def test_resting_trigger_emits_trigger_and_terminal_event(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    adapter = use_echo_adapter(monkeypatch)
    monkeypatch.setattr(
        cycle_run_mod,
        "evaluate_cycle_trigger",
        lambda *, plan, cfg: TriggerResult(
            stimulus=False,
            reason="no changes",
            matched_paths=(),
            mode="snapshot",
            persist_snapshot_after_run=False,
        ),
    )
    config = write_cycles_config(
        tmp_path, cycles={"gated": [stage_spec("g")]}, trigger_paths={"gated": ["src/**"]}
    )

    state = CycleExecutionManager().create_execution(cycle="gated", config_path=config)
    _wait(state)

    assert state.status == "completed", state.error
    assert adapter.calls == []
    events = read_artifact_events(tmp_path / "artifacts", "gated")
    assert [e["event"] for e in events] == ["cycle_trigger", "plan_finished"]
    assert events[0]["status"] == "resting"
    assert events[1]["exit_code"] == 0


def test_adhoc_execution_runs_one_stage_plan_through_the_engine(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    adapter = use_echo_adapter(monkeypatch)
    config = write_minimal_config(tmp_path)

    state = CycleExecutionManager().create_adhoc_execution(
        framework="pytest",
        target_repo=tmp_path,
        args=["--text", "adhoc-ok"],
        config_path=config,
        report_db=False,
    )
    _wait(state)

    assert state.status == "completed", state.error
    assert state.cycle == "adhoc"
    assert len(adapter.calls) == 1
    events = read_artifact_events(tmp_path / "artifacts", "adhoc")
    assert [e["event"] for e in events][-1] == "plan_finished"
    assert any(e["event"] == "stage_started" and e.get("stage") == "pytest" for e in events)


def test_adhoc_execution_rejects_unknown_framework_before_starting(tmp_path: Path) -> None:
    from testo_core.config.errors import ConfigValidationError

    manager = CycleExecutionManager()
    with pytest.raises(ConfigValidationError, match="unknown framework"):
        manager.create_adhoc_execution(framework="locust", target_repo=tmp_path)
    with pytest.raises(ConfigValidationError, match="not a directory"):
        manager.create_adhoc_execution(framework="pytest", target_repo=tmp_path / "missing")


# --- Bounded registry -------------------------------------------------------


def _start_blocked(
    manager: CycleExecutionManager, cycle: str, release: threading.Event
) -> CycleExecutionState:
    """Start an execution whose config load waits for ``release`` and then fails."""

    def load_plan():  # noqa: ANN202
        assert release.wait(10)
        raise RuntimeError("config went away")

    return manager._start(
        cycle=cycle,
        load_plan=load_plan,
        artifacts_root_override=None,
        persist=False,
        force=False,
        fail_fast=False,
        reporter_override=None,
        report_db=False,
        async_report_db=False,
        workers_override=None,
        stream=False,
        ci=True,
    )


def test_registry_evicts_oldest_finished_executions_beyond_the_cap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    use_echo_adapter(monkeypatch)
    config = write_minimal_config(tmp_path)
    manager = CycleExecutionManager(max_finished=2)

    states = []
    for _ in range(3):
        # Back to back on one cycle: `done` is only set once the cycle is free again.
        state = manager.create_execution(cycle="smoke", config_path=config, report_db=False)
        _wait(state)
        states.append(state)

    assert manager.get(states[0].execution_id) is None
    assert manager.get(states[1].execution_id) is states[1]
    assert manager.get(states[2].execution_id) is states[2]


def test_registry_never_evicts_running_executions() -> None:
    manager = CycleExecutionManager(max_finished=1)
    release_running = threading.Event()
    running = _start_blocked(manager, "slow", release_running)
    finished = []
    for cycle in ("fast-1", "fast-2"):
        release = threading.Event()
        state = _start_blocked(manager, cycle, release)
        release.set()
        _wait(state)
        finished.append(state)

    assert manager.get(finished[0].execution_id) is None
    assert manager.get(finished[1].execution_id) is finished[1]
    assert manager.get(running.execution_id) is running  # older than both, still kept
    release_running.set()
    _wait(running)


def test_max_finished_comes_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TESTO_MAX_FINISHED_EXECUTIONS", "7")
    assert CycleExecutionManager().max_finished == 7
    # 0 would evict a run before anyone could read its final status.
    monkeypatch.setenv("TESTO_MAX_FINISHED_EXECUTIONS", "0")
    assert CycleExecutionManager().max_finished == 1
    monkeypatch.setenv("TESTO_MAX_FINISHED_EXECUTIONS", "lots")
    assert CycleExecutionManager().max_finished == DEFAULT_MAX_FINISHED_EXECUTIONS
    monkeypatch.delenv("TESTO_MAX_FINISHED_EXECUTIONS")
    assert CycleExecutionManager().max_finished == DEFAULT_MAX_FINISHED_EXECUTIONS


# --- SSE tail ---------------------------------------------------------------


def _line(event: str, **fields: object) -> str:
    return json.dumps({"event": event, **fields}) + "\n"


def _collect(stream: AsyncIterator[str], timeout_s: float = 5.0) -> list[str]:
    async def drain() -> list[str]:
        return [message async for message in stream]

    return asyncio.run(asyncio.wait_for(drain(), timeout_s))


def _event_names(messages: list[str]) -> list[str]:
    return [m.split("\n", 1)[0].removeprefix("event: ") for m in messages if m.startswith("event:")]


def test_sse_stream_drains_its_own_events_and_ends_when_done(tmp_path: Path) -> None:
    events = tmp_path / "events.ndjson"
    events.write_text(_line("previous_run") + _line("plan_started"), encoding="utf-8")
    end: list[int] = []  # set once the run is done, like `events_end_offset_bytes`

    def worker() -> None:
        time.sleep(0.1)
        with events.open("a", encoding="utf-8") as fh:
            fh.write(_line("stage_started", stage="s"))
            fh.write('{"event": "half_writ')  # a line mid-write must not be lost
            fh.flush()
            time.sleep(0.1)
            fh.write('ten"}\n' + _line("plan_finished", exit_code=0))
        end.append(events.stat().st_size)
        # The next run of the cycle appends to the same file right away.
        with events.open("a", encoding="utf-8") as fh:
            fh.write(_line("next_run"))

    threading.Thread(target=worker, daemon=True).start()
    messages = _collect(
        iter_sse_from_ndjson_file(
            events_path=events,
            start_offset_bytes=len(_line("previous_run")),
            end_offset=lambda: end[0] if end else None,
            min_poll_s=0.01,
        )
    )

    assert _event_names(messages) == [
        "plan_started",
        "stage_started",
        "half_written",
        "plan_finished",
    ]


def test_sse_final_drain_keeps_a_last_line_without_newline(tmp_path: Path) -> None:
    events = tmp_path / "events.ndjson"
    events.write_text('{"event": "plan_finished"}', encoding="utf-8")

    messages = _collect(
        iter_sse_from_ndjson_file(
            events_path=events, start_offset_bytes=0, end_offset=lambda: events.stat().st_size
        )
    )

    assert _event_names(messages) == ["plan_finished"]


def test_sse_stream_stops_promptly_when_the_client_goes_away(tmp_path: Path) -> None:
    # On disconnect Starlette cancels the response task; the tail must not outlive it.
    async def scenario() -> float:
        stream = iter_sse_from_ndjson_file(
            events_path=tmp_path / "never-written.ndjson",
            start_offset_bytes=0,
            end_offset=lambda: None,
            max_poll_s=30,
        )
        task = asyncio.create_task(anext(stream))
        await asyncio.sleep(0.2)  # well into its backoff sleep
        started = time.monotonic()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        return time.monotonic() - started

    assert asyncio.run(scenario()) < 0.5


def test_execution_sse_reports_a_failure_before_any_events_file() -> None:
    manager = CycleExecutionManager()
    release = threading.Event()
    state = _start_blocked(manager, "broken", release)
    release.set()

    messages = _collect(iter_execution_sse(manager, state.execution_id, min_poll_s=0.01))

    assert _event_names(messages) == ["error"]
    assert "config went away" in messages[0]


def test_execution_sse_streams_the_run_and_closes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    use_echo_adapter(monkeypatch)
    config = write_minimal_config(tmp_path)
    manager = CycleExecutionManager()
    state = manager.create_execution(cycle="smoke", config_path=config, report_db=False)

    messages = _collect(iter_execution_sse(manager, state.execution_id, min_poll_s=0.01), 20)

    names = _event_names(messages)
    assert names[0] == "plan_started"
    assert names[-1] == "plan_finished"
