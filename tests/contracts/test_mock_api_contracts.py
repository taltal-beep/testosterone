from __future__ import annotations

from typing import Any

import pytest

from tests._allure_utils import step
from tests.contracts.models import (
    AdminResponse,
    CreateItemResponse,
    DeleteItemResponse,
    GetItemResponse,
    ItemsListResponse,
    LoginResponse,
    RootResponse,
    SecureResponse,
    SubmitResponse,
    UploadResponse,
)

pytestmark = [pytest.mark.contract]


def test_root_contract(fastapi_client) -> None:
    with step("GET /"):
        r = fastapi_client.get("/")
    assert r.status_code == 200
    RootResponse.model_validate(r.json())


@pytest.mark.parametrize(
    "username",
    [
        "alice",
        "bob",
        "",
        "   ",
        "ユーザー",
        "' OR '1'='1",
        "admin; DROP TABLE users; --",
    ],
)
def test_login_contract(username: str, fastapi_client) -> None:
    with step("POST /login"):
        r = fastapi_client.post("/login", json={"username": username})
    assert r.status_code == 200
    LoginResponse.model_validate(r.json())


def test_secure_contract_requires_bearer(fastapi_client) -> None:
    with step("GET /secure without Authorization header"):
        r = fastapi_client.get("/secure")
    assert r.status_code == 401


def test_secure_contract_success(fastapi_client, auth_headers: dict[str, str]) -> None:
    with step("GET /secure with bearer"):
        r = fastapi_client.get("/secure", headers=auth_headers)
    assert r.status_code == 200
    SecureResponse.model_validate(r.json())


def test_admin_contract_success(fastapi_client, auth_headers: dict[str, str]) -> None:
    with step("GET /admin with bearer"):
        r = fastapi_client.get("/admin", headers=auth_headers)
    assert r.status_code == 200
    AdminResponse.model_validate(r.json())


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"k": "v"},
        {"nested": {"a": 1, "b": True}},
        {"list": [1, "two", None, {"x": "y"}]},
        {"sqli": "' OR '1'='1"},
    ],
)
def test_submit_contract(payload: dict[str, Any], fastapi_client) -> None:
    with step("POST /submit"):
        r = fastapi_client.post("/submit", json=payload)
    assert r.status_code == 200
    SubmitResponse.model_validate(r.json())


def test_items_list_contract_empty(fastapi_client) -> None:
    with step("GET /items (empty)"):
        r = fastapi_client.get("/items")
    assert r.status_code == 200
    ItemsListResponse.model_validate(r.json())


@pytest.mark.parametrize(
    "name,meta",
    [
        ("n", {}),
        ("", {"k": "v"}),
        ("ユーザー", {"unicode": "✓"}),
        ("' OR '1'='1", {"attack": True}),
        ("x" * 256, {"long": True}),
    ],
)
def test_items_create_contract(name: str, meta: dict[str, Any], fastapi_client) -> None:
    with step("POST /items"):
        r = fastapi_client.post("/items", json={"name": name, "meta": meta})
    assert r.status_code == 200
    out = CreateItemResponse.model_validate(r.json())
    assert isinstance(out.item.id, int) and out.item.id >= 1


def test_items_get_contract_and_delete_contract(fastapi_client) -> None:
    with step("Create item"):
        c = fastapi_client.post("/items", json={"name": "x", "meta": {"a": 1}})
    assert c.status_code == 200
    created = CreateItemResponse.model_validate(c.json())
    item_id = created.item.id

    with step("GET /items/{id}"):
        g = fastapi_client.get(f"/items/{item_id}")
    assert g.status_code == 200
    GetItemResponse.model_validate(g.json())

    with step("DELETE /items/{id}"):
        d = fastapi_client.delete(f"/items/{item_id}")
    assert d.status_code == 200
    DeleteItemResponse.model_validate(d.json())


@pytest.mark.parametrize(
    "payload",
    [
        None,
        {"x": 1},
        {"deep": {"a": {"b": {"c": True}}}},
    ],
)
def test_upload_contract_payload_only(payload: dict[str, Any] | None, fastapi_client) -> None:
    with step("POST /upload (payload only)"):
        r = fastapi_client.post("/upload", json=payload)
    assert r.status_code == 200
    UploadResponse.model_validate(r.json())

