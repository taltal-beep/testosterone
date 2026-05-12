"""Database wiring for mock API integration tests.

Reads ``database.url`` from the repository ``testosterone.yaml`` (same discovery rules as
``testo run``) when ``DATABASE_URL`` is not already set. Ensures tables exist so code paths that
touch ``testo_core.db`` / run history behave like production without requiring manual env setup.

Chaos / flakiness (mock API tests only, including unit ``test_sandbox_api*.py``): set
``SANDBOX_API_FLAKY_P=0.07`` (see root ``tests/conftest.py``).
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="session", autouse=True)
def _configure_database_url_for_sandbox_integration() -> None:
    if not os.getenv("DATABASE_URL", "").strip():
        from testo_core.config.database_section import database_url_from_discovered_config
        from testo_core.db import reset_repository_cache
        from testo_core.db_config import create_db_and_tables, reset_engine_cache

        url = database_url_from_discovered_config(cwd=_REPO_ROOT)
        if not url:
            db_path = _REPO_ROOT / "artifacts" / "testo_sandbox.db"
            db_path.parent.mkdir(parents=True, exist_ok=True)
            url = f"sqlite:///{db_path.resolve()}"

        os.environ["DATABASE_URL"] = url
        reset_engine_cache()
        reset_repository_cache()
        create_db_and_tables()

    yield
