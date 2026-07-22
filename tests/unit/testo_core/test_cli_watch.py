"""Tests for ``testo watch``."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from testo_core.cli.app import app
from testo_core.cli.commands import watch as watch_mod
from testo_core.engine.exit_codes import EngineExitCode


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def test_watch_requires_cycle_option(runner: CliRunner) -> None:
    result = runner.invoke(app, ["watch"])
    assert result.exit_code != 0
    assert "cycle" in result.stdout.lower() or "cycle" in (result.stderr or "").lower()


def test_watch_invalid_path_exits_invalid_input(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["watch", "--cycle", "c", "--path", "does-not-exist"])
    assert result.exit_code == int(EngineExitCode.INVALID_INPUT)
    assert "not a directory" in result.stdout


@pytest.mark.parametrize(
    "path_parts,expected",
    [
        (("repo", "src", "main.py"), False),
        (("repo", ".git", "HEAD"), True),
        (("repo", "artifacts", "run.json"), True),
        (("repo", "sub", "__pycache__", "x.pyc"), True),
        (("repo", "node_modules", "x.js"), True),
    ],
)
def test_should_ignore(path_parts: tuple[str, ...], expected: bool) -> None:
    assert watch_mod._should_ignore(Path(*path_parts)) is expected


def test_watch_runs_observer_lifecycle_and_exits_zero(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Exercise ``watch()`` end-to-end with a fake, never-alive Observer so the loop exits immediately."""
    monkeypatch.chdir(tmp_path)

    calls: dict[str, int] = {"schedule": 0, "start": 0, "stop": 0, "join": 0}

    class _FakeObserver:
        def schedule(self, *_a: object, **_k: object) -> None:
            calls["schedule"] += 1

        def start(self) -> None:
            calls["start"] += 1

        def is_alive(self) -> bool:
            return False

        def stop(self) -> None:
            calls["stop"] += 1

        def join(self, timeout: float | None = None) -> None:  # noqa: ARG002
            calls["join"] += 1

    import watchdog.observers

    monkeypatch.setattr(watchdog.observers, "Observer", _FakeObserver)

    result = runner.invoke(app, ["watch", "--cycle", "c", "--path", str(tmp_path)])
    assert result.exit_code == 0, result.stdout
    assert calls == {"schedule": 1, "start": 1, "stop": 1, "join": 1}
