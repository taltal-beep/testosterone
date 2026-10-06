"""``CycleExecutionManager`` — API cycle runs go through ``CycleRunService``."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from testo_api.cycle_execution_manager import CycleExecutionManager, CycleExecutionState
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


def test_execution_runs_cycle_and_writes_events(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = use_echo_adapter(monkeypatch)
    config = write_minimal_config(tmp_path)

    state = CycleExecutionManager().create_execution(cycle="smoke", config_path=config, report_db=False)
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
