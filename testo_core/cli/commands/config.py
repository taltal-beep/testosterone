"""``testo config`` — validate or scaffold a testosterone.yaml."""

from __future__ import annotations

from pathlib import Path

import typer


app = typer.Typer(help="Validate or scaffold a testosterone.yaml.", no_args_is_help=True)


_STARTER_YAML = """\
version: 1

defaults:
  target_repo: .
  artifacts_root: artifacts
  timeout_s: 600
  workers: 4

plans:
  smoke-test:
    description: Fast sanity sweep used by the PR gate.
    stages:
      - name: api
        framework: pytest
        args: ["-m", "smoke", "--maxfail=1"]

  nightly-build:
    description: Full suite executed on cron.
    stages:
      - name: api
        framework: pytest
        args: ["-q"]
      - name: ui-bdd
        framework: behavex
        workers: 8
        timeout_s: 1800
"""


@app.command("validate")
def validate(
    config: Path = typer.Option(
        None,
        "--config",
        "-c",
        help="Path to a testosterone.yaml file (defaults to discovery).",
    ),
) -> None:
    """Load + resolve the config and print 'ok' (or exit non-zero with an error)."""
    from testo_core.cli.ui.console import default_console
    from testo_core.config.errors import ConfigError
    from testo_core.config.loader import discover_and_load

    console = default_console()
    try:
        cfg = discover_and_load(config_path=config)
    except ConfigError as exc:
        console.print(f"[fail]config error:[/] {exc}")
        raise typer.Exit(code=2) from exc
    console.print(
        f"[ok]ok[/] — version={cfg.version} plans={len(cfg.plans)} defaults_target={cfg.defaults.target_repo}"
    )


@app.command("init")
def init(
    path: Path = typer.Option(
        Path("testosterone.yaml"),
        "--path",
        "-p",
        help="Output path for the starter testosterone.yaml.",
    ),
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite an existing file."),
) -> None:
    """Write a starter testosterone.yaml at ``path``."""
    from testo_core.cli.ui.console import default_console

    console = default_console()
    if path.exists() and not force:
        console.print(f"[fail]refusing to overwrite[/] {path} (use --force).")
        raise typer.Exit(code=2)
    path.write_text(_STARTER_YAML, encoding="utf-8")
    console.print(f"[ok]wrote starter config to[/] {path}")
