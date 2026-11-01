"""One run of a cycle at a time: ``cycle_lock`` (P1 in docs/engine-cli-review.md)."""

from __future__ import annotations

import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

from testo_core.engine.cycle_lock import CycleLockTimeout, cycle_lock

pytestmark = [pytest.mark.unit, pytest.mark.tier_fast]


def test_a_second_holder_waits_and_says_why(tmp_path: Path) -> None:
    said: list[str] = []
    order: list[str] = []
    entered = threading.Event()

    def first() -> None:
        with cycle_lock(tmp_path, "web"):
            entered.set()
            time.sleep(0.6)
            order.append("first done")

    t = threading.Thread(target=first)
    t.start()
    assert entered.wait(5)
    with cycle_lock(tmp_path, "web", on_wait=said.append):
        order.append("second in")
    t.join()

    assert order == ["first done", "second in"]
    assert len(said) == 1
    assert "another run of cycle 'web'" in said[0] and "waiting" in said[0]


def test_other_cycles_do_not_wait(tmp_path: Path) -> None:
    with cycle_lock(tmp_path, "web"), cycle_lock(tmp_path, "api", timeout_s=0.5):
        pass


def test_timeout_names_the_holder(tmp_path: Path) -> None:
    with cycle_lock(tmp_path, "web"):
        with pytest.raises(CycleLockTimeout, match=r"cycle 'web'.*pid \d+"):
            with cycle_lock(tmp_path, "web", timeout_s=0.3):
                pass


def test_lock_is_released_after_the_block_and_after_an_error(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        with cycle_lock(tmp_path, "web"):
            raise ValueError("boom")
    with cycle_lock(tmp_path, "web", timeout_s=0.5):
        pass


def test_another_process_holding_the_lock_blocks_until_it_exits(tmp_path: Path) -> None:
    script = (
        "import sys, time\n"
        "from pathlib import Path\n"
        "from testo_core.engine.cycle_lock import cycle_lock\n"
        "with cycle_lock(Path(sys.argv[1]), 'web'):\n"
        "    print('held', flush=True)\n"
        "    time.sleep(30)\n"
    )
    proc = subprocess.Popen(
        [sys.executable, "-c", script, str(tmp_path)], stdout=subprocess.PIPE, text=True
    )
    try:
        assert proc.stdout is not None and proc.stdout.readline().strip() == "held"
        with pytest.raises(CycleLockTimeout):
            with cycle_lock(tmp_path, "web", timeout_s=0.5):
                pass
        proc.kill()  # a killed run must not leave the lock held
        proc.wait(10)
        with cycle_lock(tmp_path, "web", timeout_s=2):
            pass
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(10)
