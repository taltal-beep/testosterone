from __future__ import annotations

from typing import Literal

UIMode = Literal["streamlit", "react", "dual"]
SUPPORTED_UI_MODES: tuple[UIMode, ...] = ("streamlit", "react", "dual")


def resolve_ui_mode(raw_mode: str | None) -> UIMode:
    candidate = (raw_mode or "dual").strip().lower()
    if candidate in SUPPORTED_UI_MODES:
        return candidate  # type: ignore[return-value]
    return "dual"
