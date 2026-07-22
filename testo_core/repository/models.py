"""SQLModel table definitions for run history (dialect-portable JSON metadata)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from sqlalchemy import JSON, Column, LargeBinary
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

_METADATA_JSON_COL = JSON().with_variant(JSONB(), "postgresql")


class RunStatus(str, Enum):
    """Lifecycle states persisted for each orchestration run."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class RunRecord(SQLModel, table=True):
    """
    Canonical DB record for run lifecycle.

    Notes:
    - We use a deterministic UUID derived from the external ``run_id`` (from env) so we can upsert
      without relying on a separate unique column.
    - ``metadata`` is stored as JSON (JSONB on PostgreSQL); Python attribute is ``metadata_`` to
      avoid clashing with SQLAlchemy's ``.metadata``.
    """

    # Streamlit hot-reload can import this module multiple times within the same process,
    # reusing the same SQLAlchemy MetaData instance. Allow redefining the table safely.
    __table_args__ = {"extend_existing": True}

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True, index=True)
    status: RunStatus = Field(default=RunStatus.PENDING, index=True)
    start_time: datetime | None = Field(default=None)
    end_time: datetime | None = Field(default=None)
    metadata_: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column("metadata", _METADATA_JSON_COL, nullable=False),
    )


class ReportArchive(SQLModel, table=True):
    """Stored Allure/JSON artifacts for a completed CLI cycle (zip payload).

    Denormalized counters support fast listing/filtering without unpacking ``artifact_bytes``.
    Existing deployments that created this table before these columns need a manual
    ``ALTER TABLE`` (Postgres/MySQL) or a fresh SQLite file for dev.
    """

    __table_args__ = {"extend_existing": True}

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True, index=True)
    cycle_name: str = Field(index=True, max_length=512)
    created_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC), index=True)
    exit_code: int = Field(default=0)
    summary_json: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column("summary_json", _METADATA_JSON_COL, nullable=False),
    )
    artifact_bytes: bytes = Field(sa_column=Column("artifact_bytes", LargeBinary, nullable=False))
    total_tests: int | None = Field(default=None, index=True)
    passed: int | None = Field(default=None)
    failed: int | None = Field(default=None)
    broken: int | None = Field(default=None)
    skipped: int | None = Field(default=None)
    unknown: int | None = Field(
        default=None,
        description="Sum of Allure unknown-status counts across per-stage result trees.",
    )
    allure_duration_ms: int | None = Field(
        default=None,
        description="Sum of per-result-tree duration spans from *-result.json timestamps.",
    )
    plan_duration_ms: int | None = Field(
        default=None,
        index=True,
        description="Wall time from plan_result.json duration_s when present.",
    )
