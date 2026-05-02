"""Database URL resolution and SQLAlchemy engine factory (multi-dialect)."""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Final
from urllib.parse import urlparse

from sqlalchemy.engine import Engine
from sqlmodel import SQLModel, create_engine

_DEFAULT_SQLITE_URL: Final[str] = "sqlite:///./uqo_history.db"


def _is_running_in_docker() -> bool:
    """Heuristic used widely in containers; safe fallback."""
    from pathlib import Path

    return Path("/.dockerenv").exists() or os.getenv("RUNNING_IN_DOCKER", "").lower() in {"1", "true", "yes"}


def _postgres_host() -> str:
    host = (os.getenv("POSTGRES_HOST") or "").strip()
    if host:
        return host
    return "uqo-postgres" if _is_running_in_docker() else "localhost"


def resolve_database_url() -> str:
    """Return the active database URL.

    Resolution order:

    1. ``DATABASE_URL`` environment variable (recommended single source of truth).
    2. Legacy Postgres: if ``POSTGRES_USER``, ``POSTGRES_PASSWORD``, and ``POSTGRES_DB`` are all
       non-empty, build ``postgresql+psycopg://...`` using ``POSTGRES_HOST`` / ``POSTGRES_PORT``
       (with docker-aware host default when host is unset).
    3. Default file-backed SQLite at ``sqlite:///./uqo_history.db`` for sandbox / zero-config runs.
    """
    explicit = (os.getenv("DATABASE_URL") or "").strip()
    if explicit:
        return explicit

    user = (os.getenv("POSTGRES_USER") or "").strip()
    pwd = (os.getenv("POSTGRES_PASSWORD") or "").strip()
    db = (os.getenv("POSTGRES_DB") or "").strip()
    if user and pwd and db:
        host = (os.getenv("POSTGRES_HOST") or "").strip() or _postgres_host()
        port = (os.getenv("POSTGRES_PORT") or "5432").strip()
        return f"postgresql+psycopg://{user}:{pwd}@{host}:{port}/{db}"

    return _DEFAULT_SQLITE_URL


def _dialect(url: str) -> str:
    """Return the SQLAlchemy dialect name (e.g. ``sqlite``, ``postgresql``, ``mysql``)."""
    scheme = urlparse(url).scheme.lower()
    return scheme.split("+", 1)[0]


@lru_cache(maxsize=8)
def _build_engine(url: str) -> Engine:
    dialect = _dialect(url)
    kwargs: dict[str, object] = {"echo": False}

    if dialect == "sqlite":
        kwargs["connect_args"] = {"check_same_thread": False}
    else:
        kwargs["pool_pre_ping"] = True

    return create_engine(url, **kwargs)


def get_engine() -> Engine:
    """Return the cached :class:`~sqlalchemy.engine.Engine` for the active database URL."""
    return _build_engine(resolve_database_url())


def create_db_and_tables() -> None:
    """Create all registered SQLModel tables on the active engine (idempotent)."""
    # Import registers ``RunRecord`` on ``SQLModel.metadata``.
    from uqo_core.repository.models import RunRecord  # noqa: F401

    SQLModel.metadata.create_all(get_engine())


def reset_engine_cache() -> None:
    """Clear the cached engine(s). Use in tests after changing ``DATABASE_URL``."""
    _build_engine.cache_clear()
