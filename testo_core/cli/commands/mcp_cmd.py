"""``testo mcp`` — an MCP server over the run history, for coding agents (stdio)."""

from __future__ import annotations

import os
from pathlib import Path

import typer

from testo_core.engine.exit_codes import EngineExitCode

MISSING_EXTRA = "The MCP server needs the mcp extra: pip install 'testo-core[mcp]'"


def mcp(
    config: Path | None = typer.Option(
        None,
        "--config",
        help=(
            "testosterone.yaml of the project to serve (default: auto-discover from the "
            "working directory). Its folder becomes the working directory, so its database "
            "and run snapshots are found when the agent starts the server elsewhere."
        ),
    ),
    allow_writes: bool = typer.Option(
        False,
        "--allow-writes",
        help="Also register write tools (mark_failure_cause). Off by default: read-only.",
    ),
) -> None:
    """Serve the run history to a coding agent over MCP (stdio): failures, flaky tests, history."""
    try:
        import mcp as _sdk  # noqa: F401
    except ModuleNotFoundError:
        typer.echo(MISSING_EXTRA, err=True)
        raise typer.Exit(int(EngineExitCode.INVALID_INPUT)) from None

    if config is not None:
        config = config.expanduser().resolve()
        if not config.is_file():
            typer.echo(f"config file not found: {config}", err=True)
            raise typer.Exit(int(EngineExitCode.INVALID_INPUT))
        # Before anything resolves the database URL or the data root from the cwd.
        os.chdir(config.parent)

    from testo_core.config.errors import ConfigDiscoveryError, ConfigError
    from testo_core.config.loader import discover_and_load
    from testo_core.mcp_server import HistoryTools, build_server, quarantine_rules

    try:
        cfg = discover_and_load(config_path=config)
    except ConfigDiscoveryError:
        if config is not None:
            raise
        cfg = None  # ingested cycles need no config
    except ConfigError as exc:
        typer.echo(f"config error: {exc}", err=True)
        raise typer.Exit(int(EngineExitCode.INVALID_INPUT)) from exc

    if config is not None and not (os.environ.get("DATABASE_URL") or "").strip():
        # A config with a non-default file name isn't found by DB discovery; read it here.
        from testo_core.config.database_section import (
            extract_database_url_from_mapping,
            load_raw_config_dict,
        )

        url = extract_database_url_from_mapping(load_raw_config_dict(config))
        if url:
            os.environ["DATABASE_URL"] = url

    server = build_server(HistoryTools(quarantine_rules(cfg)), allow_writes=allow_writes)
    # stdout is the protocol channel: nothing else may print there.
    server.run("stdio")
