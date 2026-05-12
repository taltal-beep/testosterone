"""``testo report`` — generate / serve / export a report from the latest run.

The run path emits raw ``allure-results/`` only; HTML rendering and any UI is
performed by this command on demand.  See [Phase 3 plan](../../../.cursor/plans).
"""

from __future__ import annotations

from pathlib import Path

import typer


def report(
    artifacts_root: Path = typer.Option(
        Path("artifacts"),
        "--artifacts",
        "-a",
        help="Artifacts root that holds the per-stage allure-results.",
    ),
    plan: str = typer.Option(
        None,
        "--plan",
        "-p",
        help="Restrict the report to one plan's artifacts.",
    ),
    serve: bool = typer.Option(False, "--serve", help="Start a local HTTP server for the report."),
    port: int = typer.Option(8080, "--port", help="Port to bind the report server."),
    out: Path = typer.Option(
        Path("artifacts/report"),
        "--out",
        "-o",
        help="Where to write the generated HTML report.",
    ),
    fmt: str = typer.Option(
        "html",
        "--format",
        "-f",
        help="Output format: html (default), json, or junit.",
    ),
    summary_out: Path = typer.Option(
        None,
        "--summary-out",
        help="When --format=json|junit, file path to write the machine-readable summary to.",
    ),
) -> None:
    """Generate / serve / export a report from a previous ``testo run``."""
    from testo_core.cli.ui.console import default_console
    from testo_core.reporting.entry import dispatch_report

    console = default_console()
    exit_code = dispatch_report(
        console=console,
        artifacts_root=artifacts_root,
        plan_name=plan,
        serve=serve,
        port=port,
        out_dir=out,
        fmt=fmt,
        summary_out=summary_out,
    )
    raise typer.Exit(code=int(exit_code))
