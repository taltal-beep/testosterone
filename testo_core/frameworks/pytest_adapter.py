"""Pytest adapter — emits ``--alluredir`` pointing at the per-stage tree."""

from __future__ import annotations

from pathlib import Path


class PytestAdapter:
    name: str = "pytest"

    def results_subdir(self) -> str:
        return "pytest"

    def build_argv(
        self,
        *,
        target_repo: Path,
        results_dir: Path,
        stage_args: tuple[str, ...],
        workers: int,
    ) -> list[str]:
        del target_repo, workers  # unused by pytest argv
        argv: list[str] = ["pytest"]
        argv.extend(stage_args)
        argv.extend(["--alluredir", str(results_dir.resolve())])
        return argv
