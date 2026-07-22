"""Immutable, framework-agnostic dataclasses for the cycle-aware config schema.

The CLI loader produces a :class:`TestosteroneConfig` by parsing YAML or the
``[tool.testosterone]`` table of ``pyproject.toml``.  Down-stream code (the
orchestrator, the report exporter, tests) consumes these objects directly and
never re-parses the source text.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


# Supported frameworks. Add new ones in :mod:`testo_core.frameworks` and append here.
SUPPORTED_FRAMEWORKS: frozenset[str] = frozenset({"pytest", "behave", "behavex"})

# Supported post-run reporters. Add new ones in :mod:`testo_core.reporting.reporters` and append here.
SUPPORTED_REPORTER_TYPES: frozenset[str] = frozenset({"allure", "extent", "reportportal", "testbeats"})


@dataclass(frozen=True)
class Defaults:
    """Repository-wide defaults inherited by every stage unless overridden."""

    target_repo: Path = Path(".")
    artifacts_root: Path = Path("artifacts")
    timeout_s: float | None = 600.0
    workers: int = 4
    extra_env: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class CycleTrigger:
    """Optional selective execution: run the cycle only when matched paths change.

    ``paths`` use pathlib-style globs relative to the config file directory (anchor).
    """

    paths: tuple[str, ...]
    since_ref: str | None = None  # e.g. ``origin/main`` → ``git diff since_ref...HEAD``


@dataclass(frozen=True)
class Stage:
    """One execution step in a plan.

    All path-typed fields are resolved against the config file's directory at
    load time so the orchestrator never has to know where the YAML lives.
    """

    name: str
    framework: str
    target_repo: Path
    args: tuple[str, ...] = ()
    workers: int = 4
    timeout_s: float | None = 600.0
    if_expr: str | None = None
    extra_env: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class ReporterSpec:
    """One post-run reporter entry from the top-level ``reporters:`` list."""

    type: str
    options: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class Plan:
    """A named sequence of stages executed in order by ``testo run --cycle <name>``."""

    name: str
    description: str | None
    stages: tuple[Stage, ...]
    trigger: CycleTrigger | None = None


@dataclass(frozen=True)
class TestosteroneConfig:
    """Top-level configuration object produced by the loader."""

    version: int
    defaults: Defaults
    cycles: dict[str, Plan] = field(default_factory=dict)
    reporters: tuple[ReporterSpec, ...] = ()
    source_path: Path | None = None

    @property
    def plans(self) -> dict[str, Plan]:
        """Backward-compatible alias for older call sites."""
        return self.cycles
