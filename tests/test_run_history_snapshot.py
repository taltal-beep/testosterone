"""Coverage for snapshot download helpers in ``engine.run_history``."""

from __future__ import annotations

from pathlib import Path

import pytest

from engine.run_history import CompletedRunView, RunStatus, snapshot_files_for_download


def test_snapshot_files_for_download_empty_snapshot_dir() -> None:
    r = CompletedRunView(
        run_id="r",
        status=RunStatus.COMPLETED,
        created_at=0.0,
        started_at=0.0,
        finished_at=0.0,
        test_kind="x",
        returncode=0,
        wall_duration_ms=0.0,
        metrics_duration_ms=None,
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
    )
    assert snapshot_files_for_download(record=r) == []


def test_snapshot_files_for_download_lists_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import engine.run_history as rh

    monkeypatch.setattr(rh, "ORCHESTRATOR_ROOT", tmp_path)
    snap = tmp_path / "artifacts" / "history" / "rid"
    snap.mkdir(parents=True)
    (snap / "a.txt").write_text("x", encoding="utf-8")

    r = CompletedRunView(
        run_id="rid",
        status=RunStatus.COMPLETED,
        created_at=0.0,
        started_at=0.0,
        finished_at=0.0,
        test_kind="x",
        returncode=0,
        wall_duration_ms=0.0,
        metrics_duration_ms=None,
        total_tests=None,
        passed=None,
        failed=None,
        broken=None,
        skipped=None,
        avg_case_ms=None,
        health_pct=None,
        target_repo=None,
        snapshot_dir=str(Path("artifacts/history/rid")),
        audit_json=None,
    )
    files = snapshot_files_for_download(record=r)
    assert files and files[0][0] == "a.txt"
    assert files[0][1] == b"x"
