"""One run of a cycle at a time per artifacts folder.

Every run of a cycle writes ``<artifacts>/<cycle>/<stage>/`` and resets it when the
stage starts, so two runs of one cycle at once (two CI jobs on one runner, ``testo
watch`` plus a manual run, the CLI next to the API) wipe each other's results and
mix their logs. :func:`cycle_lock` holds an OS file lock on
``<artifacts>/<cycle>/.lock`` for the whole run; a second run waits for it and says
so. The OS drops the lock when the process exits, so a crashed run never leaves it
held. See ``docs/Specs & ADRs/Engine Fixes - 2026-11-01.md``.
"""

from __future__ import annotations

import os
import sys
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import IO

from testo_core.reporting.paths import plan_artifacts_dir

LOCK_NAME = ".lock"
_POLL_S = 0.2


class CycleLockTimeout(RuntimeError):
    """Another run of the cycle held the lock for longer than the caller would wait."""


def _try_lock(handle: IO[bytes]) -> bool:
    if sys.platform == "win32":
        import msvcrt

        handle.seek(0)
        try:
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            return False
        return True
    import fcntl

    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return False
    return True


def _unlock(handle: IO[bytes]) -> None:
    if sys.platform == "win32":
        import msvcrt

        handle.seek(0)
        try:
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        except OSError:
            pass
        return
    import fcntl

    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _holder(path: Path) -> str:
    try:
        text = path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""
    return f" (pid {text})" if text.isdigit() else ""


@contextmanager
def cycle_lock(
    artifacts_root: Path,
    cycle: str,
    *,
    on_wait: Callable[[str], None] | None = None,
    timeout_s: float | None = None,
) -> Iterator[Path]:
    """Hold the cycle's lock for the ``with`` block; wait (calling *on_wait* once) while
    another run holds it. Raises :class:`CycleLockTimeout` after *timeout_s*."""
    folder = plan_artifacts_dir(artifacts_root, cycle)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / LOCK_NAME
    handle = open(path, "a+b")  # noqa: SIM115 — closed in the finally below
    try:
        deadline = None if timeout_s is None else time.monotonic() + timeout_s
        told = False
        while not _try_lock(handle):
            if not told and on_wait is not None:
                on_wait(
                    f"another run of cycle {cycle!r} is using {folder}{_holder(path)}; "
                    "waiting for it to finish"
                )
                told = True
            if deadline is not None and time.monotonic() >= deadline:
                raise CycleLockTimeout(
                    f"another run of cycle {cycle!r} is still using {folder}{_holder(path)}"
                )
            time.sleep(_POLL_S)
        try:
            handle.seek(0)
            handle.truncate()
            handle.write(str(os.getpid()).encode())
            handle.flush()
            yield path
        finally:
            _unlock(handle)
    finally:
        handle.close()
