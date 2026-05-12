"""``testo run`` — execute a plan defined in testosterone.yaml.

This module exposes :func:`run` as a plain function so the parent Typer app
can register it under ``app.command(name="run", ...)``.  The Typer decorator
metadata (option names, help text) is attached via :func:`typer.Option`
defaults below.

The body defers every heavy import (engine, frameworks, DB) until after
argument validation so ``testo --help`` stays cheap.
"""

from __future__ import annotations

from pathlib import Path

import typer


def run(
    plan: str = typer.Option(
        None,
        "--plan",
        "-p",
        help="Name of the plan to execute (from the 'plans:' section of testosterone.yaml).",
    ),
    config: Path = typer.Option(
        None,
        "--config",
        "-c",
        exists=False,
        dir_okay=False,
        readable=True,
        help="Path to a testosterone.yaml file (defaults to discovery).",
    ),
    stream: bool = typer.Option(
        False,
        "--stream",
        help="Tail each stage's stdout live instead of waiting for the post-mortem panel.",
    ),
    ci: bool = typer.Option(
        False,
        "--ci",
        help="Emit NDJSON events on stdout instead of Rich panels (machine-readable).",
    ),
    no_persist: bool = typer.Option(
        False,
        "--no-persist",
        help="Skip writing run records to the optional history database.",
    ),
    workers: int = typer.Option(
        None,
        "--workers",
        "-w",
        help="Override the default worker count for parallel-aware frameworks (e.g. BehaveX).",
    ),
) -> None:
    """Run a plan end-to-end."""
    # Deferred imports so `testo --help` and `testo plans list` stay light.
    from testo_core.cli.ui.console import default_console, make_console
    from testo_core.cli.runner import execute_plan_command

    console = make_console(plain=True) if ci else default_console()
    exit_code = execute_plan_command(
        console=console,
        plan_name=plan,
        config_path=config,
        stream=stream,
        ci=ci,
        persist=not no_persist,
        workers_override=workers,
    )
    raise typer.Exit(code=int(exit_code))
