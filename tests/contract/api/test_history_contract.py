from __future__ import annotations

from fastapi.testclient import TestClient

from uqo_api.main import create_app
from uqo_core.repository.models import RunStatus
from uqo_core.run_history import CompletedRunView, RunSessionView


def test_runs_and_details_contract(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setattr(
        "uqo_api.routes.history.list_run_sessions",
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
        "uqo_api.routes.history.get_run",
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
        ),
    )
    monkeypatch.setattr(
        "uqo_api.routes.history.snapshot_files_for_download",
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

    reports_resp = client.get("/api/v1/runs/run-1/reports")
    assert reports_resp.status_code == 200
    reports_payload = reports_resp.json()
    assert set(reports_payload.keys()) == {"allure_server_url", "static_links", "artifact_links"}
