"""Tests for ``uqo_core.runners`` helpers."""

from __future__ import annotations

from pathlib import Path

from uqo_core.command_builders import RunConfig, TestType, build_command
from unittest.mock import patch

from uqo_core.runners import run_native_behave, validate_target_repo


def test_validate_target_repo_rejects_missing(tmp_path: Path) -> None:
    ok, msg = validate_target_repo(tmp_path / "missing")
    assert ok is False


def test_validate_target_repo_accepts_dir(tmp_path: Path) -> None:
    ok, msg = validate_target_repo(tmp_path)
    assert ok is True and msg == "OK"


def test_build_command_sets_allure_env(tmp_path: Path) -> None:
    cfg = RunConfig(
        test_type=TestType.PYTEST,
        target_repo=tmp_path,
        shared_allure_results_dir=tmp_path / "allure-results",
        pytest_args=("-q",),
    )
    bc = build_command(cfg, parent_env={})
    assert "pytest" in bc.argv[0] or bc.argv[0].endswith("pytest")
    assert "--alluredir" in bc.argv
    assert "UQO_SHARED_ALLURE_RESULTS_DIR" in bc.env


def test_run_native_behave_builds_expected_cli(tmp_path: Path) -> None:
    captured: dict[str, object] = {}

    def fake_docker_run(**kwargs):  # type: ignore[no-untyped-def]
        captured.update(kwargs)
        kwargs["emit"]("stdout", "done\n")
        return 0, 1.0, 2.0

    with patch("uqo_core.runners._run_in_ephemeral_container_streaming", side_effect=fake_docker_run) as run:

        (tmp_path / "features").mkdir()
        gen = run_native_behave(target_repo=tmp_path, artifacts_root=tmp_path / "artifacts")
        while True:
            try:
                next(gen)
            except StopIteration as e:
                rr = e.value
                break

    assert rr is not None
    run.assert_called_once()
    cmd = run.call_args.kwargs["cmd"]
    argv = cmd.argv
    assert any(str(a).endswith("behave") or str(a) == "behave" for a in argv)
    assert "-f" in argv and "allure_behave.formatter:AllureFormatter" in argv
    assert "-o" in argv
    out_dir = (tmp_path / "artifacts" / "allure-results" / "behave_native").resolve()
    assert str(out_dir) in argv


def test_run_native_behave_skips_when_missing_features(tmp_path: Path) -> None:
    with patch("uqo_core.runners._run_in_ephemeral_container_streaming") as run:
        gen = run_native_behave(target_repo=tmp_path, artifacts_root=tmp_path / "artifacts")
        ev = next(gen)
        assert "skipping" in ev.line
        try:
            while True:
                next(gen)
        except StopIteration as e:
            rr = e.value
    run.assert_not_called()
    assert rr is not None
    assert rr.returncode == 0


def test_run_native_behave_timeout_returns_124(tmp_path: Path) -> None:
    (tmp_path / "features").mkdir()

    def fake_docker_run(**_kwargs):  # type: ignore[no-untyped-def]
        return 124, 1.0, 2.0

    with patch("uqo_core.runners._run_in_ephemeral_container_streaming", side_effect=fake_docker_run):
        gen = run_native_behave(target_repo=tmp_path, artifacts_root=tmp_path / "artifacts")
        while True:
            try:
                next(gen)
            except StopIteration as e:
                rr = e.value
                break
    assert rr is not None
    assert rr.returncode == 124
