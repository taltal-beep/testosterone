from __future__ import annotations

import os

from uqo_core.services.ui_mode import resolve_ui_mode


def test_dual_mode_flag_defaults_and_override(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.delenv("UQO_UI_MODE", raising=False)
    assert resolve_ui_mode(os.getenv("UQO_UI_MODE")) == "dual"

    monkeypatch.setenv("UQO_UI_MODE", "streamlit")
    assert resolve_ui_mode(os.getenv("UQO_UI_MODE")) == "streamlit"

    monkeypatch.setenv("UQO_UI_MODE", "react")
    assert resolve_ui_mode(os.getenv("UQO_UI_MODE")) == "react"
