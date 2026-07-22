"""
Built-in Pluggy hooks for the UQO orchestrator.

This module intentionally provides "no-op" default behavior so the engine can run
without any user drop-in plugins installed.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from testo_core.command_builders import RunConfig
from testo_core.specs import hookimpl


@hookimpl
def get_command(config: RunConfig) -> list[str] | None:  # pragma: no cover
    return None


@hookimpl
def setup_env(config: RunConfig) -> Mapping[str, str] | None:  # pragma: no cover
    return None


@hookimpl
def collect_artifacts(run_id: str) -> list[Path] | None:  # pragma: no cover
    return None
