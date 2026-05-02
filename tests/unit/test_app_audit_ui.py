"""Regression coverage for the Streamlit execution controls."""

from __future__ import annotations

import importlib
import sys
from types import SimpleNamespace
from typing import Any

import pytest


class _SessionState(dict):
    def __getattr__(self, name: str) -> Any:
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc

    def __setattr__(self, name: str, value: Any) -> None:
        self[name] = value


class _Context:
    def __enter__(self) -> "_Context":
        return self

    def __exit__(self, *_exc: object) -> None:
        return None

    def metric(self, *_args: Any, **_kwargs: Any) -> None:
        return None


class _FakeStreamlit:
    def __init__(self, *, clicked_labels: set[str] | None = None) -> None:
        self.session_state = _SessionState()
        self.context = SimpleNamespace(url="http://localhost:8501/")
        self.clicked_labels = clicked_labels or set()
        self.button_labels: list[str] = []

    def button(self, label: str, *_args: Any, **_kwargs: Any) -> bool:
        self.button_labels.append(label)
        return label in self.clicked_labels

    def columns(self, spec: int | list[int], *_args: Any, **_kwargs: Any) -> list[_Context]:
        count = spec if isinstance(spec, int) else len(spec)
        return [_Context() for _ in range(count)]

    def tabs(self, labels: list[str], *_args: Any, **_kwargs: Any) -> list[_Context]:
        return [_Context() for _ in labels]

    def container(self, *_args: Any, **_kwargs: Any) -> _Context:
        return _Context()

    def expander(self, *_args: Any, **_kwargs: Any) -> _Context:
        return _Context()

    def status(self, *_args: Any, **_kwargs: Any) -> _Context:
        return _Context()

    def spinner(self, *_args: Any, **_kwargs: Any) -> _Context:
        return _Context()

    def set_page_config(self, *_args: Any, **_kwargs: Any) -> None:
        return None

    def get_option(self, name: str) -> Any:
        return {"server.address": "localhost", "server.port": 8501}.get(name)

    def checkbox(self, label: str, *_args: Any, key: str | None = None, **_kwargs: Any) -> bool:
        value = bool(self.session_state.get(key, False)) if key else False
        if key:
            self.session_state[key] = value
        return value

    def toggle(self, label: str, *_args: Any, key: str | None = None, **_kwargs: Any) -> bool:
        return self.checkbox(label, key=key)

    def text_input(self, _label: str, *_args: Any, value: str = "", key: str | None = None, **_kwargs: Any) -> str:
        if key:
            self.session_state[key] = self.session_state.get(key, value)
            return str(self.session_state[key])
        return str(value)

    def text_area(self, _label: str, *_args: Any, value: str = "", key: str | None = None, **_kwargs: Any) -> str:
        if key:
            self.session_state[key] = self.session_state.get(key, value)
            return str(self.session_state[key])
        return str(value)

    def number_input(self, _label: str, *_args: Any, value: int = 0, key: str | None = None, **_kwargs: Any) -> int:
        if key:
            self.session_state[key] = self.session_state.get(key, value)
            return int(self.session_state[key])
        return int(value)

    def slider(self, _label: str, *_args: Any, value: int = 0, key: str | None = None, **_kwargs: Any) -> int:
        if key:
            self.session_state[key] = self.session_state.get(key, value)
            return int(self.session_state[key])
        return int(value)

    def selectbox(self, _label: str, options: list[str], *_args: Any, index: int = 0, **_kwargs: Any) -> str:
        return options[index]

    def file_uploader(self, *_args: Any, **_kwargs: Any) -> None:
        return None

    def download_button(self, *_args: Any, **_kwargs: Any) -> bool:
        return False

    def link_button(self, *_args: Any, **_kwargs: Any) -> bool:
        return False

    def image(self, *_args: Any, **_kwargs: Any) -> None:
        return None

    def dataframe(self, *_args: Any, **_kwargs: Any) -> None:
        return None

    def rerun(self) -> None:
        raise AssertionError("rerun should not be triggered while rendering this regression test")

    def __getattr__(self, _name: str):
        def _noop(*_args: Any, **_kwargs: Any) -> None:
            return None

        return _noop


def _import_app_with_fake_streamlit(monkeypatch: pytest.MonkeyPatch, fake_st: _FakeStreamlit):
    sys.modules.pop("app", None)
    monkeypatch.setitem(sys.modules, "streamlit", fake_st)
    monkeypatch.setattr("engine.runners.validate_target_repo", lambda _path: (True, "ok"))
    monkeypatch.setattr("engine.sandbox_api.is_managed_process_alive", lambda: False)
    monkeypatch.setattr("engine.services.report_service.ReportService.static_reports_ready", lambda: (False, False))
    monkeypatch.setattr("engine.services.report_service.ReportService.available_allure_reports", lambda: [])
    monkeypatch.setattr("engine.metrics.list_run_history", lambda *args, **kwargs: [])
    monkeypatch.setattr("engine.run_history.list_run_sessions", lambda *args, **kwargs: [])
    monkeypatch.setattr("engine.run_history.get_run", lambda *args, **kwargs: None)
    monkeypatch.setattr("engine.run_history.cleanup_orphaned_runs", lambda: None)

    app = importlib.import_module("app")
    return app


def test_removed_full_system_audit_control_is_not_rendered_or_dispatched(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_st = _FakeStreamlit(clicked_labels={"Run full system audit"})

    app = _import_app_with_fake_streamlit(monkeypatch, fake_st)
    monkeypatch.setattr(app.AuditService, "stream_audit", lambda *args, **kwargs: pytest.fail("audit should not run"))

    assert "Run full system audit" not in fake_st.button_labels
    assert fake_st.session_state.get("is_audit_mode") is False
    assert fake_st.session_state.get("running") is False
