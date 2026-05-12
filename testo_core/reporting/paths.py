"""Path helpers shared by the reporting submodules."""

from __future__ import annotations

from pathlib import Path


def plan_artifacts_dir(artifacts_root: Path, plan: str | None = None) -> Path:
    """Return ``<artifacts>/<plan>/`` (or ``<artifacts>/`` if ``plan`` is None)."""
    root = artifacts_root.expanduser().resolve()
    return (root / plan).resolve() if plan else root


def discover_plan_dirs(artifacts_root: Path) -> list[Path]:
    """Return every ``<artifacts>/<plan>/`` directory that looks like a run."""
    root = artifacts_root.expanduser().resolve()
    if not root.is_dir():
        return []
    out: list[Path] = []
    for child in root.iterdir():
        if not child.is_dir():
            continue
        if (child / "events.ndjson").is_file() or any(child.glob("*/allure-results")):
            out.append(child)
    return sorted(out)
