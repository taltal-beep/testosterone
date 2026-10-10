"""Coverage for small defaults and placeholder runners."""

from __future__ import annotations

from pathlib import Path

from testo_core.reporting.report_generator import ReportServer, default_report_paths, url_for


def test_default_report_paths_points_to_static(tmp_path: Path) -> None:
    p = default_report_paths(artifacts_root=tmp_path)
    assert p.results_dir == tmp_path / "allure-results"
    # output is always the static allure dir (not under artifacts)
    assert "static" in str(p.report_dir)


def test_url_for_formats_relative_path(tmp_path: Path) -> None:
    # Minimal ReportServer stub
    srv = ReportServer(port=1234, root_dir=tmp_path, thread=None, httpd=None)  # type: ignore[arg-type]
    u = url_for(srv, relative_path="/x/y.html")
    assert u.endswith("/x/y.html")
