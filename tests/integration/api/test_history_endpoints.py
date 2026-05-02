from __future__ import annotations

from fastapi.testclient import TestClient

from uqo_api.main import create_app


def test_health_endpoints() -> None:
    client = TestClient(create_app())
    live = client.get("/api/v1/health/live")
    assert live.status_code == 200
    assert live.json()["status"] == "ok"

    ready = client.get("/api/v1/health/ready")
    assert ready.status_code in {200, 503}
    payload = ready.json()
    assert set(payload.keys()) == {"status", "checks"}
    assert "db" in payload["checks"]
    assert "repository" in payload["checks"]
    assert "s3" in payload["checks"]
