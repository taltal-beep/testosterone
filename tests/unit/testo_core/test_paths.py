"""Tests for ``testo_core.paths`` (layout + Allure input directory resolution)."""

from __future__ import annotations

from pathlib import Path

from testo_core.paths import (
    ALLURE_FRAMEWORK_RESULT_SUBDIRS,
    allure_cli_input_directories,
    allure_results_dir,
    default_artifacts_root,
)


def test_default_artifacts_root_is_relative() -> None:
    assert default_artifacts_root() == Path("artifacts")


def test_allure_results_dir_joins(tmp_path: Path) -> None:
    assert allure_results_dir(tmp_path) == tmp_path / "allure-results"


def test_allure_cli_input_directories_prefers_subdirs_when_any_exist(tmp_path: Path) -> None:
    root = tmp_path / "allure-results"
    root.mkdir()
    (root / "pytest").mkdir()
    d = allure_cli_input_directories(root)
    assert d == [root / "pytest"]


def test_allure_cli_input_directories_falls_back_to_parent(tmp_path: Path) -> None:
    root = tmp_path / "allure-results"
    root.mkdir()
    (root / "x-result.json").write_text("{}", encoding="utf-8")
    d = allure_cli_input_directories(root)
    assert d == [root]


def test_framework_subdir_names_triple() -> None:
    # Locust support has been removed; the framework subdir set is now
    # pytest / behave_native / behavex.
    assert len(ALLURE_FRAMEWORK_RESULT_SUBDIRS) == 3
    assert set(ALLURE_FRAMEWORK_RESULT_SUBDIRS) == {"pytest", "behave_native", "behavex"}
