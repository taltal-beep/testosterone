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
    from testo_core.cli.commands import config as config_cmd
    from testo_core.cli.commands import plans as plans_cmd
    from testo_core.cli.commands import report as report_cmd
    from testo_core.cli.commands import run as run_cmd
    from testo_core.cli.commands import version as version_cmd

    app.command(name="run", help="Execute a plan defined in testosterone.yaml.")(run_cmd.run)
    app.add_typer(plans_cmd.app, name="plans", help="Inspect plans defined in the config.")
    app.add_typer(config_cmd.app, name="config", help="Validate or scaffold a testosterone.yaml.")
    app.command(name="report", help="Generate / serve / export a report from the latest run.")(
        report_cmd.report
    )
    app.command(name="version", help="Print testo-core version.")(version_cmd.version)


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
