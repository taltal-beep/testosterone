"""Tests for service façades."""

from __future__ import annotations

from pathlib import Path

from uqo_core.services.metrics_service import MetricsService
from uqo_core.services.report_service import ReportService


def test_report_service_paths(tmp_path: Path) -> None:
    svc = ReportService(artifacts_root=tmp_path)
    p = svc.report_paths()
    assert p.results_dir == tmp_path / "allure-results"


def test_report_service_static_flags() -> None:
    has_a, has_l = ReportService.static_reports_ready()
    assert isinstance(has_a, bool)
    assert isinstance(has_l, bool)


def test_metrics_service_parse_empty_tree(tmp_path: Path) -> None:
    (tmp_path / "allure-results").mkdir(parents=True)
    m = MetricsService.parse_allure_results_dir(tmp_path / "allure-results")
    assert m.total_tests == 0
