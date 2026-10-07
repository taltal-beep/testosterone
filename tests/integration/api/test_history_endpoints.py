from __future__ import annotations

from fastapi.testclient import TestClient

from testo_api.main import create_app


def test_health_endpoints(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setenv("MINIO_ENDPOINT", "http://127.0.0.1:9000")
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


def test_readiness_ignores_minio_when_it_is_not_configured(monkeypatch) -> None:  # noqa: ANN001
    for name in ("MINIO_ENDPOINT", "MINIO_ROOT_USER", "MINIO_ROOT_PASSWORD"):
        monkeypatch.delenv(name, raising=False)
    client = TestClient(create_app())

    payload = client.get("/api/v1/health/ready").json()

    assert "s3" not in payload["checks"]
