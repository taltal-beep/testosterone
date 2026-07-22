from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from testo_api.main import create_app

CONFIG_YAML = """\
version: 1
defaults:
  target_repo: .
  artifacts_root: artifacts
  timeout_s: 600
  workers: 4
cycles:
  smoke:
    description: Quick smoke cycle.
    stages:
      - name: pytest-smoke
        equipment: pytest
        args: [-q, tests]
  full:
    description: Multi-framework cycle.
    stages:
      - name: pytest-stage
        equipment: pytest
        args: [-q, tests]
      - name: behave-stage
        equipment: behave
        args: [features]
"""


@pytest.fixture()
def config_path(tmp_path: Path) -> Path:
    path = tmp_path / "testosterone.yaml"
    path.write_text(CONFIG_YAML, encoding="utf-8")
    return path


@pytest.fixture()
def client() -> TestClient:
    return TestClient(create_app())


def test_list_cycles_returns_summaries(client: TestClient, config_path: Path) -> None:
    resp = client.get("/api/v1/cycles", params={"config_path": str(config_path)})
    assert resp.status_code == 200
    body = resp.json()
    assert body["config_path"] == str(config_path)
    by_name = {item["name"]: item for item in body["items"]}
    assert set(by_name) == {"smoke", "full"}
    assert by_name["smoke"]["stage_count"] == 1
    assert by_name["smoke"]["equipment"] == ["pytest"]
    assert by_name["full"]["stage_count"] == 2
    assert by_name["full"]["equipment"] == ["behave", "pytest"]
    assert by_name["full"]["description"] == "Multi-framework cycle."


def test_get_cycle_detail_resolves_stages(client: TestClient, config_path: Path) -> None:
    resp = client.get("/api/v1/cycles/full", params={"config_path": str(config_path)})
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "full"
    assert [s["name"] for s in body["stages"]] == ["pytest-stage", "behave-stage"]
    assert body["stages"][0]["equipment"] == "pytest"
    assert body["stages"][0]["args"] == ["-q", "tests"]
    assert body["stages"][0]["timeout_s"] == 600
    assert body["stages"][0]["workers"] == 4
    assert body["trigger"] is None


def test_get_unknown_cycle_is_404_with_available_names(client: TestClient, config_path: Path) -> None:
    resp = client.get("/api/v1/cycles/nope", params={"config_path": str(config_path)})
    assert resp.status_code == 404
    error = resp.json()["error"]
    assert error["code"] == "not_found"
    assert "Unknown cycle: nope" in error["message"]
    assert "full" in error["message"] and "smoke" in error["message"]


def test_missing_config_is_503(client: TestClient, tmp_path: Path) -> None:
    resp = client.get("/api/v1/cycles", params={"config_path": str(tmp_path / "missing.yaml")})
    assert resp.status_code == 503
    error = resp.json()["error"]
    assert error["code"] == "infra_failure"
    assert "config error" in error["message"]
