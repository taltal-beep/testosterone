from __future__ import annotations

from dataclasses import dataclass, field
import threading

from fastapi.testclient import TestClient

from testo_api.main import create_app


@dataclass
class _FakeState:
    execution_id: str
    status: str = "queued"
    summary: dict | None = None
    error: str | None = None
    lock: threading.Lock = field(default_factory=threading.Lock)


class _FakeManager:
    def __init__(self, *, status: str = "running") -> None:
        self.state = _FakeState(execution_id="exec-1", status=status)

    def create_execution(self, request_model):  # noqa: ANN001
        del request_model
        return self.state

    def get(self, execution_id: str):  # noqa: ANN001
        return self.state if execution_id == "exec-1" else None

    def read_events_since(self, execution_id: str, offset: int):  # noqa: ANN001
        del execution_id, offset
        return [], 0, True


def _client(*, manager_status: str = "running") -> TestClient:
    app = create_app()
    manager = _FakeManager(status=manager_status)
    app.dependency_overrides.clear()
    from testo_api.dependencies import get_execution_manager

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
    assert payload["status"] == "queued"
    assert payload["events_url"].endswith("/api/v1/executions/exec-1/events")
    assert payload["summary_url"].endswith("/api/v1/executions/exec-1")


def test_create_execution_acceptance_status_is_stable_after_fast_completion() -> None:
    client = _client(manager_status="completed")
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
    assert resp.json()["status"] == "queued"


def test_get_execution_not_found() -> None:
    client = _client()
    resp = client.get("/api/v1/executions/missing")
    assert resp.status_code == 404
