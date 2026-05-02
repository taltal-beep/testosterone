"""SQLModel/SQLAlchemy repository implementation (multi-dialect via engine URL)."""

from __future__ import annotations

import time
import uuid
from datetime import UTC, datetime
from typing import Any, Optional

from sqlalchemy.engine import Engine
from sqlmodel import Session, select

from .base import BaseRunRepository
from .models import RunRecord, RunStatus


def _utcnow() -> datetime:
    return datetime.now(tz=UTC)


def _run_uuid_from_external(run_id: str | uuid.UUID) -> uuid.UUID:
    """Convert external run id to a stable UUID (reuse valid UUIDs; else uuid5)."""
    if isinstance(run_id, uuid.UUID):
        return run_id
    try:
        return uuid.UUID(str(run_id))
    except (ValueError, TypeError):
        return uuid.uuid5(uuid.NAMESPACE_URL, f"uqo-run:{run_id}")


class SQLModelRunRepository(BaseRunRepository):
    """SQLModel-backed repository; works with SQLite, PostgreSQL, and MySQL engines."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def create_run(
        self,
        *,
        status: RunStatus = RunStatus.PENDING,
        metadata: Optional[dict[str, Any]] = None,
    ) -> RunRecord:
        rr = RunRecord(status=status, start_time=_utcnow(), metadata_={})
        base_md: dict[str, Any] = {"run_id": str(rr.id), "created_at": float(time.time())}
        if metadata:
            base_md.update(metadata)
        rr.metadata_ = base_md
        with Session(self._engine) as session:
            session.add(rr)
            session.commit()
            session.refresh(rr)
            session.expunge(rr)
        return rr

    def get_run(self, run_id: uuid.UUID | str) -> Optional[RunRecord]:
        rid = _run_uuid_from_external(run_id)
        with Session(self._engine) as session:
            r = session.get(RunRecord, rid)
            if r is None:
                return None
            session.expunge(r)
            return r

    def update_run_status(
        self,
        run_id: uuid.UUID | str,
        *,
        status: RunStatus,
        metadata: Optional[dict[str, Any]] = None,
    ) -> RunRecord:
        rid = _run_uuid_from_external(run_id)
        now = _utcnow()
        with Session(self._engine) as session:
            existing = session.get(RunRecord, rid)
            if existing is None:
                existing = RunRecord(
                    id=rid,
                    status=status,
                    start_time=now,
                    end_time=now if status in {RunStatus.COMPLETED, RunStatus.FAILED} else None,
                    metadata_=(metadata or {}),
                )
                session.add(existing)
                session.commit()
                session.refresh(existing)
                session.expunge(existing)
                return existing

            existing.status = status
            if existing.start_time is None:
                existing.start_time = now
            if status in {RunStatus.COMPLETED, RunStatus.FAILED}:
                existing.end_time = now
            if metadata is not None:
                merged = dict(existing.metadata_ or {})
                merged.update(metadata)
                existing.metadata_ = merged
            session.add(existing)
            session.commit()
            session.refresh(existing)
            session.expunge(existing)
            return existing

    def list_recent_runs(self, *, limit: int = 30) -> list[RunRecord]:
        stmt = select(RunRecord).order_by(RunRecord.start_time.desc()).limit(int(limit))
        with Session(self._engine) as session:
            rows = list(session.exec(stmt).all())
            for r in rows:
                session.expunge(r)
            return rows

    def list_runs_by_status(self, status: RunStatus) -> list[RunRecord]:
        stmt = select(RunRecord).where(RunRecord.status == status)
        with Session(self._engine) as session:
            rows = list(session.exec(stmt).all())
            for r in rows:
                session.expunge(r)
            return rows

    def bulk_update(self, records: list[RunRecord]) -> int:
        if not records:
            return 0
        with Session(self._engine) as session:
            for r in records:
                session.merge(r)
            session.commit()
            return len(records)
