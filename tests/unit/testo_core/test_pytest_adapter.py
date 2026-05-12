"""Tests for :class:`~testo_core.frameworks.pytest_adapter.PytestAdapter`."""

from __future__ import annotations

from pathlib import Path

from testo_core.frameworks.pytest_adapter import PytestAdapter


def test_pytest_adapter_injects_config_when_target_has_pytest_ini(tmp_path: Path) -> None:
    repo = tmp_path / "target"
    repo.mkdir()
    (repo / "pytest.ini").write_text("[pytest]\npythonpath = .\n", encoding="utf-8")
    ad = PytestAdapter()
    argv = ad.build_argv(
        target_repo=repo,
        results_dir=tmp_path / "out",
        stage_args=("-q", "tests"),
        workers=4,
    )
    assert argv[0] == "pytest"
    assert argv[1] == "-c"
    assert argv[2] == str((repo / "pytest.ini").resolve())


def test_pytest_adapter_skips_inject_when_user_passes_c(tmp_path: Path) -> None:
    repo = tmp_path / "target"
    repo.mkdir()
    (repo / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
    ad = PytestAdapter()
    argv = ad.build_argv(
        target_repo=repo,
        results_dir=tmp_path / "out",
        stage_args=("-c", "/other/pytest.ini", "-q"),
        workers=4,
    )
    assert argv[1:3] == ["-c", "/other/pytest.ini"]
