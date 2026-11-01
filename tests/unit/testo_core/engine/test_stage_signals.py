"""Timeouts and signals stop the whole stage (P3/P4 in docs/engine-cli-review.md)."""

from __future__ import annotations

import json
import os
import signal
import sys
import threading
import time
from pathlib import Path

import pytest

from testo_core.config.schema import Plan, Stage
from testo_core.engine import interrupt
from testo_core.engine.exit_codes import EngineExitCode
from testo_core.engine.orchestrator import run_plan
from tests.fixtures.engine import NoopRenderer

pytestmark = [
    pytest.mark.unit,
    pytest.mark.tier_fast,
    pytest.mark.skipif(sys.platform == "win32", reason="POSIX process groups"),
]

# Starts a grandchild that records its pid, then waits on it.
_TREE = (
    "import subprocess, sys, pathlib\n"
    "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])\n"
    "pathlib.Path(sys.argv[1]).write_text(str(child.pid))\n"
    "child.wait()\n"
)


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    # A zombie still answers kill(0); it is dead for our purposes.
    try:
        with open(f"/proc/{pid}/stat", encoding="utf-8") as fh:
            return fh.read().split()[2] != "Z"
    except OSError:
        return True


def _stage(name: str, args: tuple[str, ...], timeout_s: float = 30.0) -> Stage:
    return Stage(
        name=name, framework="command", target_repo=Path("."), args=args, timeout_s=timeout_s
    )


def _wait_for(path: Path) -> int:
    for _ in range(100):
        if path.is_file() and path.read_text().strip():
            return int(path.read_text())
        time.sleep(0.05)
    raise AssertionError("grandchild never started")


def _gone(pid: int) -> bool:
    for _ in range(40):
        if not _alive(pid):
            return True
        time.sleep(0.05)
    os.kill(pid, signal.SIGKILL)
    return False


def test_a_timeout_also_kills_what_the_stage_started(tmp_path: Path) -> None:
    pid_file = tmp_path / "grandchild.pid"
    plan = Plan(
        name="tree",
        description=None,
        stages=(_stage("s1", (sys.executable, "-c", _TREE, str(pid_file)), timeout_s=1.5),),
    )
    result = run_plan(plan, renderer=NoopRenderer(), artifacts_root=tmp_path / "a", persist=False)

    assert result.stages[0].returncode == 124
    assert _gone(_wait_for(pid_file))


def test_sigterm_stops_the_stage_skips_the_rest_and_records_why(tmp_path: Path) -> None:
    pid_file = tmp_path / "grandchild.pid"
    plan = Plan(
        name="stopme",
        description=None,
        stages=(
            _stage("s1", (sys.executable, "-c", _TREE, str(pid_file))),
            _stage("s2", (sys.executable, "-c", "print('s2 ran')")),
        ),
    )

    def stop_soon() -> None:
        _wait_for(pid_file)
        interrupt.request_stop(signal.SIGTERM)

    threading.Thread(target=stop_soon, daemon=True).start()
    started = time.monotonic()
    result = run_plan(plan, renderer=NoopRenderer(), artifacts_root=tmp_path / "a", persist=False)

    assert time.monotonic() - started < 20
    assert result.exit_code == EngineExitCode.TERMINATED == 143
    assert [s.stage_name for s in result.stages] == ["s1"]
    assert result.stages[0].returncode == 143
    assert result.stages[0].error == "stopped by SIGTERM"
    assert result.extra["run_metadata"]["interrupted_by"] == "SIGTERM"
    assert _gone(int(pid_file.read_text()))
    events = [
        json.loads(line)
        for line in (tmp_path / "a" / "stopme" / "events.ndjson").read_text().splitlines()
    ]
    aborted = [e for e in events if e["event"] == "plan_aborted"]
    assert aborted and aborted[-1]["reason"] == "signal" and aborted[-1]["signal"] == "SIGTERM"


def test_the_next_run_starts_clean(tmp_path: Path) -> None:
    interrupt.request_stop(signal.SIGINT)  # left over from an earlier run in this process
    plan = Plan(
        name="ok",
        description=None,
        stages=(_stage("s1", (sys.executable, "-c", "print('hi')")),),
    )
    result = run_plan(plan, renderer=NoopRenderer(), artifacts_root=tmp_path, persist=False)
    assert result.exit_code == EngineExitCode.SUCCESS
