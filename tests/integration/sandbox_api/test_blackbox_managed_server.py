from __future__ import annotations

import pytest
import requests

from tests._allure_utils import step

pytestmark = [pytest.mark.integration]


@pytest.fixture
def managed_requests_client(sandbox_server: str, api_recorder):
    class _Req:
        def request(self, method: str, path: str, *, json=None, headers=None, timeout: float | None = None):
            url = f"{sandbox_server}{path}"
            hdrs = dict(headers or {})
            try:
                r = requests.request(method, url, json=json, headers=hdrs, timeout=timeout or 5)
            except Exception as exc:
                api_recorder.record(
                    method=method.upper(),
                    url=url,
                    request_json=json,
                    request_headers=hdrs,
                    status_code=None,
                    response_json=None,
                    response_text=str(exc),
                    response_headers={},
                )
                raise

            try:
                rj = r.json()
            except Exception:
                rj = None
            api_recorder.record(
                method=method.upper(),
                url=url,
                request_json=json,
                request_headers=hdrs,
                status_code=r.status_code,
                response_json=rj,
                response_text=r.text,
                response_headers=dict(r.headers or {}),
            )
            return r

        def get(self, path: str, **kwargs):
            return self.request("GET", path, **kwargs)

        def post(self, path: str, **kwargs):
            return self.request("POST", path, **kwargs)

    return _Req()


def test_blackbox_root_ok(managed_requests_client) -> None:
    with step("GET / (managed uvicorn)"):
        r = managed_requests_client.get("/")
    assert r.status_code == 200
    assert r.json().get("status") == "ok"


@pytest.mark.flaky_demo
def test_blackbox_flaky_endpoint_demo(managed_requests_client) -> None:
    """
    This test is intentionally marked for the opt-in flaky demo mode.
    In normal mode, it is still non-deterministic because the endpoint is flaky by design.
    """
    with step("GET /flaky (managed uvicorn)"):
        r = managed_requests_client.get("/flaky", timeout=5)
    assert r.status_code in {200, 500}

