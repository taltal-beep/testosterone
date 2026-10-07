"""Pytest hooks for ``sample_target_repo``.

Provides the FastAPI ``TestClient`` used by ``tests/flow/test_api_flow.py``.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from mock_api import app
from starlette.testclient import TestClient


@pytest.fixture
def client() -> Iterator[TestClient]:
    """In-process ASGI client for HTTP flow tests."""

    with TestClient(app) as test_client:
        yield test_client
