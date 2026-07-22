"""Pytest hooks for ``sample_target_repo``.

Provides the FastAPI ``TestClient`` used by ``tests/flow/test_api_flow.py`` and
opt-in random failure injection via ``TESTO_SAMPLE_RANDOM_FAIL_P``; see
``random_fail.roll_fail``.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from mock_api import app
from random_fail import roll_fail
from starlette.testclient import TestClient


@pytest.fixture
def client() -> Iterator[TestClient]:
    """In-process ASGI client for HTTP flow tests."""

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def _inject_random_failure(request: pytest.FixtureRequest) -> None:
    roll_fail(f"pytest:{request.node.nodeid}")
