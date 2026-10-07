"""Contract for the API's optional bearer token and CORS defaults (``testo_api/security.py``)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from testo_api.main import create_app
from testo_api.security import is_loopback_host

_ADHOC = "/api/v1/adhoc-executions"


class _FakeManager:
    def __init__(self) -> None:
        self.calls = 0

    def create_adhoc_execution(self, **_kwargs):  # noqa: ANN003
        self.calls += 1
        raise AssertionError("auth should have rejected this request first")


def _client(manager: _FakeManager | None = None) -> TestClient:
    from testo_api.dependencies import get_cycle_execution_manager

    app = create_app()
    if manager is not None:
        app.dependency_overrides[get_cycle_execution_manager] = lambda: manager
    return TestClient(app)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("TESTO_API_TOKEN", "TESTO_CORS_ORIGINS", "UQO_API_CORS_ORIGINS"):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def token(monkeypatch: pytest.MonkeyPatch) -> str:
    monkeypatch.setenv("TESTO_API_TOKEN", "s3cret")
    return "s3cret"


@pytest.mark.parametrize("header", [None, "Bearer wrong", "Basic s3cret", "s3cret"])
def test_mutating_request_without_valid_token_is_401(token: str, header: str | None) -> None:
    manager = _FakeManager()
    headers = {"Authorization": header} if header else {}
    resp = _client(manager).post(_ADHOC, json={"framework": "pytest"}, headers=headers)
    assert resp.status_code == 401
    assert resp.headers["WWW-Authenticate"] == "Bearer"
    assert resp.json()["error"]["code"] == "unauthorized"
    assert manager.calls == 0


def test_mutating_request_with_token_reaches_the_route(token: str) -> None:
    # An empty body fails validation, which proves auth let the request through.
    resp = _client().post(_ADHOC, json={}, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 422


def test_reads_stay_open_with_token_set(token: str) -> None:
    assert _client().get("/api/v1/health/live").status_code == 200


def test_no_token_configured_means_no_auth() -> None:
    assert _client().post(_ADHOC, json={}).status_code == 422


def test_foreign_origin_cannot_mutate_even_without_token() -> None:
    # A cross-site "simple" POST skips the CORS preflight, so the server must refuse it itself.
    manager = _FakeManager()
    client = _client(manager)
    resp = client.post(_ADHOC, json={}, headers={"Origin": "https://evil.example"})
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "forbidden"
    assert manager.calls == 0
    allowed = client.post(_ADHOC, json={}, headers={"Origin": "http://localhost:5173"})
    assert allowed.status_code == 422
    # Reads from any origin stay open (CORS still decides whether the browser may see them).
    read = client.get("/api/v1/health/live", headers={"Origin": "https://evil.example"})
    assert read.status_code == 200


def test_token_tolerates_surrounding_whitespace_in_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TESTO_API_TOKEN", "s3cret\n")
    resp = _client().post(_ADHOC, json={}, headers={"Authorization": "Bearer s3cret"})
    assert resp.status_code == 422


def _preflight(client: TestClient, origin: str):  # noqa: ANN202
    return client.options(
        _ADHOC,
        headers={"Origin": origin, "Access-Control-Request-Method": "POST"},
    )


def test_cors_defaults_to_vite_dev_server_without_credentials() -> None:
    client = _client()
    allowed = _preflight(client, "http://localhost:5173")
    assert allowed.status_code == 200
    assert allowed.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert "access-control-allow-credentials" not in allowed.headers
    denied = _preflight(client, "https://evil.example")
    assert denied.status_code == 400
    assert "access-control-allow-origin" not in denied.headers


def test_cors_explicit_origins_allow_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TESTO_CORS_ORIGINS", "https://qa.internal, http://localhost:4173")
    client = _client()
    resp = _preflight(client, "https://qa.internal")
    assert resp.headers["access-control-allow-origin"] == "https://qa.internal"
    assert resp.headers["access-control-allow-credentials"] == "true"
    assert _preflight(client, "http://localhost:5173").status_code == 400


def test_cors_wildcard_never_allows_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TESTO_CORS_ORIGINS", "*")
    resp = _preflight(_client(), "https://anywhere.example")
    assert resp.headers["access-control-allow-origin"] == "*"
    assert "access-control-allow-credentials" not in resp.headers


@pytest.mark.parametrize(
    ("host", "loopback"),
    [
        ("127.0.0.1", True),
        ("localhost", True),
        ("::1", True),
        ("[::1]", True),
        ("0.0.0.0", False),
        ("myhost", False),
    ],
)
def test_is_loopback_host(host: str, loopback: bool) -> None:
    assert is_loopback_host(host) is loopback
