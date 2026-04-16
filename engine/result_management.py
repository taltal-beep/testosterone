from __future__ import annotations

import shutil
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PrepareResult:
    shared_dir: Path
    archived_to: Path | None


def prepare_allure_results_dir(
    shared_dir: Path,
    *,
    mode: str = "archive",
    archive_root: Path | None = None,
    run_id: str | None = None,
) -> PrepareResult:
    """
    Prevent data bleeding between runs.

    - mode="clear": delete and recreate shared_dir
    - mode="archive": move shared_dir to archive_root/<timestamp>_<run_id>/ and recreate
    """
    shared_dir = shared_dir.expanduser().resolve()
    archive_root = (archive_root or (shared_dir.parent / "allure-results-archive")).expanduser().resolve()

    if not shared_dir.exists():
        shared_dir.mkdir(parents=True, exist_ok=True)
        return PrepareResult(shared_dir=shared_dir, archived_to=None)

    if mode not in {"clear", "archive"}:
        raise ValueError(f"Unsupported mode: {mode}")

    archived_to: Path | None = None
    if mode == "clear":
        shutil.rmtree(shared_dir, ignore_errors=True)
    else:
        ts = time.strftime("%Y%m%d_%H%M%S")
        suffix = f"_{run_id}" if run_id else ""
        archived_to = archive_root / f"{ts}{suffix}"
        archived_to.parent.mkdir(parents=True, exist_ok=True)
        if archived_to.exists():
            shutil.rmtree(archived_to, ignore_errors=True)
        shutil.move(str(shared_dir), str(archived_to))

    shared_dir.mkdir(parents=True, exist_ok=True)
    return PrepareResult(shared_dir=shared_dir, archived_to=archived_to)

