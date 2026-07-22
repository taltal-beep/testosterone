"""Abstract repository interface for run history persistence."""

from __future__ import annotations

import uuid
from typing import Any, Protocol, runtime_checkable

from .models import RunRecord, RunStatus


class RunNotFoundError(LookupError):
    """Raised when a run id has no corresponding :class:`RunRecord`."""


@runtime_checkable
class BaseRunRepository(Protocol):
    """Storage-agnostic interface for :class:`RunRecord` lifecycle operations.

    Implementations MUST be safe to call from multiple threads (e.g. Streamlit worker
    thread and main UI thread) when backed by a thread-safe SQLAlchemy engine.
    """

    def create_run(
        self,
        *,
        status: RunStatus = RunStatus.PENDING,
        metadata: dict[str, Any] | None = None,
    ) -> RunRecord:
        """Insert a new :class:`RunRecord` and return the persisted row (with ``id`` assigned)."""

    def get_run(self, run_id: uuid.UUID | str) -> RunRecord | None:
        """Return the :class:`RunRecord` for the given id, or ``None`` if missing.

        Accepts the orchestrator's external string id; implementations derive a stable
        :class:`uuid.UUID` from non-UUID strings using :func:`uuid.uuid5` over the
        ``uqo-run:<run_id>`` namespace.
        """

    def update_run_status(
        self,
        run_id: uuid.UUID | str,
        *,
        status: RunStatus,
        metadata: dict[str, Any] | None = None,
    ) -> RunRecord:
        """Update status (and shallow-merge ``metadata``) for ``run_id``, or insert if missing.

        Sets ``end_time`` to the current UTC time when ``status`` is
        :attr:`RunStatus.COMPLETED` or :attr:`RunStatus.FAILED`.
        """

    def list_recent_runs(self, *, limit: int = 30) -> list[RunRecord]:
        """Return up to ``limit`` runs ordered by ``start_time`` descending (newest first)."""

    def list_runs_by_status(self, status: RunStatus) -> list[RunRecord]:
        """Return all runs currently in the given ``status`` (e.g. for orphan cleanup)."""

    def bulk_update(self, records: list[RunRecord]) -> int:
        """Persist updates to the given rows in one transaction; return the number of rows written."""
