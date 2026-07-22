from __future__ import annotations

import sys
from typing import Any

import pytest

from tests._allure_utils import step

pytestmark = [pytest.mark.integration]


@pytest.fixture
def mock_api_module(mock_api_app):
    module = sys.modules.get("uqo_sample_mock_api")
    assert module is not None
    return module


@pytest.mark.parametrize(
    "random_value,expected_status,expected_body",
    [
        (0.10, 200, {"status": "ok", "mode": "high_latency", "delay_ms": 3456}),
        (0.20, 401, {"detail": "chaos unauthorized"}),
        (0.40, 500, {"detail": "chaos server error"}),
        (0.75, 200, {"status": "ok", "mode": "normal", "delay_ms": 0}),
    ],
)
def test_chaos_endpoint_branches_are_deterministic(
    monkeypatch: pytest.MonkeyPatch,
    mock_api_module,
    fastapi_client,
    random_value: float,
    expected_status: int,
    expected_body: dict[str, Any],
) -> None:
    async def fake_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr(mock_api_module.random, "random", lambda: random_value)
    monkeypatch.setattr(mock_api_module.random, "uniform", lambda _start, _end: 3.456)
    monkeypatch.setattr(mock_api_module.asyncio, "sleep", fake_sleep)

    with step(f"GET /chaos with random={random_value}"):
        response = fastapi_client.get("/chaos")

    assert response.status_code == expected_status
    assert response.json() == expected_body
