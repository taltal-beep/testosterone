"""Filesystem + Docker cleanup helpers for ``testo clean``."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

PROJECT_DOCKER_LABEL = "com.testosterone.project=uqo"


def remove_tree_if_exists(path: Path) -> bool:
    """Delete ``path`` if it exists and is a directory. Returns whether anything was removed."""
    p = path.expanduser().resolve()
    if p.is_dir():
        shutil.rmtree(p, ignore_errors=False)
        return True
    return False


def docker_prune_stopped_with_label(*, label: str = PROJECT_DOCKER_LABEL) -> tuple[int, str]:
    """Run ``docker container prune`` filtered by label; returns (exit_code, combined stderr+stdout)."""
    try:
        proc = subprocess.run(  # noqa: S603, S607
            [
                "docker",
                "container",
                "prune",
                "-f",
                f"--filter=label={label}",
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=120,
        )
        out = (proc.stdout or "") + (proc.stderr or "")
        return proc.returncode, out
    except FileNotFoundError:
        return 127, "docker: command not found"
    except subprocess.TimeoutExpired:
        return 124, "docker prune timed out"
