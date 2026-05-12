"""``testo diff`` and ``testo summary`` — compare archived report runs."""

from __future__ import annotations

import tempfile
from pathlib import Path

import typer

from testo_core.engine.exit_codes import EngineExitCode


def _render_diff(
    *,
    console,
    baseline,
    current,
    metrics_only: bool,
) -> None:
    from testo_core.cli.ui.summary_dashboard import render_full_diff
    from testo_core.services.report_archive_diff import diff_archives

    if metrics_only:
        render_full_diff(
            console,
            baseline=baseline,
            current=current,
            changes=[],
            metrics_only=True,
        )
        return

    with tempfile.TemporaryDirectory(prefix="testo-diff-") as td:
        changes, _meta = diff_archives(baseline=baseline, current=current, tmp=Path(td))

    render_full_diff(
        console,
        baseline=baseline,
        current=current,
        changes=changes,
        metrics_only=False,
    )


def diff_reports(
    baseline_id: str = typer.Argument(
        ...,
        metavar="BASELINE_ID",
        help="Older archived run UUID (``testo report list`` id column).",
    ),
    current_id: str = typer.Argument(
        ...,
        metavar="CURRENT_ID",
        help="Newer archived run UUID.",
    ),
    metrics_only: bool = typer.Option(
        False,
        "--metrics-only",
        help="Show only denormalized DB columns (no per-test Allure diff).",
    ),
) -> None:
    """Compare two ``ReportArchive`` rows (regressions, fixes, duration deltas)."""
    from testo_core.cli.ui.console import default_console
    from testo_core.db import get_report_archive_repository
    from testo_core.services.report_archive_diff import parse_archive_uuid

    console = default_console()
    bid = parse_archive_uuid(baseline_id)
    cid = parse_archive_uuid(current_id)
    if bid is None or cid is None:
        console.print("[fail]Each argument must be a valid report archive UUID.[/]")
        raise typer.Exit(code=int(EngineExitCode.INVALID_INPUT))

    repo = get_report_archive_repository()
    base = repo.get(bid)
    cur = repo.get(cid)
    if base is None or cur is None:
        console.print("[fail]One or both archive ids were not found in the database.[/]")
        raise typer.Exit(code=int(EngineExitCode.INVALID_INPUT))

    _render_diff(console=console, baseline=base, current=cur, metrics_only=metrics_only)
    raise typer.Exit(code=0)


def summary_reports(
    cycle: str | None = typer.Option(
        None,
        "--cycle",
        help="Restrict to the two most recent archives for this cycle name.",
    ),
) -> None:
    """Diff the two most recent archived runs (newest vs previous)."""
    from testo_core.cli.ui.console import default_console
    from testo_core.db import get_report_archive_repository

    console = default_console()
    repo = get_report_archive_repository()
    cycle_key = cycle.strip() if cycle else None
    rows = repo.list_recent_for_cycle(cycle_name=cycle_key, limit=2) if cycle_key else repo.list_recent(limit=2)
    if len(rows) < 2:
        console.print("[fail]Need at least two archived runs in the database for ``summary``.[/]")
        raise typer.Exit(code=int(EngineExitCode.INVALID_INPUT))
    current, baseline = rows[0], rows[1]
    console.print(
        f"[muted]Comparing[/] [bold]{baseline.id}[/] (baseline) → [bold]{current.id}[/] (current)"
    )
    _render_diff(console=console, baseline=baseline, current=current, metrics_only=False)
    raise typer.Exit(code=0)
