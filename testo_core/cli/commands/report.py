"""``testo report`` — unified Allure reports and raw framework-native reports.

Default (no subcommand): generate / serve / export from Allure results.

``native``: open or list BehaveX HTML, pytest junit/html heuristics, etc.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import typer

from testo_core.engine.exit_codes import EngineExitCode

report_app = typer.Typer(
    name="report",
    help=(
        "Build unified Allure reports from the latest cycle, or access raw, framework-specific "
        "reports (e.g. BehaveX HTML) from the latest run."
    ),
    invoke_without_command=True,
    no_args_is_help=False,
)


@report_app.callback(invoke_without_command=True)
def report_callback(
    ctx: typer.Context,
    artifacts_root: Path = typer.Option(
        Path("artifacts"),
        "--artifacts",
        "-a",
        help="Artifacts root that holds per-cycle and per-stage outputs.",
    ),
    cycle: str | None = typer.Option(
        None,
        "--cycle",
        help="Restrict to one cycle's artifacts (YAML key under cycles:; legacy plans:).",
    ),
    plan: str | None = typer.Option(
        None,
        "--plan",
        "-p",
        help="Deprecated alias for --cycle.",
        hidden=True,
    ),
    generate_only: bool = typer.Option(
        False,
        "--generate-only",
        help="Write HTML to --out only; do not start the local HTTP dashboard (Allure path only).",
    ),
    host: str = typer.Option(
        "127.0.0.1",
        "--host",
        help="Host for the Allure dashboard (after allure generate).",
    ),
    port: int = typer.Option(
        8080,
        "--port",
        help="Port for the Allure dashboard; if busy, a free port is used automatically. Use 0 to always pick a free port.",
    ),
    out: Path = typer.Option(
        Path("artifacts/report"),
        "--out",
        "-o",
        help="Where to write the generated HTML report (Allure path only).",
    ),
    fmt: str = typer.Option(
        "html",
        "--format",
        "-f",
        help="Output format: html (default), json, or junit (Allure path only).",
    ),
    summary_out: Path | None = typer.Option(
        None,
        "--summary-out",
        help="When --format=json|junit, file path to write the machine-readable summary to.",
    ),
    no_history: bool = typer.Option(
        False,
        "--no-history",
        help="Do not inject Allure history/ from a prior DB-archived run before ``allure generate``.",
    ),
) -> None:
    """Build a unified Allure report from the latest (or selected) cycle, then open it locally."""
    resolved_cycle = cycle if cycle is not None else plan
    ctx.obj = {"artifacts_root": artifacts_root, "resolved_cycle": resolved_cycle}

    if ctx.invoked_subcommand is not None:
        return

    from testo_core.cli.ui.console import default_console
    from testo_core.reporting.entry import dispatch_report

    console = default_console()
    exit_code = dispatch_report(
        console=console,
        artifacts_root=artifacts_root,
        plan_name=resolved_cycle,
        generate_only=generate_only,
        port=port,
        host=host,
        out_dir=out,
        fmt=fmt,
        summary_out=summary_out,
        inject_history=not no_history,
    )
    raise typer.Exit(code=int(exit_code))


@report_app.command(
    "native",
    help="Open or list raw, framework-specific reports (e.g. BehaveX report.html) from the latest run.",
)
def report_native(
    ctx: typer.Context,
    routine_name: str | None = typer.Argument(
        None,
        metavar="[ROUTINE]",
        help="Stage (routine) directory name; omit to list native reports for the resolved cycle.",
    ),
    no_open: bool = typer.Option(
        False,
        "--no-open",
        help="Print paths only; do not open the default browser (mirrors Allure --generate-only style).",
    ),
) -> None:
    """List or open native HTML/XML under ``artifacts/<cycle>/<stage>/``.

    With no routine argument, prints a summary table then opens each discoverable HTML report
    in the browser (same idea as ``testo report`` for Allure). Use ``--no-open`` to list only.
    """
    from rich.table import Table

    from testo_core.cli.ui.console import default_console
    from testo_core.reporting.native_reports import (
        _infer_equipment,
        find_stage_dir,
        list_native_rows,
        load_stage_equipment,
        native_row_for_stage,
        open_native_uri,
        resolve_cycle_dir,
    )
    from testo_core.reporting.paths import relpath_for_display

    obj: dict[str, Any] = ctx.obj or {}
    artifacts_root = obj.get("artifacts_root") or Path("artifacts")
    resolved_cycle = obj.get("resolved_cycle")

    console = default_console()
    console.print(
        "[bold magenta]────────────────────────── Raw Equipment Specs ──────────────────────────[/]"
    )

    cycle_dir = resolve_cycle_dir(artifacts_root=artifacts_root, cycle=resolved_cycle)
    if cycle_dir is None:
        label = resolved_cycle or "(latest)"
        console.print(f"[fail]No cycle artifacts found for[/] {label} under {relpath_for_display(Path(artifacts_root))}")
        raise typer.Exit(code=int(EngineExitCode.INVALID_INPUT))

    if routine_name is None or not str(routine_name).strip():
        rows = list_native_rows(cycle_dir=cycle_dir)
        if not rows:
            console.print("[warn]No raw data found for this routine[/] — no stage directories under the cycle.")
            raise typer.Exit(code=0)

        table = Table(title="Native reports", show_lines=False, title_justify="left")
        table.add_column("Routine", style="title")
        table.add_column("Equipment", style="framework")
        table.add_column("Open", style="muted", overflow="fold", no_wrap=False)
        table.add_column("Notes")
        for r in rows:
            open_cell = relpath_for_display(r.open_path) if r.open_path else "—"
            notes = r.notes or ("ready" if r.open_path else "—")
            table.add_row(r.routine, r.equipment, open_cell, notes)
        console.print(table)
        for r in rows:
            if r.open_path is not None:
                uri = r.open_path.expanduser().resolve().as_uri()
                console.print(f"[dim]{r.routine} →[/] [link={uri}]{r.open_path.resolve()}[/]")
        console.print(f"[muted]cycle:[/] {relpath_for_display(cycle_dir)}")
        if not no_open:
            html_targets = [r for r in rows if r.open_path is not None and r.open_kind == "html"]
            any_failed = False
            for r in html_targets:
                if open_native_uri(r.open_path):
                    console.print(
                        f"[ok]Opened[/] [html] {relpath_for_display(r.open_path)} [muted]({r.routine})[/]"
                    )
                else:
                    any_failed = True
                    console.print(
                        f"[fail]Could not open browser for[/] {r.open_path.resolve()} [muted]({r.routine})[/]"
                    )
            if any_failed:
                raise typer.Exit(code=int(EngineExitCode.INFRA_FAILURE))
        raise typer.Exit(code=0)

    routine = str(routine_name).strip()
    stage_dir = find_stage_dir(cycle_dir, routine)
    if stage_dir is None:
        console.print(f"[fail]Unknown routine[/] {routine!r} under {relpath_for_display(cycle_dir)}")
        raise typer.Exit(code=int(EngineExitCode.INVALID_INPUT))

    eq_map = load_stage_equipment(cycle_dir)
    equipment = _infer_equipment(stage_dir, routine, eq_map)
    row = native_row_for_stage(stage_dir, equipment)

    if row.open_path is None:
        console.print("[warn]No raw data found for this routine[/]")
        if row.notes:
            console.print(f"[muted]{row.notes}[/]")
        raise typer.Exit(code=0)

    uri = row.open_path.expanduser().resolve().as_uri()
    console.print(f"[dim]path:[/] [link={uri}]{row.open_path.resolve()}[/]")
    if no_open:
        raise typer.Exit(code=0)

    if open_native_uri(row.open_path):
        console.print(
            f"[ok]Opened[/] [{row.open_kind}] {relpath_for_display(row.open_path)}"
        )
        raise typer.Exit(code=0)

    console.print("[fail]Could not open the default browser for[/] " f"{relpath_for_display(row.open_path)}")
    raise typer.Exit(code=int(EngineExitCode.INFRA_FAILURE))


@report_app.command("list", help="List archived cycle reports stored in the database.")
def report_list_archived(
    limit: int = typer.Option(30, "--limit", "-n", help="Maximum number of rows to show."),
) -> None:
    from rich.table import Table

    from testo_core.cli.ui.console import default_console
    from testo_core.db import get_report_archive_repository

    console = default_console()
    try:
        rows = get_report_archive_repository().list_recent(limit=limit)
    except Exception as exc:
        console.print(f"[fail]could not list reports:[/] {exc}")
        raise typer.Exit(code=int(EngineExitCode.INFRA_FAILURE)) from exc

    if not rows:
        console.print("[muted]No archived reports found.[/]")
        raise typer.Exit(code=0)

    table = Table(title="Archived reports", title_justify="left")
    table.add_column("id", style="bold", overflow="fold", min_width=36, no_wrap=True)
    table.add_column("cycle", style="title")
    table.add_column("created", style="muted")
    table.add_column("exit", justify="right")
    table.add_column("tests", justify="right")
    table.add_column("pass", justify="right")
    table.add_column("fail", justify="right")
    for r in rows:
        table.add_row(
            str(r.id),
            r.cycle_name,
            str(r.created_at),
            str(r.exit_code),
            "—" if r.total_tests is None else str(r.total_tests),
            "—" if r.passed is None else str(r.passed),
            "—" if r.failed is None else str(r.failed),
        )
    console.print(table)
    raise typer.Exit(code=0)


@report_app.command("open", help="Re-open an archived report from the database (Allure path).")
def report_open_archived(
    report_id: str = typer.Option(
        ...,
        "--id",
        help="Report archive UUID (primary key; use ``testo report list`` id column—not headless RunRecord id).",
    ),
    generate_only: bool = typer.Option(
        False,
        "--generate-only",
        help="Write HTML to --out only; do not start the Allure HTTP dashboard.",
    ),
    host: str = typer.Option("127.0.0.1", "--host", help="Host for the Allure dashboard."),
    port: int = typer.Option(
        8080,
        "--port",
        help="Port for the Allure dashboard; if busy, a free port is used automatically. Use 0 to always pick a free port.",
    ),
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
    summary_out: Path | None = typer.Option(
        None,
        "--summary-out",
        help="When --format=json|junit, output file path.",
    ),
) -> None:
    import tempfile
    import uuid

    from testo_core.cli.ui.console import default_console
    from testo_core.db import get_report_archive_repository
    from testo_core.reporting.entry import dispatch_report
    from testo_core.services.report_archive import extract_archive_to_plan_dir

    console = default_console()
    try:
        rid = uuid.UUID(str(report_id).strip())
    except (ValueError, TypeError):
        console.print(f"[fail]invalid report id:[/] {report_id!r}")
        raise typer.Exit(code=int(EngineExitCode.INVALID_INPUT)) from None

    try:
        row = get_report_archive_repository().get(rid)
    except Exception as exc:
        console.print(f"[fail]could not load report:[/] {exc}")
        raise typer.Exit(code=int(EngineExitCode.INFRA_FAILURE)) from exc

    if row is None:
        console.print(f"[fail]no archived report with id[/] {rid}")
        raise typer.Exit(code=int(EngineExitCode.INVALID_INPUT))

    with tempfile.TemporaryDirectory(prefix="testo-report-") as td:
        root = Path(td)
        extract_archive_to_plan_dir(
            zip_bytes=row.artifact_bytes,
            dest_artifacts_root=root,
            plan_name=row.cycle_name,
        )
        exit_code = dispatch_report(
            console=console,
            artifacts_root=root,
            plan_name=row.cycle_name,
            generate_only=generate_only,
            port=port,
            host=host,
            out_dir=out,
            fmt=fmt,
            summary_out=summary_out,
            inject_history=False,
        )
    raise typer.Exit(code=int(exit_code))
