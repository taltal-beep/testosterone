"""Typer entry-point for the ``testo`` CLI.

Commands are imported lazily inside their handlers so ``testo --help`` does
not pay for the cost of importing the engine, framework adapters, or the
optional database layer.
"""

from __future__ import annotations

import sys

import typer


app = typer.Typer(
    name="testo",
    help="Testosterone — unified quality orchestration CLI.",
    no_args_is_help=True,
    add_completion=False,
    pretty_exceptions_show_locals=False,
)


def _register_commands() -> None:
    """Wire every subcommand at module load time without importing heavy modules.

    Each handler does its own deferred imports (engine, frameworks, DB), so
    only the lightweight Typer + Rich surface is loaded here.
    """
    from testo_core.cli.commands import clean as clean_mod
    from testo_core.cli.commands import config as config_cmd
    from testo_core.cli.commands import config_db as config_db_cmd
    from testo_core.cli.commands import diff_cli as diff_cli_mod
    from testo_core.cli.commands import doctor as doctor_mod
    from testo_core.cli.commands import init_cmd as init_cmd_mod
    from testo_core.cli.commands import plans as cycles_cmd
    from testo_core.cli.commands import report as report_cmd
    from testo_core.cli.commands import run as run_cmd
    from testo_core.cli.commands import version as version_cmd
    from testo_core.cli.commands import watch as watch_mod

    app.command(name="run", help="Execute a cycle defined in testosterone.yaml.")(run_cmd.run)
    app.command(
        name="config-db",
        help="Set database.url in testosterone.yaml (or pyproject [tool.testosterone]).",
    )(config_db_cmd.config_db)
    app.command(
        name="diff",
        help="Compare two archived report runs (UUIDs from ``testo report list``).",
    )(diff_cli_mod.diff_reports)
    app.command(
        name="summary",
        help="Rich diff of the two most recent archived runs (optional ``--cycle``).",
    )(diff_cli_mod.summary_reports)
    app.add_typer(cycles_cmd.app, name="cycles", help="Inspect cycles defined in the config.")
    # Backward-compatible alias for muscle memory.
    app.add_typer(cycles_cmd.app, name="plans", help="Deprecated alias for `testo cycles`.", hidden=True)
    app.add_typer(config_cmd.app, name="config", help="Validate or scaffold a testosterone.yaml.")
    app.add_typer(
        report_cmd.report_app,
        name="report",
        help=(
            "Unified Allure reports from the latest cycle, or raw framework-native reports "
            "(e.g. BehaveX HTML) via ``testo report native``."
        ),
    )
    app.command(name="version", help="Print testo-core version.")(version_cmd.version)
    app.command(name="doctor", help="Health check: config load, DB probe, CLIs on PATH.")(doctor_mod.doctor)
    app.command(
        name="clean",
        help="Remove artifacts/temp; optional Docker prune (``--yes``, ``--docker``).",
    )(clean_mod.clean)
    app.command(name="watch", help="Watch files and re-run a cycle (``--cycle`` required).")(watch_mod.watch)
    app.command(
        name="init",
        help="Interactive wizard for testosterone.yaml (non-interactive: ``testo config init``).",
    )(init_cmd_mod.wizard)


_register_commands()


def main(argv: list[str] | None = None) -> int:
    """Public main entry-point referenced by ``[project.scripts] testo``."""
    try:
        result = app(args=argv, standalone_mode=False)
    except typer.Exit as exc:
        return int(exc.exit_code or 0)
    except SystemExit as exc:
        return int(exc.code or 0)

    # In ``standalone_mode=False`` Click captures ``typer.Exit`` and returns
    # its exit code instead of raising. Treat the result as an exit code if
    # it looks like one.
    if isinstance(result, int):
        return int(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
