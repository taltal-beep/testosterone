"""``testo config-db`` — set ``database.url`` in testosterone config (YAML or pyproject)."""

from __future__ import annotations

from pathlib import Path

import typer

from testo_core.engine.exit_codes import EngineExitCode


def config_db(
    config: Path | None = typer.Option(
        None,
        "--config",
        "-c",
        help="Config file to update (YAML or pyproject.toml). Defaults to the first discovered file.",
    ),
    url: str | None = typer.Option(
        None,
        "--url",
        help="Full SQLAlchemy database URL (skips host/port/user prompts when set).",
    ),
    host: str | None = typer.Option(None, "--host", help="PostgreSQL host (with --url omitted)."),
    port: int | None = typer.Option(None, "--port", help="PostgreSQL port (default 5432)."),
    username: str | None = typer.Option(None, "--username", help="Database user."),
    password: str | None = typer.Option(None, "--password", help="Database password."),
    database: str | None = typer.Option(
        None,
        "--database",
        "--db",
        help="Database name (PostgreSQL / MySQL).",
    ),
    schema: str | None = typer.Option(
        None,
        "--schema",
        help="PostgreSQL search_path (optional); encoded as a connection option.",
    ),
) -> None:
    """Write ``database.url`` into testosterone config.

    Merging uses PyYAML / tomli-w and may strip YAML comments. ``DATABASE_URL`` in the
    environment still overrides file-based settings at runtime.
    """
    from testo_core.cli.ui.console import default_console
    from testo_core.config.database_section import (
        build_postgresql_url,
        discover_config_path,
        merge_database_url_pyproject,
        merge_database_url_yaml,
    )
    from testo_core.config.errors import ConfigDiscoveryError, ConfigValidationError
    from testo_core.db import reset_repository_cache
    from testo_core.db_config import reset_engine_cache, validate_database_url
    from testo_core.repository.factory import select_repository_adapter

    console = default_console()

    target = config.expanduser().resolve() if config is not None else discover_config_path()
    if target is None:
        console.print(
            "[fail]No testosterone.yaml / testosterone.yml / pyproject.toml with "
            "[tool.testosterone] found. Pass --config PATH.[/]"
        )
        raise typer.Exit(code=int(EngineExitCode.INVALID_INPUT))

    if not target.is_file():
        console.print(f"[fail]Config file not found:[/] {target}")
        raise typer.Exit(code=int(EngineExitCode.INVALID_INPUT))

    resolved_url: str
    if url is not None and str(url).strip():
        resolved_url = str(url).strip()
    else:
        h = host or typer.prompt("Database host", default="localhost")
        p = port if port is not None else int(typer.prompt("Port", default="5432"))
        u = username or typer.prompt("Username")
        pw = password or typer.prompt("Password", hide_input=True)
        dbn = database or typer.prompt("Database name")
        sch = schema if schema is not None else typer.prompt("PostgreSQL schema (optional)", default="")
        sch = sch.strip() or None
        resolved_url = build_postgresql_url(
            host=str(h).strip(),
            port=int(p),
            username=str(u).strip(),
            password=str(pw),
            database=str(dbn).strip(),
            schema=sch,
        )

    try:
        validate_database_url(resolved_url)
        select_repository_adapter(url=resolved_url)
    except ValueError as exc:
        console.print(f"[fail]{exc}[/]")
        raise typer.Exit(code=int(EngineExitCode.INVALID_INPUT)) from exc

    try:
        from urllib.parse import urlparse

        from sqlalchemy import create_engine, text

        dialect = urlparse(resolved_url).scheme.lower().split("+", 1)[0]
        eng_kwargs: dict[str, object] = {}
        if dialect == "sqlite":
            eng_kwargs["connect_args"] = {"check_same_thread": False}
        else:
            eng_kwargs["pool_pre_ping"] = True
        probe = create_engine(resolved_url, **eng_kwargs)
        with probe.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:
        console.print(f"[fail]Database connection check failed:[/] {exc}")
        raise typer.Exit(code=int(EngineExitCode.INFRA_FAILURE)) from exc

    try:
        if target.suffix.lower() == ".toml":
            merge_database_url_pyproject(path=target, url=resolved_url)
        else:
            merge_database_url_yaml(path=target, url=resolved_url)
    except (ConfigDiscoveryError, ConfigValidationError) as exc:
        console.print(f"[fail]{exc}[/]")
        raise typer.Exit(code=int(EngineExitCode.INVALID_INPUT)) from exc

    reset_engine_cache()
    reset_repository_cache()
    console.print(f"[ok]Wrote database.url to[/] {target}")
    console.print(
        "[dim]Note: ``DATABASE_URL`` env overrides file settings. PyYAML may reorder keys "
        "and remove comments.[/]"
    )
