from __future__ import annotations

from dataclasses import dataclass, field
import threading

from fastapi.testclient import TestClient

from uqo_api.main import create_app


@dataclass
class _FakeState:
    execution_id: str
    status: str = "queued"
    summary: dict | None = None
    error: str | None = None
    lock: threading.Lock = field(default_factory=threading.Lock)


class _FakeManager:
    def __init__(self) -> None:
        self.state = _FakeState(execution_id="exec-1", status="running")

    def create_execution(self, request_model):  # noqa: ANN001
        del request_model
        return self.state

    def get(self, execution_id: str):  # noqa: ANN001
        return self.state if execution_id == "exec-1" else None

    def read_events_since(self, execution_id: str, offset: int):  # noqa: ANN001
        del execution_id, offset
        return [], 0, True


def _client() -> TestClient:
    app = create_app()
    manager = _FakeManager()
    app.dependency_overrides.clear()
    from uqo_api.dependencies import get_execution_manager

    app.dependency_overrides[get_execution_manager] = lambda: manager
    return TestClient(app)


def test_create_execution_contract_shape() -> None:
    client = _client()
    resp = client.post(
        "/api/v1/executions",
        json={
            "runs": [
                {
                    "test_type": "pytest",
                    "target_repo": ".",
                    "cli_args": ["-q"],
                }
            ],
            "persist": True,
            "trigger_source": "ui",
            "ci_mode": False,
        },
    )
    assert resp.status_code == 202
    payload = resp.json()
    assert set(payload.keys()) == {"execution_id", "status", "events_url", "summary_url"}
    assert payload["execution_id"] == "exec-1"
    assert payload["status"] in {"queued", "running"}
    assert payload["events_url"].endswith("/api/v1/executions/exec-1/events")
    assert payload["summary_url"].endswith("/api/v1/executions/exec-1")


def test_get_execution_not_found() -> None:
    client = _client()
    resp = client.get("/api/v1/executions/missing")
    assert resp.status_code == 404
