"""Copy Allure ``history/`` from a prior archived cycle into current result dirs (trend graphs)."""

from __future__ import annotations

import logging
import shutil
import tempfile
from pathlib import Path

from rich.console import Console

from testo_core.reporting.collector import collect_results
from testo_core.services.report_archive import extract_archive_to_plan_dir

logger = logging.getLogger(__name__)


def _copy_matching_history(prior_plan_root: Path, current_results_dir: Path) -> bool:
    fw = current_results_dir.name
    candidates = sorted(prior_plan_root.glob(f"**/allure-results/{fw}/history"))
    if not candidates:
        return False
    src = candidates[-1]
    if not src.is_dir():
        return False
    dest = current_results_dir / "history"
    shutil.copytree(src, dest, dirs_exist_ok=True)
    return True


def try_inject_prior_history(
    *,
    artifacts_root: Path,
    plan_name: str | None,
    console: Console | None,
    enabled: bool,
) -> None:
    """Best-effort: unpack latest prior archive for ``plan_name`` and merge ``history`` folders."""
    if not enabled or not plan_name:
        return
    try:
        from testo_core.db import get_report_archive_repository

        repo = get_report_archive_repository()
        rows = repo.list_recent_for_cycle(cycle_name=plan_name, limit=2)
        if len(rows) < 2:
            return
        src_row = rows[1]

        with tempfile.TemporaryDirectory(prefix="testo-history-") as td:
            tmp = Path(td)
            extract_archive_to_plan_dir(
                zip_bytes=src_row.artifact_bytes,
                dest_artifacts_root=tmp,
                plan_name=plan_name,
            )
            prior_root = tmp / plan_name
            if not prior_root.is_dir():
                return
            results = collect_results(artifacts_root, plan_name=plan_name)
            copied = any(_copy_matching_history(prior_root, st.results_dir) for st in results.stages)

        if console and copied:
            console.print("[dim]Injected Allure history from a prior archived run (trends).[/]")
    except Exception:
        logger.debug("Allure history injection skipped", exc_info=True)
