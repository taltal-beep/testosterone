"""Single entry point for running configured reporters after test execution."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from testo_core.config.schema import TestosteroneConfig
from testo_core.reporting.collector import CollectedResults, collect_results, collect_results_docker_run
from testo_core.reporting.reporters.base import ReportContext, ReportLayout
from testo_core.reporting.reporters.factory import ReporterFactory


def run_configured_reporters(
    *,
    cfg: TestosteroneConfig | None = None,
    config_reporters: tuple | None = None,
    artifacts_root: Path,
    plan_name: str | None = None,
    reporter_override: Sequence[str] | None = None,
    layout: ReportLayout = "cycle",
    run_id: str | None = None,
    console: object | None = None,
    ci: bool = False,
    generate_only: bool = True,
    inject_history: bool = True,
    trend_depth: int = 1,
    out_dir: Path | None = None,
) -> list:
    """Collect artifacts and run all active reporters. No-op when none configured."""
    reporters_tuple = config_reporters if config_reporters is not None else (
        cfg.reporters if cfg is not None else ()
    )
    if not reporters_tuple and not reporter_override:
        return []

    try:
        active_reporters = ReporterFactory.build(
            config_reporters=reporters_tuple,
            overrides=reporter_override,
        )
    except ValueError as exc:
        if console is not None:
            console.print(f"[fail]{exc}[/]")  # type: ignore[union-attr]
        return []

    if layout == "docker_run":
        results = collect_results_docker_run(artifacts_root, run_id=run_id)
    else:
        results = collect_results(artifacts_root, plan_name=plan_name)

    if not results.stages:
        if console is not None and not ci:
            console.print(  # type: ignore[union-attr]
                f"[muted]No Allure results under {artifacts_root}; skipping reporters.[/]"
            )
        return []

    context = ReportContext(
        artifacts_root=artifacts_root.expanduser().resolve(),
        plan_name=plan_name,
        layout=layout,
        run_id=run_id,
        ci=ci,
        generate_only=generate_only,
        inject_history=inject_history,
        trend_depth=trend_depth,
        out_dir=out_dir,
        open_browser=not ci and not generate_only,
    )

    outcomes = ReporterFactory.run_all(active_reporters, results=results, context=context, console=console)
    for outcome in outcomes:
        if console is None:
            continue
        if outcome.ok:
            console.print(f"[muted]Reporter:[/] {outcome.message}")  # type: ignore[union-attr]
        else:
            console.print(f"[warn]Reporter failed:[/] {outcome.message}")  # type: ignore[union-attr]
    return outcomes
