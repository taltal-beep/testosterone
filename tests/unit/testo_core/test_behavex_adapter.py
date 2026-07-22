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


def test_native_report_present_when_report_html_exists(tmp_path: Path) -> None:
    stage_dir = tmp_path / "stage"
    reports_dir = stage_dir / "behave_reports"
    reports_dir.mkdir(parents=True)
    (reports_dir / "report.html").write_text("<html></html>", encoding="utf-8")

    native = BehaveXAdapter().native_report(stage_dir)

    assert native is not None
    assert native.root_dir == reports_dir
    assert native.entry_relpath == "report.html"


def test_native_report_none_when_report_html_missing(tmp_path: Path) -> None:
    stage_dir = tmp_path / "stage"
    (stage_dir / "behave_reports").mkdir(parents=True)

    assert BehaveXAdapter().native_report(stage_dir) is None
