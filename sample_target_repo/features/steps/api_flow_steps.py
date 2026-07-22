"""Step definitions for mock API flows (in-process via FastAPI TestClient)."""

from __future__ import annotations

import json

from behave import given, then, when
from fastapi.testclient import TestClient
from mock_api import app


def _client(context) -> TestClient:
    if not getattr(context, "client", None):
        context.client = TestClient(app)
    return context.client


@given("the mock API client is ready")
def given_client_ready(context) -> None:
    _client(context)


@given('I am logged in as "{username}"')
def given_logged_in(context, username: str) -> None:
    client = _client(context)
    resp = client.post("/login", json={"username": username})
    assert resp.status_code == 200, resp.text
    context.token = resp.json()["token"]


@when('I GET "{path}" as authenticated user')
def when_get_authenticated(context, path: str) -> None:
    token = getattr(context, "token", None)
    assert token, "not logged in; use Given I am logged in as \"...\""
    context.response = _client(context).get(
        path, headers={"Authorization": f"Bearer {token}"}
    )


@when('I GET "{path}"')
def when_get(context, path: str) -> None:
    context.response = _client(context).get(path)


@when('I request GET "{path}" with Authorization "{value}"')
def when_get_auth_header(context, path: str, value: str) -> None:
    context.response = _client(context).get(path, headers={"Authorization": value})


@when('I POST to "{path}" with JSON')
def when_post_json(context, path: str) -> None:
    body = json.loads((context.text or "").strip() or "{}")
    context.response = _client(context).post(path, json=body)


@when('I DELETE "{path}"')
def when_delete(context, path: str) -> None:
    context.response = _client(context).delete(path)


@then("the status code should be {code:d}")
def then_status(context, code: int) -> None:
    assert context.response.status_code == code, (
        f"expected {code}, got {context.response.status_code}: {context.response.text}"
    )


@then("the status code should be one of {codes}")
def then_status_one_of(context, codes: str) -> None:
    allowed = {int(x.strip()) for x in codes.replace(" ", "").split(",") if x.strip()}
    got = context.response.status_code
    assert got in allowed, f"expected one of {allowed}, got {got}: {context.response.text}"


@then('the JSON field "{key}" should exist')
def then_json_key(context, key: str) -> None:
    data = context.response.json()
    assert key in data, f"missing key {key!r} in {data!r}"


@then('the JSON field "{key}" should equal "{value}"')
def then_json_key_str(context, key: str, value: str) -> None:
    data = context.response.json()
    assert str(data.get(key)) == value, data


@then('the JSON field "{key}" should be true')
def then_json_key_true(context, key: str) -> None:
    data = context.response.json()
    assert data.get(key) is True, data
