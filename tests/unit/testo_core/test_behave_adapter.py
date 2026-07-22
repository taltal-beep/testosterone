"""Tests for :class:`~testo_core.frameworks.behave_adapter.BehaveAdapter`."""

from __future__ import annotations

from pathlib import Path

from testo_core.frameworks.behave_adapter import BehaveAdapter


def test_behave_adapter_has_no_native_report(tmp_path: Path) -> None:
    assert BehaveAdapter().native_report(tmp_path) is None
