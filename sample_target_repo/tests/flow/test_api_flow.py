"""Flow tests for ``mock_api`` over an in-process ``TestClient``.

The flow lane covers HTTP behavior end-to-end without spinning up uvicorn:
auth, items CRUD, and the deliberately flaky/chaotic endpoints. Non-
deterministic and slow endpoints (``/flaky``, ``/chaos``, ``/upload``,
``/slow``) are made deterministic with focused monkeypatches so the
suite stays fast and stable in the ``flow`` plan.
"""

from __future__ import annotations

import types
from collections.abc import Awaitable, Callable
from typing import Any

import mock_api
import pytest
from starlette.testclient import TestClient


async def _no_sleep(*_args: Any, **_kwargs: Any) -> None:
    """Drop-in replacement for :func:`asyncio.sleep` used by mock_api."""

    return None


@pytest.fixture
def fast_sleep(monkeypatch: pytest.MonkeyPatch) -> Callable[..., Awaitable[None]]:
    """Replace ``mock_api.asyncio`` so awaited sleeps return immediately.

    We swap out only the attribute mock_api looks up at call time, so the
    rest of the test framework (anyio, starlette, etc.) keeps using the
    real :mod:`asyncio` module.
    """

    fake_asyncio = types.SimpleNamespace(sleep=_no_sleep)
    monkeypatch.setattr(mock_api, "asyncio", fake_asyncio)
    return _no_sleep


# ---------------------------------------------------------------------------
# Root & health (2)
# ---------------------------------------------------------------------------


@pytest.mark.flow
def test_root_returns_ok_status(client: TestClient) -> None:
    r = client.get("/")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


@pytest.mark.flow
def test_root_returns_hello_world_message(client: TestClient) -> None:
    r = client.get("/")
    assert r.json()["message"] == "Hello World"


# ---------------------------------------------------------------------------
# Auth — /login, /secure, /admin (3 + 1 + 1 + 1 + 1 + 1 + 1 = 9)
# ---------------------------------------------------------------------------


@pytest.mark.flow
@pytest.mark.parametrize("username", ["alice", "bob", "charlie"])
def test_login_returns_token_for_username(client: TestClient, username: str) -> None:
    r = client.post("/login", json={"username": username})
    assert r.status_code == 200
    token = r.json()["token"]
    assert isinstance(token, str) and token


@pytest.mark.flow
def test_login_uses_default_user_when_username_missing(client: TestClient) -> None:
    r = client.post("/login", json={})
    assert r.status_code == 200
    assert isinstance(r.json()["token"], str)


@pytest.mark.flow
def test_secure_without_auth_header_returns_401(client: TestClient) -> None:
    r = client.get("/secure")
    assert r.status_code == 401


@pytest.mark.flow
def test_secure_with_invalid_bearer_token_returns_401(client: TestClient) -> None:
    r = client.get("/secure", headers={"Authorization": "Bearer not-a-token"})
    assert r.status_code == 401


