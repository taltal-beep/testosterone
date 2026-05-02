"""Coverage for Locust static publishing helper."""

from __future__ import annotations

from pathlib import Path

from uqo_core import report_generator as rg


def test_publish_locust_html_to_static(tmp_path: Path, monkeypatch) -> None:
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    (artifacts / "locust_report.html").write_text("<html/>", encoding="utf-8")

    static_dir = tmp_path / "static"
    monkeypatch.setattr(rg, "STATIC_DIR", static_dir)
    monkeypatch.setattr(rg, "STATIC_LOCUST_HTML", static_dir / "locust_report.html")

    out = rg.publish_locust_html_to_static(artifacts_root=artifacts)
    assert out is not None
    assert out.is_file()

