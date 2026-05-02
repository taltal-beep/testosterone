"""More coverage for ``uqo_core.sandbox_api`` (mocked subprocess + requests)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from uqo_core import sandbox_api as sa


def test_is_mock_api_responding_true(monkeypatch: pytest.MonkeyPatch) -> None:
    class _R:
        status_code = 200

    class _Req:
        @staticmethod
        def get(*_a, **_kw):
            return _R()

    monkeypatch.setitem(__import__("sys").modules, "requests", _Req())
    assert sa.is_mock_api_responding(timeout_s=0.01) is True


def test_start_sandbox_if_needed_already_running(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sa, "is_mock_api_responding", lambda **_: True)
    ok, msg = sa.start_sandbox_if_needed()
    assert ok is True
    assert "already running" in msg.lower()


def test_start_sandbox_if_needed_missing_file(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.setattr(sa, "is_mock_api_responding", lambda **_: False)
    monkeypatch.setattr(sa, "sample_target_repo", lambda: tmp_path)
    ok, msg = sa.start_sandbox_if_needed()
    assert ok is False
    assert "Missing" in msg


def test_stop_sandbox_if_managed_noop() -> None:
    # should not raise when no process is managed
    sa.stop_sandbox_if_managed()


def test_start_sandbox_if_needed_port_in_use(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    (tmp_path / "mock_api.py").write_text("x=1", encoding="utf-8")
    monkeypatch.setattr(sa, "sample_target_repo", lambda: tmp_path)
    monkeypatch.setattr(sa, "is_mock_api_responding", lambda **_: False)
    monkeypatch.setattr(sa, "_port_in_use", lambda *_a, **_kw: True)
    ok, msg = sa.start_sandbox_if_needed()
    assert ok is False
    assert "Port" in msg

