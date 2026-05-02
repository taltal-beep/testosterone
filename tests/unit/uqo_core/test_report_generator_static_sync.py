"""Coverage for static mirroring helpers in ``uqo_core.report_generator``."""

from __future__ import annotations

from pathlib import Path

import pytest

from uqo_core import report_generator as rg


def test_publish_allure_index_to_static_chmod_branch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Make report_dir == STATIC_ALLURE_REPORT_DIR
    static_dir = tmp_path / "static"
    report_dir = static_dir / "allure_report"
    report_dir.mkdir(parents=True)
    (report_dir / "index.html").write_text("<html/>", encoding="utf-8")

    monkeypatch.setattr(rg, "STATIC_DIR", static_dir)
    monkeypatch.setattr(rg, "STATIC_ALLURE_REPORT_DIR", report_dir)
    monkeypatch.setattr(rg, "STATIC_ALLURE_INDEX", report_dir / "index.html")

    out = rg.publish_allure_index_to_static(report_dir=report_dir)
    assert out is not None


def test_sync_all_reports_to_static_all_branches(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()

    static_dir = tmp_path / "static"
    allure_dir = static_dir / "allure_report"
    allure_dir.mkdir(parents=True)
    (allure_dir / "index.html").write_text("ok", encoding="utf-8")

    # Locust html
    (artifacts / "locust_report.html").write_text("<html/>", encoding="utf-8")

    # Behave reports dir
    behave_reports = artifacts / "behave_reports"
    behave_reports.mkdir(parents=True)
    (behave_reports / "report.html").write_text("<html/>", encoding="utf-8")

    monkeypatch.setattr(rg, "STATIC_DIR", static_dir)
    monkeypatch.setattr(rg, "STATIC_ALLURE_REPORT_DIR", allure_dir)
    monkeypatch.setattr(rg, "STATIC_ALLURE_INDEX", allure_dir / "index.html")
    monkeypatch.setattr(rg, "STATIC_BEHAVE_DIR", static_dir / "behave")
    monkeypatch.setattr(rg, "STATIC_BEHAVE_INDEX", static_dir / "behave" / "index.html")
    monkeypatch.setattr(rg, "STATIC_LOCUST_HTML", static_dir / "locust_report.html")

    out = rg.sync_all_reports_to_static(artifacts_root=artifacts, run_id="rid")
    assert out["allure"] is not None
    assert out["locust"] is not None
    assert out["behavex"] is not None

