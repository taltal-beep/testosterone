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


def test_pytest_adapter_has_no_native_report(tmp_path: Path) -> None:
    assert PytestAdapter().native_report(tmp_path) is None


def test_pytest_adapter_passes_alluredir_as_one_token(tmp_path: Path) -> None:
    argv = PytestAdapter().build_argv(
        target_repo=tmp_path,
        results_dir=tmp_path / "out",
        stage_args=("-q",),
        workers=1,
    )
    assert argv[-1] == f"--alluredir={(tmp_path / 'out').resolve()}"


def test_target_inside_another_pytest_project_keeps_its_own_rootdir(tmp_path: Path) -> None:
    """A target nested in a project with its own ``pytest.ini`` (testosterone's
    checkout, in CI) must still use its own config. Before the fix, the results
    path pulled pytest's rootdir up to the outer project and the target's
    ``pythonpath`` was ignored, so every import of the target's package failed.
    """
    import subprocess
    import sys

    outer = tmp_path / "outer"
    target = outer / ".demo" / "app"
    (target / "pkg").mkdir(parents=True)
    (target / "tests").mkdir()
    (outer / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
    (target / "pyproject.toml").write_text(
        '[tool.pytest.ini_options]\npythonpath = ["."]\n', encoding="utf-8"
    )
    (target / "pkg" / "__init__.py").write_text("VALUE = 1\n", encoding="utf-8")
    (target / "tests" / "test_pkg.py").write_text(
        "from pkg import VALUE\n\n\ndef test_value():\n    assert VALUE == 1\n", encoding="utf-8"
    )

    # The engine creates the results directory before the stage runs; only an
    # existing path can move pytest's rootdir.
    results = outer / "artifacts" / "stage" / "allure-results"
    results.mkdir(parents=True)

    argv = PytestAdapter().build_argv(
        target_repo=target,
        results_dir=results,
        stage_args=("-q", "-p", "no:cacheprovider", "tests"),
        workers=1,
    )
    # Run the console script as the engine does: ``python -m pytest`` would put
    # the cwd on sys.path and hide a wrong rootdir.
    pytest_bin = Path(sys.executable).with_name("pytest")
    proc = subprocess.run(
        [str(pytest_bin), *argv[1:]], cwd=target, capture_output=True, text=True, timeout=60
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
