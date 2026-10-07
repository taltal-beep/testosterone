"""Run history read side (``testo_core.history``) against an in-memory SQLite repository."""

from __future__ import annotations

from pathlib import Path

import pytest

from testo_core.db import get_repository, reset_repository_cache
from testo_core.db_config import reset_engine_cache
from testo_core.history.read_model import (
    get_run,
    get_run_metadata,
    list_recent_runs,
    list_run_sessions,
)
from testo_core.history.report_links import allure_report_url_for_run
from testo_core.history.snapshots import snapshot_files_for_download
from testo_core.history.views import (
    CompletedRunView,
    view_from_record,
    wall_duration_ms_from_metadata,
)
from testo_core.repository.models import RunRecord, RunStatus


@pytest.fixture
def sqlite_repo(monkeypatch: pytest.MonkeyPatch):
    reset_repository_cache()
    reset_engine_cache()
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    try:
        yield get_repository()
    finally:
        reset_repository_cache()
        reset_engine_cache()


@pytest.fixture
def static_history(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    root = tmp_path / "static" / "history"
    monkeypatch.setattr("testo_core.paths.STATIC_HISTORY_ROOT", root)
    return root


def _view(**overrides: object) -> CompletedRunView:
    fields: dict[str, object] = {
        "run_id": "rid",
        "status": RunStatus.COMPLETED,
        "created_at": 0.0,
        "started_at": 0.0,
        "finished_at": 0.0,
        "test_kind": "cycle",
        "returncode": 0,
        "wall_duration_ms": 0.0,
        "metrics_duration_ms": None,
        "total_tests": None,
        "passed": None,
        "failed": None,
        "broken": None,
        "skipped": None,
        "avg_case_ms": None,
        "health_pct": None,
        "target_repo": None,
        "snapshot_dir": None,
        "audit_json": None,
    }
    fields.update(overrides)
    return CompletedRunView(**fields)  # type: ignore[arg-type]


# --- views -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("metadata", "expected"),
    [
        ({"duration_s": 1.5}, 1500.0),
        ({"started_at": 10.0, "finished_at": 12.25}, 2250.0),
        ({}, 0.0),
    ],
)
def test_wall_duration_ms_falls_back_to_engine_duration(metadata: dict, expected: float) -> None:
    assert wall_duration_ms_from_metadata(metadata) == pytest.approx(expected)


def test_view_from_engine_record() -> None:
    record = RunRecord(
        status=RunStatus.FAILED,
        metadata_={
            "run_id": "r1",
            "plan": "smoke",
            "exit_code": 1,
            "duration_s": 2.0,
            "stages": [{"name": "unit", "returncode": 0}, {"name": "flows", "returncode": 1}],
        },
    )
    view = view_from_record(record)
    assert view is not None
    assert (view.cycle, view.returncode, view.wall_duration_ms, view.health_pct) == (
        "smoke",
        1,
        2000.0,
        50.0,
    )
    assert [s["name"] for s in view.stage_health] == ["unit", "flows"]


def test_view_from_record_without_run_id_is_skipped() -> None:
    assert view_from_record(RunRecord(status=RunStatus.COMPLETED, metadata_={})) is None


# --- read model --------------------------------------------------------------


def test_read_model_lists_and_gets_runs(sqlite_repo) -> None:
    assert list_recent_runs(limit=5) == []
    record = sqlite_repo.create_run(
        status=RunStatus.COMPLETED, metadata={"exit_code": 0, "plan": "smoke"}
    )
    run_id = str(record.id)

    rows = list_recent_runs(limit=5)
    assert [r.run_id for r in rows] == [run_id]
    assert get_run(run_id=run_id) == rows[0]
    assert get_run_metadata(run_id=run_id)["plan"] == "smoke"
    assert get_run(run_id="missing") is None
    assert get_run_metadata(run_id="missing") is None


def test_list_run_sessions_maps_report_layout(sqlite_repo, static_history: Path) -> None:
    rid = str(sqlite_repo.create_run(status=RunStatus.COMPLETED, metadata={"exit_code": 0}).id)
    base = static_history / rid
    for rel in (
        "allure_reports/pytest/index.html",
        # Adapters name the subdir after the stage equipment; the scan must not assume a fixed set.
        "allure_reports/behave/index.html",
        "extent_report/index.html",
        "native_reports/behavex/index.html",
    ):
        (base / rel).parent.mkdir(parents=True, exist_ok=True)
        (base / rel).write_text("ok", encoding="utf-8")

    [session] = list_run_sessions(limit=5)
    assert session.links_under_static == {
        "pytest": f"history/{rid}/allure_reports/pytest/index.html",
        "behave": f"history/{rid}/allure_reports/behave/index.html",
        "extent": f"history/{rid}/extent_report/index.html",
        "behavex-native": f"history/{rid}/native_reports/behavex/index.html",
    }


# --- report links and snapshots --------------------------------------------------


def test_allure_report_url_for_run(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALLURE_SERVER_URL", "http://localhost:5050/")
    assert (
        allure_report_url_for_run("abc-123") == "http://localhost:5050/reports/abc-123/index.html"
    )


def test_snapshot_files_for_download_reads_local_dir(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr("testo_core.paths.ORCHESTRATOR_ROOT", tmp_path)
    snap = tmp_path / "artifacts" / "smoke"
    (snap / "unit").mkdir(parents=True)
    (snap / "unit" / "run.log").write_text("x", encoding="utf-8")

    assert snapshot_files_for_download(record=_view(snapshot_dir=None)) == []
    assert snapshot_files_for_download(record=_view(snapshot_dir="artifacts/missing")) == []
    assert snapshot_files_for_download(record=_view(snapshot_dir="artifacts/smoke")) == [
        ("unit/run.log", b"x")
    ]
