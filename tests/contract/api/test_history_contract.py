from __future__ import annotations

from fastapi.testclient import TestClient

from testo_api.main import create_app
from testo_core.history.views import CompletedRunView, RunSessionView
from testo_core.repository.models import RunStatus


def test_runs_and_details_contract(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setattr(
        "testo_api.routes.history.list_run_sessions",
        lambda limit=30: [  # noqa: ARG005
            RunSessionView(
                run_id="run-1",
                created_at=1.0,
                returncode=0,
                health_pct=99.0,
                total_tests=10,
                passed=10,
                failed=0,
                skipped=0,
                broken=0,
                status=RunStatus.COMPLETED,
                links_under_static={"pytest": "history/run-1/allure_reports/pytest/index.html"},
            )
        ],
    )
    monkeypatch.setattr(
        "testo_api.routes.history.get_run",
        lambda run_id: CompletedRunView(  # noqa: ARG005
            run_id="run-1",
            status=RunStatus.COMPLETED,
            created_at=1.0,
            started_at=1.0,
            finished_at=2.0,
            test_kind="pytest",
            returncode=0,
            wall_duration_ms=1000.0,
            metrics_duration_ms=1000,
            total_tests=10,
            passed=10,
            failed=0,
            broken=0,
            skipped=0,
            avg_case_ms=100.0,
            health_pct=100.0,
            target_repo="/tmp/repo",
            snapshot_dir="runs/run-1/artifacts",
            audit_json=None,
            branch="feat",
            commit="abc1234",
            base_branch="main",
            repository="acme/shop",
        ),
    )
    monkeypatch.setattr(
        "testo_api.routes.history.snapshot_files_for_download",
        lambda record: [("allure_report.html", b"x")],  # noqa: ARG005
    )

    client = TestClient(create_app())
    list_resp = client.get("/api/v1/runs")
    assert list_resp.status_code == 200
    list_payload = list_resp.json()
    assert "items" in list_payload
    assert list_payload["items"][0]["run_id"] == "run-1"
    assert "links_under_static" in list_payload["items"][0]

    detail_resp = client.get("/api/v1/runs/run-1")
    assert detail_resp.status_code == 200
    detail_payload = detail_resp.json()
    assert set(detail_payload.keys()) == {"run", "metrics", "sync"}
    assert detail_payload["run"]["run_id"] == "run-1"
    run = detail_payload["run"]
    assert (run["branch"], run["commit"], run["base_branch"], run["repository"]) == (
        "feat",
        "abc1234",
        "main",
        "acme/shop",
    )

    reports_resp = client.get("/api/v1/runs/run-1/reports")
    assert reports_resp.status_code == 200
    reports_payload = reports_resp.json()
    assert set(reports_payload.keys()) == {"allure_server_url", "static_links", "artifact_links"}


def test_run_pyramid_contract(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setattr(
        "testo_api.routes.history.get_run",
        lambda run_id: CompletedRunView(  # noqa: ARG005
            run_id="run-1",
            status=RunStatus.COMPLETED,
            created_at=1.0,
            started_at=1.0,
            finished_at=2.0,
            test_kind="pytest",
            returncode=0,
            wall_duration_ms=1000.0,
            metrics_duration_ms=1000,
            total_tests=10,
            passed=10,
            failed=0,
            broken=0,
            skipped=0,
            avg_case_ms=100.0,
            health_pct=100.0,
            target_repo="/tmp/repo",
            snapshot_dir="runs/run-1/artifacts",
            audit_json=None,
            cycle=None,  # no cycle -> skip config lookup, tests still bucket to "unit" default
            stage_health=[{"name": "pytest-sample", "total_tests": 10}],
        ),
    )

    client = TestClient(create_app())
    resp = client.get("/api/v1/runs/run-1/pyramid")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload == {
        "unit": 10,
        "integration": 0,
        "e2e": 0,
        "shape": "irregular",
        "message": "Not a clean pyramid: each tier should be smaller than the one below it.",
    }


def _cycle_run(stage_health: list[dict]) -> CompletedRunView:
    return CompletedRunView(
        run_id="run-2",
        status=RunStatus.COMPLETED,
        created_at=1.0,
        started_at=1.0,
        finished_at=2.0,
        test_kind="cycle",
        returncode=0,
        wall_duration_ms=1000.0,
        metrics_duration_ms=1000,
        total_tests=None,
        passed=None,
        failed=None,
        broken=None,
        skipped=None,
        avg_case_ms=None,
        health_pct=None,
        target_repo=None,
        snapshot_dir=None,
        audit_json=None,
        cycle="smoke",
        stage_health=stage_health,
    )


def test_run_pyramid_uses_tiers_recorded_in_the_run(monkeypatch) -> None:  # noqa: ANN001
    run = _cycle_run(
        [
            {"name": "unit-tests", "tier": "unit", "total_tests": 8},
            {"name": "api-tests", "tier": "integration", "total_tests": 3},
            {"name": "ui-tests", "tier": "e2e", "total_tests": 1},
        ]
    )
    monkeypatch.setattr("testo_api.routes.history.get_run", lambda run_id: run)  # noqa: ARG005

    def _no_config(**_kwargs):  # noqa: ANN202, ANN003
        raise AssertionError("pyramid must not read testosterone.yaml when tiers are recorded")

    monkeypatch.setattr("testo_api.routes.history.discover_and_load", _no_config)

    resp = TestClient(create_app()).get("/api/v1/runs/run-2/pyramid")
    assert resp.status_code == 200
    assert resp.json()["unit"] == 8
    assert resp.json()["integration"] == 3
    assert resp.json()["e2e"] == 1
    assert resp.json()["shape"] == "healthy"


def test_run_pyramid_falls_back_to_yaml_for_runs_without_tiers(  # noqa: ANN001
    monkeypatch, tmp_path
) -> None:
    run = _cycle_run([{"name": "api-tests", "total_tests": 3}])
    monkeypatch.setattr("testo_api.routes.history.get_run", lambda run_id: run)  # noqa: ARG005
    config = tmp_path / "testosterone.yaml"
    config.write_text(
        "cycles:\n"
        "  smoke:\n"
        "    stages:\n"
        "      - name: api-tests\n"
        "        equipment: pytest\n"
        "        target_repo: .\n"
        "        tier: integration\n",
        encoding="utf-8",
    )

    resp = TestClient(create_app()).get(
        "/api/v1/runs/run-2/pyramid", params={"config_path": str(config)}
    )
    assert resp.status_code == 200
    assert resp.json()["integration"] == 3
    assert resp.json()["unit"] == 0


def test_run_pyramid_contract_missing_run(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setattr("testo_api.routes.history.get_run", lambda run_id: None)  # noqa: ARG005
    client = TestClient(create_app())
    resp = client.get("/api/v1/runs/does-not-exist/pyramid")
    assert resp.status_code == 404


def test_run_failures_contract(monkeypatch) -> None:  # noqa: ANN001
    from testo_core.services.run_failures import FailingTest, FailureGroup, RunFailures

    failing = FailingTest(
        key="k1",
        name="test_login",
        full_name="tests.api.test_login",
        group="tests.api",
        stage="api",
        status="failed",
        message="ConnectionRefusedError",
        duration_ms=12,
        failing_runs=1,
        failing_since_run_id="run-1",
        flaky=False,
        new=True,
    )
    monkeypatch.setattr(
        "testo_api.routes.history.load_run_failures",
        lambda run_id: (
            RunFailures(  # noqa: ARG005
                run_id="run-1",
                runs_considered=3,
                tests=(failing,),
                groups=(
                    FailureGroup(message="ConnectionRefusedError", count=2, keys=("k1", "k2")),
                ),
                baseline_run_id="run-0",
                baseline_branch="main",
                rerun_commands=("pytest tests/api/test_login.py::test_login",),
            )
            if run_id == "run-1"
            else None
        ),
    )

    client = TestClient(create_app())
    resp = client.get("/api/v1/runs/run-1/failures")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["new_failures"] == 1
    assert payload["runs_considered"] == 3
    assert (payload["baseline_run_id"], payload["baseline_branch"]) == ("run-0", "main")
    assert payload["tests"][0]["new"] is True
    assert payload["rerun_commands"] == ["pytest tests/api/test_login.py::test_login"]
    assert payload["tests"][0]["name"] == "test_login"
    assert payload["tests"][0]["failing_since_run_id"] == "run-1"
    assert payload["groups"] == [
        {"message": "ConnectionRefusedError", "count": 2, "keys": ["k1", "k2"]}
    ]
    assert client.get("/api/v1/runs/missing/failures").status_code == 404
