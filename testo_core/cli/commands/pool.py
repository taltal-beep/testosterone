"""``testo pool`` — look at the real keys behind a resource pool, with your own commands.

Testosterone never creates or deletes a VM (or any key) on its own. A pool's
``provider:`` holds the config author's commands, and only this command group
runs them, when a person types it. ``testo pool status`` is read-only: it runs
``provider.list`` and, with ``--check``, the pool's ``on_check`` on each free key,
then says which keys are missing, which exist outside the pool, and which fail.
See :mod:`testo_core.resources.provider`.
"""

from __future__ import annotations

from pathlib import Path

import typer

from testo_core.cli.commands.lease import _CONFIG, _SERVER, _backend, _console, _fail
from testo_core.engine.exit_codes import EngineExitCode

app = typer.Typer(
    help="Compare resource pools with the keys that really exist (your provider commands).",
    no_args_is_help=True,
)


@app.command("status")
def status(
    pool_name: str | None = typer.Argument(None, metavar="[POOL]"),
    check: bool = typer.Option(
        False, "--check", help="Also run each pool's on_check on every free key."
    ),
    as_json: bool = typer.Option(False, "--json", help="Print the reports as JSON."),
    server: str | None = _SERVER,
    config: Path | None = _CONFIG,
) -> None:
    """Missing keys, leftovers and failed checks. Exits 1 when any pool has one, 3 when a list command fails."""
    import json
    from dataclasses import asdict

    from rich.markup import escape
    from rich.table import Table

    from testo_core.config.errors import ConfigError
    from testo_core.config.loader import discover_and_load
    from testo_core.resources.provider import pool_report
    from testo_core.resources.store import LeaseError

    try:
        pools = list(discover_and_load(config_path=config).resources.values())
    except ConfigError as exc:
        raise _fail(str(exc), EngineExitCode.INVALID_INPUT) from exc
    if pool_name:
        pools = [p for p in pools if p.name == pool_name]
        if not pools:
            raise _fail(
                f"no pool {pool_name!r} under 'resources:' in the config",
                EngineExitCode.INVALID_INPUT,
            )
    try:
        leases = {s.name: s.items for s in _backend(server).status(pool_name, pools=pools)}
    except LeaseError as exc:
        raise _fail(str(exc), EngineExitCode.INFRA_FAILURE) from exc

    note = _console(stderr=True)
    reports = []
    for pool in pools:
        if pool.provider and pool.provider.list:
            note.print(f"[muted]testo pool: {pool.name}: running {escape(pool.provider.list)}[/]")
        if check and pool.on_check:
            note.print(f"[muted]testo pool: {pool.name}: on_check on each free key[/]")
        reports.append(pool_report(pool, leases.get(pool.name, ()), check=check))

    if as_json:
        typer.echo(
            json.dumps(
                [{**asdict(r), "missing": list(r.missing), "healthy": r.healthy} for r in reports]
            )
        )
    else:
        console = _console()
        if not reports:
            console.print(
                "[muted]No pools yet. Add one under 'resources:' in testosterone.yaml.[/]"
            )
        for report in reports:
            if report.list_problem:
                verdict = f"[fail]{escape(report.list_problem)}[/]"
            elif report.healthy:
                verdict = "[ok]matches[/]" if report.has_list else "[muted]no provider.list[/]"
            else:
                verdict = "[warn]needs a look[/]"
            table = Table(title=f"{report.pool}: {verdict}", title_justify="left")
            table.add_column("key", style="bold")
            table.add_column("exists")
            table.add_column("lease")
            table.add_column("check")
            for key in report.keys:
                exists = {True: "[ok]yes[/]", False: "[fail]missing[/]", None: "[muted]?[/]"}
                checked = (
                    ""
                    if key.check is None
                    else "[ok]ok[/]"
                    if key.check == ""
                    else f"[muted]{escape(key.check)}[/]"
                    if key.check_skipped
                    else f"[fail]{escape(key.check)}[/]"
                )
                table.add_row(escape(key.key), exists[key.exists], key.state, checked)
            for extra in report.extra:
                table.add_row(escape(extra), "[warn]not in pool[/]", "", "")
            console.print(table)
        console.print("[muted]Read-only: testo pool never creates or deletes anything.[/]")

    if any(r.list_problem for r in reports):
        raise typer.Exit(code=int(EngineExitCode.INFRA_FAILURE))
    if not all(r.healthy for r in reports):
        raise typer.Exit(code=int(EngineExitCode.DOMAIN_FAILURE))
