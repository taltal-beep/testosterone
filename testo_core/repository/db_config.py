"""Database URL resolution and SQLAlchemy engine factory (multi-dialect)."""

from __future__ import annotations

import os
import threading
from typing import Final
from urllib.parse import urlparse

from sqlalchemy.engine import Engine
from sqlmodel import SQLModel, create_engine

_DEFAULT_SQLITE_URL: Final[str] = "sqlite:///./testo_history.db"
SUPPORTED_DATABASE_DIALECTS: Final[frozenset[str]] = frozenset({"sqlite", "postgresql", "mysql"})


def _is_running_in_docker() -> bool:
    """Heuristic used widely in containers; safe fallback."""
    from pathlib import Path

    return Path("/.dockerenv").exists() or os.getenv("RUNNING_IN_DOCKER", "").lower() in {
        "1",
        "true",
        "yes",
    }


def _postgres_host() -> str:
    host = (os.getenv("POSTGRES_HOST") or "").strip()
    if host:
        return host
    return "testo-postgres" if _is_running_in_docker() else "localhost"


def resolve_database_url() -> str:
    """Return the active database URL.

    Resolution order:

    1. ``DATABASE_URL`` environment variable (recommended single source of truth).
    2. ``database.url`` from the discovered testosterone config (``testosterone.yaml`` /
       ``testosterone.yml`` / ``[tool.testosterone]`` in ``pyproject.toml`` under the current
       working directory), when set.
    3. Legacy Postgres: if ``POSTGRES_USER``, ``POSTGRES_PASSWORD``, and ``POSTGRES_DB`` are all
       non-empty, build ``postgresql+psycopg://...`` using ``POSTGRES_HOST`` / ``POSTGRES_PORT``
       (with docker-aware host default when host is unset).
    4. Default file-backed SQLite at ``sqlite:///./testo_history.db`` for sandbox / zero-config runs.
    """
    from pathlib import Path

    from testo_core.config.database_section import database_url_from_discovered_config

    explicit = (os.getenv("DATABASE_URL") or "").strip()
    if explicit:
        return explicit

    file_url = database_url_from_discovered_config(cwd=Path.cwd())
    if file_url:
        return file_url.strip()

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


def validate_database_url(url: str) -> str:
    """Validate database URL dialect and return normalized dialect."""
    dialect = _dialect(url)
    if dialect not in SUPPORTED_DATABASE_DIALECTS:
        allowed = ", ".join(sorted(SUPPORTED_DATABASE_DIALECTS))
        raise ValueError(
            f"Unsupported database dialect `{dialect}`. Supported dialects: {allowed}."
        )
    return dialect


# One engine (and so one connection pool) per database URL, kept until
# reset_engine_cache() disposes it. A plain dict rather than lru_cache: evicting
# an engine without dispose() would leave its pooled connections open.
_ENGINES: dict[str, Engine] = {}
_ENGINES_LOCK = threading.Lock()


def engine_kwargs(url: str) -> dict[str, object]:
    """``create_engine`` keyword arguments for ``url``'s dialect (shared by probes)."""
    dialect = urlparse(url).scheme.lower().split("+", 1)[0]
    if dialect == "sqlite":
        return {"connect_args": {"check_same_thread": False}}
    return {"pool_pre_ping": True}


def _build_engine(url: str) -> Engine:
    with _ENGINES_LOCK:
        engine = _ENGINES.get(url)
        if engine is None:
            validate_database_url(url)
            engine = create_engine(url, echo=False, **engine_kwargs(url))
            _ENGINES[url] = engine
        return engine


def get_engine() -> Engine:
    """Return the cached :class:`~sqlalchemy.engine.Engine` for the active database URL."""
    return _build_engine(resolve_database_url())


def create_db_and_tables() -> None:
    """Create all registered SQLModel tables on the active engine (idempotent)."""
    # Import registers ``RunRecord`` on ``SQLModel.metadata``.
    from testo_core.repository.models import (  # noqa: F401
        AuditEvent,
        FailureTriage,
        QueuedRun,
        ReportArchive,
        ResourceAction,
        ResourceItemRow,
        ResourceLease,
        ResourceWaiter,
        RunRecord,
        UserAccount,
    )

    SQLModel.metadata.create_all(get_engine())


def reset_engine_cache() -> None:
    """Dispose and forget the cached engine(s). Use in tests after changing ``DATABASE_URL``."""
    with _ENGINES_LOCK:
        engines = list(_ENGINES.values())
        _ENGINES.clear()
    for engine in engines:
        engine.dispose()
