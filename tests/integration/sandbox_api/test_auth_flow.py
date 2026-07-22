from __future__ import annotations

import pytest

from tests._allure_utils import step

pytestmark = [pytest.mark.integration]


def test_login_then_secure_then_admin(fastapi_client, auth_headers: dict[str, str]) -> None:
    with step("GET /secure"):
        s = fastapi_client.get("/secure", headers=auth_headers)
    assert s.status_code == 200
    assert s.json().get("secure") is True

    with step("GET /admin"):
        a = fastapi_client.get("/admin", headers=auth_headers)
    assert a.status_code == 200
    claims = a.json().get("claims") or {}
    assert isinstance(claims.get("sub"), str)


@pytest.mark.parametrize("auth_header", [None, "", "Bearer", "Bearer ", "Basic abc", "bearer not-a-jwt"])
def test_secure_rejects_invalid_bearer(auth_header: str | None, fastapi_client) -> None:
    headers = {}
    if auth_header is not None:
        headers["Authorization"] = auth_header
    with step("GET /secure invalid bearer"):
        r = fastapi_client.get("/secure", headers=headers)
    assert r.status_code == 401

