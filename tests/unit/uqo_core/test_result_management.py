"""Tests for ``prepare_allure_results_dir`` (clear / archive)."""

from __future__ import annotations

from pathlib import Path

from uqo_core.result_management import prepare_allure_results_dir


def test_prepare_clear(tmp_path: Path) -> None:
    d = tmp_path / "allure-results"
    d.mkdir()
    (d / "x.json").write_text("{}", encoding="utf-8")
    r = prepare_allure_results_dir(d, mode="clear")
    assert r.shared_dir.is_dir()
    assert not (r.shared_dir / "x.json").exists()


def test_prepare_archive_moves_old(tmp_path: Path) -> None:
    d = tmp_path / "allure-results"
    d.mkdir()
    (d / "z.json").write_text("{}", encoding="utf-8")
    archive_root = tmp_path / "archive"
    r = prepare_allure_results_dir(d, mode="archive", archive_root=archive_root, run_id="rid")
    assert r.archived_to is not None
    assert (r.archived_to / "z.json").is_file()
    assert r.shared_dir.is_dir() and not (r.shared_dir / "z.json").exists()
