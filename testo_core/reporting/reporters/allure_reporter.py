"""Allure HTML generation and optional local dashboard serve."""

from __future__ import annotations

from pathlib import Path

from testo_core.reporting.collector import CollectedResults
from testo_core.reporting.reporters.base import BaseReporter, ReportContext, ReporterResult


class AllureReporter(BaseReporter):
    @property
    def reporter_type(self) -> str:
        return "allure"

    def publish(
        self,
        *,
        results: CollectedResults,
        context: ReportContext,
        console: object | None = None,
    ) -> ReporterResult:
        if not results.stages:
            return ReporterResult(ok=False, message="no Allure result directories found.")

        out_dir = (
            context.out_dir
            or Path(self._options.get("out_dir", str(context.artifacts_root / "allure-report")))
        ).expanduser().resolve()

        if context.inject_history:
            from testo_core.reporting.history_inject import try_inject_prior_history

            try_inject_prior_history(
                artifacts_root=context.artifacts_root,
                plan_name=context.plan_name,
                console=console,
                enabled=True,
                trend_depth=context.trend_depth,
            )

        from testo_core.reporting.allure import AllureCLINotFoundError, generate_html

        try:
            outcome = generate_html(result_dirs=results.result_dirs, out_dir=out_dir)
        except AllureCLINotFoundError as exc:
            return ReporterResult(ok=False, message=str(exc))

        if not outcome.ok:
            return ReporterResult(ok=False, message=outcome.message)

        index_path = outcome.out_dir.resolve() / "index.html"
        if context.generate_only or context.ci or not context.open_browser:
            return ReporterResult(
                ok=True,
                message=f"Allure HTML at {index_path}",
                artifacts=(index_path,),
            )

        from testo_core.reporting.allure_cli import is_allure_available

        if not is_allure_available():
            return ReporterResult(
                ok=True,
                message=f"Allure HTML at {index_path} (Allure 3 CLI missing; cannot serve dashboard)",
                artifacts=(index_path,),
            )

        from testo_core.reporting.server import open_generated_report, resolve_serve_port

        serve_port = resolve_serve_port(context.host, context.port)
        if console is not None and serve_port != context.port:
            console.print(  # type: ignore[union-attr]
                f"[muted]Port {context.port} is in use; serving the dashboard on[/] [bold]{serve_port}[/] instead."
            )
        code = open_generated_report(report_dir=outcome.out_dir.resolve(), host=context.host, port=serve_port)
        if code == 127:
            return ReporterResult(
                ok=True,
                message=f"Allure HTML at {index_path} (allure serve not found)",
                artifacts=(index_path,),
            )
        if code not in (0, 130):
            return ReporterResult(ok=False, message=f"allure serve exited {code}")

        return ReporterResult(
            ok=True,
            message=f"Allure dashboard served from {index_path}",
            artifacts=(index_path,),
        )
