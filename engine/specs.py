from __future__ import annotations

from pathlib import Path
from typing import Mapping, Protocol

import pluggy

from engine.command_builders import RunConfig

hookspec = pluggy.HookspecMarker("uqo")
hookimpl = pluggy.HookimplMarker("uqo")


class BaseRunnerSpec(Protocol):
    """
    Pluggy hook specifications for UQO runner orchestration.

    Hooks are intentionally small and optional so the engine can run with the
    built-in plugin alone.
    """

    @hookspec(firstresult=True)
    def get_command(self, config: RunConfig) -> list[str] | None:
        """Return an argv to execute for this run, or None if not applicable."""

    @hookspec(firstresult=True)
    def setup_env(self, config: RunConfig) -> Mapping[str, str] | None:
        """Return env var overrides for this run, or None if not applicable."""

    @hookspec
    def collect_artifacts(self, run_id: str) -> list[Path] | None:
        """Return host paths to snapshot/upload for this run, if any."""
