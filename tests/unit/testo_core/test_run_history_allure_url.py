"""Tests for hosted Allure report URL helpers."""

from __future__ import annotations

import pytest


def test_allure_report_url_for_run(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALLURE_SERVER_URL", "http://localhost:5050")
    from testo_core.run_history import allure_report_url_for_run

    assert (
        allure_report_url_for_run("abc-123") == "http://localhost:5050/reports/abc-123/index.html"
    )
