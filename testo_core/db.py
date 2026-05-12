"""Service locator for the process-wide :class:`~testo_core.repository.base.BaseRunRepository`."""

from __future__ import annotations

from functools import lru_cache

from testo_core.db_config import create_db_and_tables, get_engine, resolve_database_url
from testo_core.repository.base import BaseRunRepository
from testo_core.repository.factory import create_repository_for_url
from testo_core.repository.report_archive_repository import SQLReportArchiveRepository


@lru_cache(maxsize=1)
def get_repository() -> BaseRunRepository:
    """Return the cached repository for the active :func:`~testo_core.db_config.resolve_database_url`."""
    url = resolve_database_url()
    create_db_and_tables()
    return create_repository_for_url(url=url, engine=get_engine())


@lru_cache(maxsize=1)
def get_report_archive_repository() -> SQLReportArchiveRepository:
    """Return the cached :class:`SQLReportArchiveRepository` for the active database URL."""
    create_db_and_tables()
    return SQLReportArchiveRepository(get_engine())


def reset_repository_cache() -> None:
    """Clear the cached repository. Use in tests after changing database configuration."""
    get_repository.cache_clear()
    get_report_archive_repository.cache_clear()
