from __future__ import annotations

import pytest

from tests._allure_utils import step

pytestmark = [pytest.mark.e2e]


_JOURNEYS: list[tuple[str, str, str]] = [
    ("auth_resource_basic_01", "alice", "item-a"),
    ("auth_resource_basic_02", "bob", "item-b"),
    ("auth_resource_unicode_03", "ユーザー", "項目"),
    ("auth_resource_sqli_04", "' OR '1'='1", "x';--"),
    ("auth_resource_long_05", "x" * 128, "y" * 128),
    ("auth_resource_empty_06", "", ""),
    ("auth_resource_space_07", "   ", "   "),
    ("auth_resource_quotes_08", "\"'`", "\"'`"),
    ("auth_resource_pathlike_09", "../etc/passwd", "../tmp"),
    ("auth_resource_jsonlike_10", '{"u":"x"}', '{"n":"y"}'),
    ("auth_resource_basic_11", "charlie", "item-c"),
    ("auth_resource_basic_12", "diana", "item-d"),
    ("auth_resource_basic_13", "eve", "item-e"),
    ("auth_resource_basic_14", "frank", "item-f"),
    ("auth_resource_basic_15", "grace", "item-g"),
    ("auth_resource_basic_16", "heidi", "item-h"),
    ("auth_resource_basic_17", "ivan", "item-i"),
    ("auth_resource_basic_18", "judy", "item-j"),
    ("auth_resource_basic_19", "mallory", "item-m"),
    ("auth_resource_basic_20", "oscar", "item-o"),
]


@pytest.mark.parametrize("journey_id,username,item_name", _JOURNEYS, ids=lambda x: x if isinstance(x, str) else str(x))
def test_full_user_journey(journey_id: str, username: str, item_name: str, fastapi_client) -> None:
    """
    E2E journey (sequential & stateful within the test):
      Signup/verify not implemented in mock API; we treat `/login` as issuance.
      Login -> Secure -> Admin -> Resource create -> read -> list -> delete -> post-delete 404
      Token tamper -> Secure should reject
    """
    with step(f"[{journey_id}] Login"):
        login = fastapi_client.post("/login", json={"username": username})
    assert login.status_code == 200
    token = login.json().get("token")
    assert isinstance(token, str) and token
    headers = {"Authorization": f"Bearer {token}"}

    with step(f"[{journey_id}] Secure access"):
        sec = fastapi_client.get("/secure", headers=headers)
    assert sec.status_code == 200

    with step(f"[{journey_id}] Admin access + claims"):
        adm = fastapi_client.get("/admin", headers=headers)
    assert adm.status_code == 200
    claims = adm.json().get("claims") or {}
    assert isinstance(claims.get("sub"), str)

    with step(f"[{journey_id}] Create resource"):
        c = fastapi_client.post("/items", json={"name": item_name, "meta": {"journey": journey_id}})
    assert c.status_code == 200
    item_id = int(c.json()["item"]["id"])

    with step(f"[{journey_id}] Read resource"):
        g = fastapi_client.get(f"/items/{item_id}")
    assert g.status_code == 200
    assert int(g.json()["item"]["id"]) == item_id

    with step(f"[{journey_id}] List resources"):
        lst = fastapi_client.get("/items")
    assert lst.status_code == 200
    assert any(int(i["id"]) == item_id for i in lst.json().get("items", []))

    with step(f"[{journey_id}] Delete resource"):
        d = fastapi_client.delete(f"/items/{item_id}")
    assert d.status_code == 200

    with step(f"[{journey_id}] Verify resource is gone"):
        gone = fastapi_client.get(f"/items/{item_id}")
    assert gone.status_code == 404

    with step(f"[{journey_id}] Token tamper should be rejected"):
        bad = {"Authorization": f"Bearer {token}x"}
        rej = fastapi_client.get("/secure", headers=bad)
    assert rej.status_code == 401

