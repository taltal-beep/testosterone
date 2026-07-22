"""``testo version`` — print the installed testo-core version."""

from __future__ import annotations

import importlib.metadata as md

import typer


def resolve_version() -> str:
    try:
        return md.version("testo-core")
    except md.PackageNotFoundError:
        return "0.0.0+source"


def version() -> None:
    typer.echo(f"testo {resolve_version()}")
