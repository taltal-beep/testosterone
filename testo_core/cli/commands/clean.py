"""``testo clean`` — remove local artifacts/temp and optionally prune Docker."""

from __future__ import annotations

from pathlib import Path

import typer

from testo_core.engine.exit_codes import EngineExitCode


def clean(
    yes: bool = typer.Option(False, "--yes", "-y", help="Required to confirm destructive deletes."),
    config: Path | None = typer.Option(
        None,
        "--config",
        "-c",
        help="Path to testosterone.yaml for resolving defaults.artifacts_root.",
    ),
    temp_dir: Path = typer.Option(
        Path("temp"),
        "--temp-dir",
        help="Relative directory to remove if present (default ./temp).",
    ),
    docker: bool = typer.Option(
        False,
        "--docker",
        help="Prune stopped Docker containers labeled com.testosterone.project=uqo.",
    ),
) -> None:
    """Delete local artifacts and temp output; optional Docker prune."""
    from testo_core.cli.cleanup import docker_prune_stopped_with_label, remove_tree_if_exists
    from testo_core.cli.ui.console import default_console
    from testo_core.config.errors import ConfigError
    from testo_core.config.loader import discover_and_load

    console = default_console()
    if not yes:
        console.print("[fail]Refusing to delete without --yes (or -y).[/]")
        raise typer.Exit(code=int(EngineExitCode.INVALID_INPUT))

    artifacts_root = Path("artifacts")
    try:
        cfg = discover_and_load(config_path=config)
        artifacts_root = cfg.defaults.artifacts_root.expanduser().resolve()
    except ConfigError as exc:
        console.print(f"[warn]Could not load config ({exc}); using ./artifacts for cleanup.[/]")

    removed: list[str] = []
    if remove_tree_if_exists(artifacts_root):
        removed.append(str(artifacts_root))
    td = temp_dir.expanduser().resolve()
    if remove_tree_if_exists(td):
        removed.append(str(td))

    if removed:
        for p in removed:
            console.print(f"[ok]Removed directory {p}[/]")
    else:
        console.print("[muted]No matching artifact/temp directories found to remove.[/]")

    if docker:
        code, out = docker_prune_stopped_with_label()
        if code == 0:
            console.print("[ok]Docker prune completed for labeled containers.[/]")
            if out.strip():
                console.print(f"[dim]{out.strip()}[/]")
        elif code == 127:
            console.print("[warn]docker CLI not found; skipping container prune.[/]")
        else:
            console.print(f"[fail]docker prune exited {code}: {out.strip()}[/]")
            raise typer.Exit(code=int(EngineExitCode.INFRA_FAILURE))

    console.print("[ok]Clean finished.[/]")
    raise typer.Exit(code=0)
