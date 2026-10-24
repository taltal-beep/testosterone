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

    # A reloader (``testo-api`` with TESTO_API_RELOAD=1) can import this module twice in one process,
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


class QueuedRun(SQLModel, table=True):
    """An API run waiting for a worker, kept only when ``TESTO_RUN_QUEUE=db``.

    The row is deleted when a worker starts the run, so the table only ever holds
    runs that have not started. ``request_json`` is ``testo_api.run_queue.RunRequest``.
    """

    __tablename__ = "queued_run"
    __table_args__ = {"extend_existing": True}

    id: str = Field(primary_key=True, max_length=64)
    cycle: str = Field(index=True, max_length=512)
    created_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC), index=True)
    request_json: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column("request_json", _METADATA_JSON_COL, nullable=False),
    )


class UserAccount(SQLModel, table=True):
    """A team server account, used only when ``TESTO_AUTH=accounts``.

    ``password_hash`` is ``scrypt$<n>$<r>$<p>$<salt hex>$<hash hex>``. Bumping
    ``session_version`` signs the user out of every browser.
    """

    __tablename__ = "user_account"
    __table_args__ = {"extend_existing": True}

    username: str = Field(primary_key=True, max_length=64)
    password_hash: str = Field(max_length=512)
    role: str = Field(default="viewer", max_length=16)
    session_version: int = Field(default=1)
    created_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))


class AuditEvent(SQLModel, table=True):
    """One write to the API by a signed-in user (``TESTO_AUTH=accounts``)."""

    __tablename__ = "audit_event"
    __table_args__ = {"extend_existing": True}

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC), index=True)
    username: str = Field(index=True, max_length=64)
    method: str = Field(max_length=8)
    path: str = Field(max_length=1024)
    status: int = Field(default=0)
