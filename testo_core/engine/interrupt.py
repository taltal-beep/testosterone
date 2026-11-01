"""Stop the running stages when ``testo`` is told to stop (P3/P4 in docs/engine-cli-review.md).

Each host stage runs in its own process group (see
:mod:`testo_core.engine.backends`), so a timeout kills the whole tree, not just the
direct child. The flip side is that Ctrl-C in a terminal no longer reaches the
stage by itself, so while :func:`run_plan` runs on the main thread it installs
handlers for SIGINT and SIGTERM (what CI cancel buttons send) that:

1. first signal: terminate every running stage's group and stop starting new stages;
   the run is still recorded, as interrupted, and ``testo`` exits 130 (SIGINT) or
   143 (SIGTERM);
2. second signal: kill the groups outright;
3. third: raise :class:`KeyboardInterrupt`, as before.

Stages started off the main thread (the API's worker pool) are killed at interpreter
exit, so stopping the server never leaves test processes behind.
"""

from __future__ import annotations

import atexit
import logging
import signal
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from types import FrameType
from typing import Any

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_running: set[Any] = set()
_signum: int | None = None
_count = 0


def register(proc: Any) -> None:
    """Track a running stage process (anything with ``terminate()`` and ``kill()``)."""
    with _lock:
        _running.add(proc)


def unregister(proc: Any) -> None:
    with _lock:
        _running.discard(proc)


def requested() -> int | None:
    """The signal that asked this run to stop, or None."""
    return _signum


def signal_name(signum: int) -> str:
    try:
        return signal.Signals(signum).name
    except ValueError:
        return f"signal {signum}"


def _stop_all(*, force: bool) -> None:
    with _lock:
        procs = list(_running)
    for proc in procs:
        try:
            proc.kill() if force else proc.terminate()
        except (OSError, ValueError):
            logger.debug("could not stop stage process %r", proc, exc_info=True)


def request_stop(signum: int) -> None:
    """What the signal handler does; callable directly (tests, other front ends)."""
    global _signum, _count
    _count += 1
    if _signum is None:
        _signum = signum
    if _count >= 3:
        raise KeyboardInterrupt
    _stop_all(force=_count >= 2)


def _handler(signum: int, _frame: FrameType | None) -> None:
    request_stop(signum)


def _reset() -> None:
    global _signum, _count
    _signum = None
    _count = 0


@contextmanager
def stop_on_signals() -> Iterator[None]:
    """Install the SIGINT/SIGTERM handlers for the block (main thread only)."""
    _reset()
    if threading.current_thread() is not threading.main_thread():
        yield
        return
    previous: dict[signal.Signals, Any] = {}
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            previous[sig] = signal.signal(sig, _handler)
        except (ValueError, OSError):  # not allowed here (embedded interpreter)
            continue
    try:
        yield
    finally:
        for sig, old in previous.items():
            try:
                signal.signal(sig, old)
            except (ValueError, OSError):
                pass


@atexit.register
def _kill_leftovers() -> None:
    _stop_all(force=True)
