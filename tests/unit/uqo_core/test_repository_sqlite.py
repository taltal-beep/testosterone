"""SQLite-backed repository contract tests (no Postgres required)."""

from __future__ import annotations

import uuid

import pytest

from uqo_core.db import get_repository, reset_repository_cache
from uqo_core.db_config import reset_engine_cache
from uqo_core.repository.models import RunStatus
from uqo_core.run_history import cleanup_orphaned_runs


@pytest.fixture
def sqlite_repo(monkeypatch: pytest.MonkeyPatch):
    """Use in-memory SQLite and a fresh engine/repository cache per test."""
    reset_repository_cache()
    reset_engine_cache()
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    try:
        yield get_repository()
    finally:
        reset_repository_cache()
        reset_engine_cache()


def test_create_run_returns_record_with_metadata(sqlite_repo) -> None:
    r = sqlite_repo.create_run(status=RunStatus.RUNNING, metadata={"test_kind": "pytest"})
    assert r.id is not None
    assert r.status == RunStatus.RUNNING
    assert r.metadata_.get("test_kind") == "pytest"
    assert r.metadata_.get("run_id") == str(r.id)


def test_get_run_by_string_id_and_uuid(sqlite_repo) -> None:
    r = sqlite_repo.create_run(status=RunStatus.PENDING)
    ext_id = "my-external-run"
    sqlite_repo.update_run_status(ext_id, status=RunStatus.COMPLETED, metadata={"run_id": ext_id, "returncode": 0})

    by_str = sqlite_repo.get_run(ext_id)
    assert by_str is not None
    assert by_str.status == RunStatus.COMPLETED

    rid = uuid.uuid5(uuid.NAMESPACE_URL, f"uqo-run:{ext_id}")
    by_uuid = sqlite_repo.get_run(rid)
    assert by_uuid is not None
    assert by_uuid.id == rid


def test_list_recent_runs_order(sqlite_repo) -> None:
    a = sqlite_repo.create_run(status=RunStatus.COMPLETED, metadata={"k": "a"})
    b = sqlite_repo.create_run(status=RunStatus.COMPLETED, metadata={"k": "b"})
    rows = sqlite_repo.list_recent_runs(limit=10)
    ids = [r.id for r in rows]
    # Newest first (by start_time)
    assert ids[0] == b.id
    assert ids[1] == a.id


def test_cleanup_orphaned_running(sqlite_repo) -> None:
    sqlite_repo.create_run(status=RunStatus.RUNNING, metadata={"run_id": "r1"})
    sqlite_repo.create_run(status=RunStatus.RUNNING, metadata={"run_id": "r2"})
    running = sqlite_repo.list_runs_by_status(RunStatus.RUNNING)
    assert len(running) == 2

    now_rows = list(running)
    for r in now_rows:
        r.status = RunStatus.FAILED
        r.metadata_ = dict(r.metadata_ or {})
        r.metadata_["error"] = "orphaned"
    n = sqlite_repo.bulk_update(now_rows)
    assert n == 2
    assert sqlite_repo.list_runs_by_status(RunStatus.RUNNING) == []


def test_cleanup_orphaned_runs_marks_running_failed(sqlite_repo) -> None:
    sqlite_repo.create_run(status=RunStatus.RUNNING, metadata={"run_id": "orphan-me"})
    assert len(sqlite_repo.list_runs_by_status(RunStatus.RUNNING)) == 1
    n = cleanup_orphaned_runs(note="pytest orphan")
    assert n == 1
    assert sqlite_repo.list_runs_by_status(RunStatus.RUNNING) == []
    failed = sqlite_repo.list_runs_by_status(RunStatus.FAILED)
    assert len(failed) == 1
    assert failed[0].metadata_.get("error") == "orphaned"
    assert failed[0].metadata_.get("error_message") == "pytest orphan"


def test_update_run_status_merge_metadata(sqlite_repo) -> None:
    ext = "merge-test"
    sqlite_repo.update_run_status(ext, status=RunStatus.RUNNING, metadata={"a": 1})
    sqlite_repo.update_run_status(ext, status=RunStatus.COMPLETED, metadata={"b": 2})
    r = sqlite_repo.get_run(ext)
    assert r is not None
    assert r.status == RunStatus.COMPLETED
    assert r.metadata_.get("a") == 1
    assert r.metadata_.get("b") == 2
    assert r.end_time is not None
