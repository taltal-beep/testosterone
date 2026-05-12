"""Tests for :class:`testo_core.frameworks.behavex_adapter.BehaveXAdapter`."""

from __future__ import annotations

from pathlib import Path

from testo_core.frameworks.behavex_adapter import BehaveXAdapter


def test_behavex_output_dir_is_sibling_of_allure_results(tmp_path: Path) -> None:
    """Native BehaveX ``-o`` must live under the stage root, not under ``allure-results/``."""
    adapter = BehaveXAdapter()
    target_repo = tmp_path / "repo"
    results_dir = tmp_path / "stage" / "allure-results" / "behavex"
    results_dir.mkdir(parents=True)
    argv = adapter.build_argv(
        target_repo=target_repo,
        results_dir=results_dir,
        stage_args=(),
        workers=2,
    )
    oi = argv.index("-o")
    out = Path(argv[oi + 1]).resolve()
    assert out == (tmp_path / "stage" / "behave_reports").resolve()
