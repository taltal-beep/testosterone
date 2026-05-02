"""
Service: Allure HTML generation, report path resolution, and static mirror readiness checks.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from uqo_core.paths import (
    STATIC_ALLURE_HTML,
    STATIC_ALLURE_INDEX,
    STATIC_ALLURE_REPORTS_DIR,
    STATIC_LOCUST_HTML,
    allure_report_dir,
)
from uqo_core.paths import default_artifacts_root as paths_default_artifacts_root
from uqo_core.report_generator import (
    ReportPaths,
    default_report_paths,
    generate_allure_html as _generate_allure_html,
    generate_allure_reports as _generate_allure_reports,
    make_report_zip,
    read_single_file_html,
)


class ReportService:
    """
    Framework-agnostic façade over report generation and filesystem checks.

    ``artifacts_root`` defaults to :func:`uqo_core.paths.default_artifacts_root` when omitted.
    """

    def __init__(self, artifacts_root: Path | None = None) -> None:
        self._artifacts_root = (
            (artifacts_root or paths_default_artifacts_root()).expanduser().resolve()
        )

    @property
    def artifacts_root(self) -> Path:
        return self._artifacts_root

    def report_paths(self) -> ReportPaths:
        """Resolved Allure results dir, HTML output dir, and zip path."""
        return default_report_paths(artifacts_root=self._artifacts_root)

    def generate_allure_html(
        self,
        *,
        subprocess_run: Callable[..., Any] | None = None,
    ) -> tuple[bool, str, float | None]:
        paths = self.report_paths()
        return _generate_allure_html(
            results_dir=paths.results_dir,
            report_dir=paths.report_dir,
            subprocess_run=subprocess_run,
        )

    def generate_individual_allure(
        self,
        *,
        frameworks: list[str] | None = None,
        subprocess_run: Callable[..., Any] | None = None,
    ) -> dict[str, tuple[bool, str, float | None]]:
        paths = self.report_paths()
        return _generate_allure_reports(
            results_dir=paths.results_dir,
            frameworks=frameworks,
            subprocess_run=subprocess_run,
        )

    def generate_framework_reports(
        self,
        *,
        subprocess_run: Callable[..., Any] | None = None,
    ) -> dict[str, tuple[bool, str, float | None]]:
        """Generate isolated Allure HTML for Allure-producing frameworks (Locust is native HTML)."""
        return self.generate_individual_allure(
            frameworks=["pytest", "behavex", "behave_native"],
            subprocess_run=subprocess_run,
        )

    @staticmethod
    def available_allure_reports() -> list[str]:
        """Framework names with generated HTML under ``static/allure_reports/<fw>/index.html``."""
        if not STATIC_ALLURE_REPORTS_DIR.is_dir():
            return []
        out: list[str] = []
        for p in sorted([d for d in STATIC_ALLURE_REPORTS_DIR.iterdir() if d.is_dir()]):
            # Legacy/unsupported: never surface a unified master report in the UI.
            if p.name == "unified":
                continue
            if (p / "index.html").is_file():
                out.append(p.name)
        return out

    def make_report_zip(self, *, base_name: str = "allure-report") -> Path:
        paths = self.report_paths()
        return make_report_zip(report_dir=paths.report_dir, out_dir=self._artifacts_root, base_name=base_name)

    def read_single_file_html(self) -> tuple[bool, str, bytes | None]:
        paths = self.report_paths()
        return read_single_file_html(report_dir=paths.report_dir)

    @staticmethod
    def static_reports_ready() -> tuple[bool, bool]:
        """
        Returns ``(has_allure_static, has_locust_static)`` for mirrored HTML under ``static/``.
        """
        has_allure = False
        if STATIC_ALLURE_REPORTS_DIR.is_dir():
            has_allure = any((d / "index.html").is_file() for d in STATIC_ALLURE_REPORTS_DIR.iterdir() if d.is_dir())
        has_allure = has_allure or STATIC_ALLURE_INDEX.is_file() or STATIC_ALLURE_HTML.is_file()
        has_locust = STATIC_LOCUST_HTML.is_file()
        return has_allure, has_locust
