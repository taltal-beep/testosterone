"""Dispatcher for ``testo report`` — picks generate / serve / export."""

from __future__ import annotations

from pathlib import Path

from rich.console import Console

from testo_core.engine.exit_codes import EngineExitCode
from testo_core.reporting.collector import collect_results
from testo_core.reporting.exporter import write_json_summary, write_junit_xml


def dispatch_report(
    *,
    console: Console,
    artifacts_root: Path,
    plan_name: str | None,
    serve: bool,
    port: int,
    out_dir: Path,
    fmt: str,
    summary_out: Path | None,
) -> int:
    """Wire one ``testo report`` invocation to the right backend."""
    results = collect_results(artifacts_root, plan_name=plan_name)
    if not results.stages:
        console.print(
            f"[fail]no results found under {artifacts_root}[/] "
            f"— run `testo run --plan ...` first."
        )
        return int(EngineExitCode.INVALID_INPUT)

    fmt_normalised = fmt.lower().strip()
    if fmt_normalised in {"json", "junit"}:
        target = summary_out or (out_dir.parent / f"summary.{fmt_normalised}.{'json' if fmt_normalised == 'json' else 'xml'}")
        try:
            if fmt_normalised == "json":
                written = write_json_summary(results=results, out=target)
            else:
                written = write_junit_xml(results=results, out=target)
        except OSError as exc:
            console.print(f"[fail]failed to write {target}: {exc}[/]")
            return int(EngineExitCode.INFRA_FAILURE)
        console.print(f"[ok]wrote {fmt_normalised} summary to[/] {written}")
        return int(EngineExitCode.SUCCESS)

    if fmt_normalised != "html":
        console.print(f"[fail]unknown --format {fmt_normalised!r}[/]")
        return int(EngineExitCode.INVALID_INPUT)

    # HTML generation path → uses the Allure CLI when present.
    from testo_core.reporting.allure import (
        AllureCLINotFoundError,
        generate_html,
    )

    try:
        outcome = generate_html(result_dirs=results.result_dirs, out_dir=out_dir)
    except AllureCLINotFoundError as exc:
        console.print(f"[fail]{exc}[/]")
        return int(EngineExitCode.INFRA_FAILURE)

    if not outcome.ok:
        console.print(f"[fail]allure generate failed:[/] {outcome.message}")
        return int(EngineExitCode.INFRA_FAILURE)

    console.print(f"[ok]wrote Allure HTML to[/] {outcome.out_dir}")
    if serve:
        from testo_core.reporting.server import serve_report

        return int(serve_report(report_dir=outcome.out_dir, port=port) or 0)
    return int(EngineExitCode.SUCCESS)
