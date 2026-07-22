from __future__ import annotations

import pytest

from tests._allure_utils import step

pytestmark = [pytest.mark.integration]


def test_items_lifecycle_create_get_list_delete(fastapi_client) -> None:
    with step("POST /items create"):
        c = fastapi_client.post("/items", json={"name": "alpha", "meta": {"v": 1}})
    assert c.status_code == 200
    item = c.json()["item"]
    item_id = int(item["id"])

    with step("GET /items/{id}"):
        g = fastapi_client.get(f"/items/{item_id}")
    assert g.status_code == 200
    assert g.json()["item"]["id"] == item_id

    with step("GET /items list contains created"):
        lst = fastapi_client.get("/items")
    assert lst.status_code == 200
    assert any(int(i["id"]) == item_id for i in lst.json().get("items", []))

    with step("DELETE /items/{id}"):
        d = fastapi_client.delete(f"/items/{item_id}")
    assert d.status_code == 200
    assert d.json()["deleted"] is True

    with step("GET deleted item returns 404"):
        g2 = fastapi_client.get(f"/items/{item_id}")
    assert g2.status_code == 404


@pytest.mark.parametrize("bad_id", [0, -1, 999999])
def test_get_missing_item_is_404(bad_id: int, fastapi_client) -> None:
    with step(f"GET /items/{bad_id} missing"):
        r = fastapi_client.get(f"/items/{bad_id}")
    assert r.status_code == 404

