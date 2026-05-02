"""Coverage for sandbox process termination paths."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

import uqo_core.sandbox_api as sa


def test_stop_sandbox_terminates_proc(monkeypatch: pytest.MonkeyPatch) -> None:
    proc = MagicMock()
    proc.poll.return_value = None
    proc.wait.return_value = 0
    monkeypatch.setattr(sa, "_PROC", proc)
    sa.stop_sandbox_if_managed()
    proc.terminate.assert_called_once()


def test_stop_sandbox_kills_on_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    proc = MagicMock()
    proc.poll.return_value = None

    class _Timeout(Exception):
        pass

    # Use the real TimeoutExpired type check in the module by raising it.
    def _wait(*_a, **_kw):
        raise sa.subprocess.TimeoutExpired(cmd="x", timeout=0)

    proc.wait.side_effect = _wait
    monkeypatch.setattr(sa, "_PROC", proc)
    sa.stop_sandbox_if_managed()
    proc.kill.assert_called_once()

