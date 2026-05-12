"""``testo version`` — print the installed testo-core version."""

from __future__ import annotations

import importlib.metadata as md

import typer


def version() -> None:
    try:
        ver = md.version("testo-core")
    except md.PackageNotFoundError:
        ver = "0.0.0+source"
    typer.echo(f"testo {ver}")
