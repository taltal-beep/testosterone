"""SQLModel table definitions for run history (dialect-portable JSON metadata)."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from sqlalchemy import JSON, Column
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
    start_time: Optional[datetime] = Field(default=None)
    end_time: Optional[datetime] = Field(default=None)
    metadata_: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column("metadata", _METADATA_JSON_COL, nullable=False),
    )
