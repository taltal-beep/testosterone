"""Run history DB — requires Postgres env vars when enabled.

These tests are skipped unless `POSTGRES_USER`, `POSTGRES_PASSWORD`, and `POSTGRES_DB` are set.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from engine.command_builders import BuiltCommand
from engine.run_history import (
    compare_latest_two,
    create_db_and_tables,
    get_run,
    list_recent_runs,
    list_run_sessions,
    record_completed_run,
)
from engine.runners import RunResult


def _pg_ready() -> bool:
    import os

    return bool(os.getenv("POSTGRES_USER") and os.getenv("POSTGRES_PASSWORD") and os.getenv("POSTGRES_DB"))


pytestmark = pytest.mark.skipif(not _pg_ready(), reason="Postgres env vars not set for run_history tests")


def test_init_and_list_recent_empty(tmp_path: Path) -> None:
    create_db_and_tables()
    assert list_recent_runs(limit=5) == []


def test_record_completed_run_inserts_row(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    cmd = BuiltCommand(argv=["pytest"], cwd=tmp_path, env={"UQO_RUN_ID": "rid-1"})
    rr = RunResult(returncode=0, started_at=0.0, finished_at=1.0, command=cmd)
    (tmp_path / "allure-results").mkdir(parents=True)
    monkeypatch.setattr("engine.run_history._snapshot_reports", lambda **_: None)
    record_completed_run(rr=rr, artifacts_root=tmp_path, test_kind="pytest")
    rows = list_recent_runs(limit=5)
    assert len(rows) == 1
    assert rows[0].run_id == "rid-1"
    assert get_run(run_id="rid-1") is not None


def test_compare_latest_two_none_when_insufficient(tmp_path: Path) -> None:
    create_db_and_tables()
    assert compare_latest_two() is None


def test_list_run_sessions_maps_new_allure_reports_layout(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # Point the static history root at a temp directory so we can create fake snapshots.
    fake_static_history = tmp_path / "static" / "history"
    monkeypatch.setattr("engine.run_history.STATIC_HISTORY_ROOT", fake_static_history)

    cmd = BuiltCommand(argv=["pytest"], cwd=tmp_path, env={"UQO_RUN_ID": "rid-1"})
    rr = RunResult(returncode=0, started_at=0.0, finished_at=1.0, command=cmd)
    (tmp_path / "allure-results").mkdir(parents=True)
    monkeypatch.setattr("engine.run_history._snapshot_reports", lambda **_: None)
    record_completed_run(rr=rr, artifacts_root=tmp_path, test_kind="pytest")

    base = fake_static_history / "rid-1" / "allure_reports"
    (base / "pytest").mkdir(parents=True)
    (base / "pytest" / "index.html").write_text("ok", encoding="utf-8")
    (base / "behave_native").mkdir(parents=True)
    (base / "behave_native" / "index.html").write_text("ok", encoding="utf-8")

    sessions = list_run_sessions(limit=5)
    assert sessions
    links = sessions[0].links_under_static
    assert links["pytest"].endswith("history/rid-1/allure_reports/pytest/index.html")
    assert links["behave_native"].endswith("history/rid-1/allure_reports/behave_native/index.html")
