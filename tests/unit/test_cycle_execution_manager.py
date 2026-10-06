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
