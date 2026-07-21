"""ExtentReports-style local HTML dashboard (Jinja2, dark theme)."""

from __future__ import annotations

from pathlib import Path

from testo_core.reporting.allure_results import parse_collected_results
from testo_core.reporting.collector import CollectedResults
from testo_core.reporting.exporter import write_json_summary
from testo_core.reporting.reporters.base import BaseReporter, ReportContext, ReporterResult
from testo_core.reporting.reporters.extent_builder import render_dashboard


class ExtentReporter(BaseReporter):
    @property
    def reporter_type(self) -> str:
        return "extent"

    def publish(
        self,
        *,
        results: CollectedResults,
        context: ReportContext,
        console: object | None = None,
    ) -> ReporterResult:
        if not results.stages:
            return ReporterResult(ok=False, message="no results to export for Extent report.")

        output_dir = Path(
            self._options.get("output_dir")
            or str(context.artifacts_root / "reports" / "extent")
        ).expanduser().resolve()
        output_dir.mkdir(parents=True, exist_ok=True)

        aggregate = parse_collected_results(results)
        summary_path = output_dir / "summary.json"
        write_json_summary(results=results, out=summary_path)

        try:
            index_path = render_dashboard(aggregate, context=context, output_dir=output_dir)
        except Exception as exc:
            return ReporterResult(ok=False, message=f"Extent dashboard render failed: {exc}")

        msg = f"Extent report at {index_path}"
        if console is not None:
            console.print(f"[ok]{msg}[/]")  # type: ignore[union-attr]
        return ReporterResult(ok=True, message=msg, artifacts=(index_path, summary_path))