@pytest.mark.flow
def test_secure_with_valid_bearer_token_returns_secure_true(client: TestClient) -> None:
    token = client.post("/login", json={"username": "alice"}).json()["token"]
    r = client.get("/secure", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["secure"] is True


@pytest.mark.flow
def test_admin_with_valid_token_returns_claims(client: TestClient) -> None:
    token = client.post("/login", json={"username": "alice"}).json()["token"]
    r = client.get("/admin", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    body = r.json()
    assert body["admin"] is True
    assert body["claims"]["sub"] == "alice"


@pytest.mark.flow
def test_admin_without_auth_header_returns_401(client: TestClient) -> None:
    r = client.get("/admin")
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# /error & /submit (1 + 2 = 3)
# ---------------------------------------------------------------------------


@pytest.mark.flow
def test_error_endpoint_returns_500(client: TestClient) -> None:
    r = client.get("/error")
    assert r.status_code == 500


@pytest.mark.flow
@pytest.mark.parametrize(
    "payload",
    [
        {"a": 1},
        {"x": "y", "z": [1, 2]},
    ],
)
def test_submit_echoes_payload(
    client: TestClient, payload: dict[str, Any]
) -> None:
    r = client.post("/submit", json=payload)
    assert r.status_code == 200
    body = r.json()
    assert body["received"] is True
    assert body["payload"] == payload


# ---------------------------------------------------------------------------
# Items CRUD (8)
# ---------------------------------------------------------------------------


@pytest.mark.flow
def test_items_list_initially_empty(client: TestClient) -> None:
    r = client.get("/items")
    assert r.status_code == 200
    assert r.json()["items"] == []


@pytest.mark.flow
def test_items_create_assigns_sequential_ids(client: TestClient) -> None:
    r1 = client.post("/items", json={"name": "a"})
    r2 = client.post("/items", json={"name": "b"})
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r1.json()["item"]["id"] == 1
    assert r2.json()["item"]["id"] == 2


@pytest.mark.flow
def test_items_create_defaults_name_when_missing(client: TestClient) -> None:
    r = client.post("/items", json={})
    assert r.status_code == 200
    assert r.json()["item"]["name"].startswith("item-")


@pytest.mark.flow
def test_items_get_returns_existing_item(client: TestClient) -> None:
    new_id = client.post("/items", json={"name": "alpha"}).json()["item"]["id"]
    r = client.get(f"/items/{new_id}")
    assert r.status_code == 200
    assert r.json()["item"]["name"] == "alpha"


@pytest.mark.flow
def test_items_get_unknown_id_returns_404(client: TestClient) -> None:
    r = client.get("/items/9999")
    assert r.status_code == 404


@pytest.mark.flow
def test_items_delete_existing_returns_deleted_true(client: TestClient) -> None:
    new_id = client.post("/items", json={"name": "alpha"}).json()["item"]["id"]
    r = client.delete(f"/items/{new_id}")
    assert r.status_code == 200
    assert r.json()["deleted"] is True


@pytest.mark.flow
def test_items_delete_unknown_id_returns_404(client: TestClient) -> None:
    r = client.delete("/items/9999")
    assert r.status_code == 404


@pytest.mark.flow
def test_items_full_crud_flow_round_trip(client: TestClient) -> None:
    created = client.post("/items", json={"name": "alpha", "meta": {"n": 1}})
    item_id = created.json()["item"]["id"]
    assert client.get(f"/items/{item_id}").status_code == 200
    assert client.delete(f"/items/{item_id}").status_code == 200
    assert client.get(f"/items/{item_id}").status_code == 404


# ---------------------------------------------------------------------------
# /flaky & /chaos — deterministic via monkeypatched random (2 + 4 = 6)
# ---------------------------------------------------------------------------


@pytest.mark.flow
def test_flaky_succeeds_when_random_above_threshold(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(mock_api.random, "random", lambda: 0.99)
    r = client.get("/flaky")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


@pytest.mark.flow
def test_flaky_fails_when_random_below_threshold(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(mock_api.random, "random", lambda: 0.01)
    r = client.get("/flaky")
    assert r.status_code == 500


@pytest.mark.flow
def test_chaos_normal_path(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(mock_api.random, "random", lambda: 0.99)
    r = client.get("/chaos")
    assert r.status_code == 200
    assert r.json()["mode"] == "normal"


@pytest.mark.flow
def test_chaos_high_latency_path(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    fast_sleep: Callable[..., Awaitable[None]],
) -> None:
    monkeypatch.setattr(mock_api.random, "random", lambda: 0.01)
    monkeypatch.setattr(mock_api.random, "uniform", lambda a, _b: a)
    r = client.get("/chaos")
    assert r.status_code == 200
    assert r.json()["mode"] == "high_latency"


@pytest.mark.flow
def test_chaos_unauthorized_path(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(mock_api.random, "random", lambda: 0.20)
    r = client.get("/chaos")
    assert r.status_code == 401


@pytest.mark.flow
def test_chaos_server_error_path(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(mock_api.random, "random", lambda: 0.40)
    r = client.get("/chaos")
    assert r.status_code == 500


# ---------------------------------------------------------------------------
# /upload & /slow — deterministic via fast_sleep / uniform patch (2)
# ---------------------------------------------------------------------------


@pytest.mark.flow
def test_upload_with_file_reports_size(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    fast_sleep: Callable[..., Awaitable[None]],
) -> None:
    monkeypatch.setattr(mock_api.random, "uniform", lambda _a, _b: 0.05)
    files = {"file": ("test.txt", b"hello world")}
    r = client.post("/upload", files=files)
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["size"] == len(b"hello world")


@pytest.mark.flow
def test_slow_endpoint_returns_ok(
    client: TestClient, fast_sleep: Callable[..., Awaitable[None]]
) -> None:
    r = client.get("/slow")
    assert r.status_code == 200
    assert r.json()["message"] == "slow"
