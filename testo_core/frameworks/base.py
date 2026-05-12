"""Framework adapter protocol + registry.

Adapters live in tiny modules so adding support for a new framework is a
single-file change with zero impact on the orchestrator.  The executor only
sees the protocol; framework-specific knobs stay encapsulated.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol


class FrameworkAdapter(Protocol):
    """Minimum surface required to schedule a stage."""

    name: str

    def results_subdir(self) -> str:
        """Subdirectory under ``<artifacts>/<plan>/<stage>/allure-results/``."""
        ...

    def build_argv(
        self,
        *,
        target_repo: Path,
        results_dir: Path,
        stage_args: tuple[str, ...],
        workers: int,
    ) -> list[str]:
        """Return the argv that should be passed to :class:`subprocess.Popen`."""
        ...


def get_adapter(framework: str) -> FrameworkAdapter:
    """Return the registered adapter for ``framework``.

    Imports are kept inside this function so adding a new framework cannot
    break ``testo --help`` import-time performance.
    """
    if framework == "pytest":
        from testo_core.frameworks.pytest_adapter import PytestAdapter

        return PytestAdapter()
    if framework == "behave":
        from testo_core.frameworks.behave_adapter import BehaveAdapter

        return BehaveAdapter()
    if framework == "behavex":
        from testo_core.frameworks.behavex_adapter import BehaveXAdapter

        return BehaveXAdapter()
    raise ValueError(f"Unsupported framework: {framework!r}")
