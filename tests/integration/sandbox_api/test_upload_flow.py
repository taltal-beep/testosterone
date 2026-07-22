from __future__ import annotations

from io import BytesIO

import pytest

from tests._allure_utils import step

pytestmark = [pytest.mark.integration]


@pytest.mark.parametrize(
    "payload",
    [
        None,
        {},
        {"k": "v"},
        {"nested": {"a": 1}},
        {"sqli": "' OR '1'='1"},
    ],
)
def test_upload_payload_only(payload, fastapi_client) -> None:
    with step("POST /upload payload-only"):
        r = fastapi_client.post("/upload", json=payload)
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert isinstance(body["delay_ms"], int)
    assert isinstance(body["size"], int)


def test_upload_file_only(monkeypatch: pytest.MonkeyPatch, mock_api_app, api_recorder, fastapi_client) -> None:
    # Use underlying TestClient for multipart; `fastapi_client` wrapper is JSON-oriented.
    from fastapi.testclient import TestClient  # type: ignore

    client = TestClient(mock_api_app)
    content = b"abc" * 10
    with step("POST /upload file-only multipart"):
        r = client.post("/upload", files={"file": ("f.bin", BytesIO(content), "application/octet-stream")})
    assert r.status_code == 200
    j = r.json()
    assert j["size"] >= len(content)

