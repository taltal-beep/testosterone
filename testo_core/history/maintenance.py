"""The few writes the read side needs: metadata patches and orphaned-run cleanup."""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime
from typing import Any

from testo_core.db import get_repository
from testo_core.repository.models import RunRecord, RunStatus

logger = logging.getLogger(__name__)


def upsert_run_metadata(*, run_id: str, metadata_patch: dict[str, Any]) -> bool:
    """Shallow-merge ``metadata_patch`` into the run's metadata; ``False`` if the run is missing."""
    return get_repository().merge_run_metadata(run_id, metadata_patch)


def cleanup_orphaned_runs(*, note: str = "Orphaned due to system crash") -> int:
    """Mark runs still ``RUNNING`` as ``FAILED``; returns how many were updated.

    Called when the API starts: a run cannot still be executing if the process
    that ran it is gone (reload, crash, reboot), and leaving it ``RUNNING``
    would show it as live in the UI forever.
    """
    repo = get_repository()
    orphans = repo.list_runs_by_status(RunStatus.RUNNING)
    if not orphans:
        return 0
    now = datetime.now(tz=UTC)
    updated: list[RunRecord] = []
    for record in orphans:
        metadata = dict(record.metadata_ or {})
        metadata.setdefault("error", "orphaned")
        metadata.setdefault("error_message", note)
        metadata.setdefault("orphaned_at", time.time())
        record.metadata_ = metadata
        record.status = RunStatus.FAILED
        record.end_time = now
        updated.append(record)
    count = repo.bulk_update(updated)
    if count:
        logger.warning("Marked %s orphaned RUNNING run(s) as FAILED (%s).", count, note)
    return count
