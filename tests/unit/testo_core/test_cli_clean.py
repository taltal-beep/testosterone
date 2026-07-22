"""Tests for ``testo clean``."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from testo_core.cli.app import app
from testo_core.engine.exit_codes import EngineExitCode


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def test_clean_refuses_without_yes(runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["clean"])
    assert result.exit_code == int(EngineExitCode.INVALID_INPUT)
    assert "Refusing to delete without --yes" in result.stdout


def test_clean_removes_artifacts_and_temp(runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    cfg = tmp_path / "testosterone.yaml"
    cfg.write_text(
        "version: 1\ndefaults: {target_repo: ., artifacts_root: artifacts}\n"
        "cycles:\n  c:\n    stages:\n      - {name: s, equipment: pytest, args: ['-q']}\n",
        encoding="utf-8",
    )
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    (artifacts / "marker.txt").write_text("x", encoding="utf-8")
    temp = tmp_path / "temp"
    temp.mkdir()

    result = runner.invoke(app, ["clean", "--yes", "--config", str(cfg)])
    assert result.exit_code == 0, result.stdout
    assert not artifacts.exists()
    assert not temp.exists()
    assert "Clean finished" in result.stdout


def test_clean_with_missing_config_falls_back_to_default_artifacts(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()

    result = runner.invoke(app, ["clean", "--yes"])
    assert result.exit_code == 0, result.stdout
    assert "Could not load config" in result.stdout
    assert not artifacts.exists()


def test_clean_reports_nothing_to_remove(runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["clean", "--yes"])
    assert result.exit_code == 0, result.stdout
    assert "No matching artifact/temp directories found" in result.stdout


def test_clean_docker_prune_missing_cli_warns_but_succeeds(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    from testo_core.cli import cleanup as cleanup_mod

    monkeypatch.setattr(cleanup_mod, "docker_prune_stopped_with_label", lambda: (127, "docker: command not found"))
    result = runner.invoke(app, ["clean", "--yes", "--docker"])
    assert result.exit_code == 0, result.stdout
    assert "docker CLI not found" in result.stdout


def test_clean_docker_prune_failure_exits_infra_failure(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    from testo_core.cli import cleanup as cleanup_mod

    monkeypatch.setattr(cleanup_mod, "docker_prune_stopped_with_label", lambda: (1, "boom"))
    result = runner.invoke(app, ["clean", "--yes", "--docker"])
    assert result.exit_code == int(EngineExitCode.INFRA_FAILURE)
    assert "docker prune exited 1" in result.stdout
