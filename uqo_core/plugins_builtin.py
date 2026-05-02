from __future__ import annotations

"""
Built-in Pluggy hooks for the UQO orchestrator.

This module intentionally provides "no-op" default behavior so the engine can run
without any user drop-in plugins installed.
"""

from pathlib import Path
from typing import Mapping

from uqo_core.command_builders import RunConfig
from uqo_core.specs import hookimpl


@hookimpl
def get_command(config: RunConfig) -> list[str] | None:  # pragma: no cover
    return None


@hookimpl
def setup_env(config: RunConfig) -> Mapping[str, str] | None:  # pragma: no cover
    return None


@hookimpl
def collect_artifacts(run_id: str) -> list[Path] | None:  # pragma: no cover
    return None
