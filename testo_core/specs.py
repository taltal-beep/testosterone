from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Protocol

try:
    import pluggy  # type: ignore
except ModuleNotFoundError:  # pragma: no cover
    pluggy = None  # type: ignore[assignment]

from testo_core.command_builders import RunConfig

if pluggy is not None:
    hookspec = pluggy.HookspecMarker("uqo")
    hookimpl = pluggy.HookimplMarker("uqo")
else:  # pragma: no cover
    def _noop_marker(*args, **kwargs):  # type: ignore[no-redef]
        def _decorator(fn):
            return fn

        return _decorator

    hookspec = _noop_marker
    hookimpl = _noop_marker


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
