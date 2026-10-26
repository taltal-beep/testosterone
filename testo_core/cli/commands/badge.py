"""``testo badge`` — a README badge for a cycle's latest run (SVG or shields.io JSON)."""

from __future__ import annotations

import json
from pathlib import Path

import typer

from testo_core.engine.exit_codes import EngineExitCode


def badge(
    cycle: str | None = typer.Option(
        None, "--cycle", help="Latest run of this cycle (default: the latest run of any cycle)."
    ),
    out: Path | None = typer.Option(
        None, "--out", "-o", help="File to write (default: print to stdout)."
    ),
    fmt: str = typer.Option(
        "svg", "--format", help="svg: the badge image. json: a shields.io endpoint badge."
    ),
    label: str = typer.Option("tests", "--label", help="Text on the left of the badge."),
) -> None:
    """Write a badge like 'tests | 412 passed · 2 flaky' for a README."""
    from testo_core.services.badge import badge_for_cycle, render_svg, shields_endpoint

    fmt = fmt.strip().lower()
    if fmt not in ("svg", "json"):
        typer.echo("--format takes svg or json", err=True)
        raise typer.Exit(code=int(EngineExitCode.INVALID_INPUT))
    made = badge_for_cycle(cycle.strip() if cycle else None, label=label)
    text = render_svg(made) if fmt == "svg" else json.dumps(shields_endpoint(made))
    if out is None:
        typer.echo(text)
        return
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text + "\n", encoding="utf-8")
    typer.echo(f"{out}: {made.label} | {made.message}")
