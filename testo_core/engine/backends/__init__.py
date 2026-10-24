"""Where a stage's process runs: on this machine (default) or in a throwaway container.

``TESTO_RUNNER`` picks the backend:

- ``host`` (default): :class:`subprocess.Popen`, as always.
- ``container``: the runner service (``TESTO_RUNNER_URL``) starts the stage in a
  fresh container and streams its output back. Only the stage's own variables
  travel with it (``stage_env``: its ``env:`` block and what Testosterone and the
  adapter set), never this process's environment.
"""

from __future__ import annotations

import logging
import os
import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Literal, Protocol

from testo_core.engine.log_buffer import ByteReader

logger = logging.getLogger(__name__)

RUNNER_ENV = "TESTO_RUNNER"
RunnerKind = Literal["host", "container"]


class RunnerError(RuntimeError):
    """The runner service is not configured, unreachable, or refused the stage."""


class StageProcess(Protocol):
    """The part of :class:`subprocess.Popen` the executor uses."""

    @property
    def stdout(self) -> ByteReader | None: ...

    @property
    def returncode(self) -> int | None: ...

    def wait(self, timeout: float | None = None) -> int: ...

    def send_signal(self, sig: int) -> None: ...

    def terminate(self) -> None: ...

    def kill(self) -> None: ...


def runner_kind() -> RunnerKind:
    raw = (os.environ.get(RUNNER_ENV) or "host").strip().lower()
    if raw in ("host", "container"):
        return raw  # type: ignore[return-value]
    logger.warning("%s=%r is not 'host' or 'container'; using host", RUNNER_ENV, raw)
    return "host"


def launch(
    argv: Sequence[str],
    *,
    cwd: Path,
    env: Mapping[str, str],
    stage_env: Mapping[str, str],
) -> StageProcess:
    """Start a stage with stdout and stderr merged into one ``stdout`` stream."""
    if runner_kind() == "container":
        from testo_core.engine.backends.container import RemoteStageProcess

        return RemoteStageProcess(argv, cwd=str(cwd), env=stage_env)
    return subprocess.Popen(  # noqa: S603 - argv is built by trusted adapters
        list(argv),
        cwd=str(cwd),
        env=dict(env),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        bufsize=0,
        close_fds=True,
    )
