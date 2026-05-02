"""Coverage for snapshot download helpers in ``uqo_core.run_history``."""

from __future__ import annotations

from pathlib import Path

import pytest

from uqo_core.command_builders import BuiltCommand
from uqo_core.run_history import CompletedRunView, RunStatus, record_completed_run, snapshot_files_for_download
from uqo_core.runners import RunResult


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
    import uqo_core.run_history as rh

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


def test_record_completed_run_uses_scoped_results_dir_for_metrics(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import uqo_core.run_history as rh

    scoped = tmp_path / "artifacts" / "allure-results" / "pytest" / "rid"
    other = tmp_path / "artifacts" / "allure-results" / "pytest" / "other"
    scoped.mkdir(parents=True)
    other.mkdir(parents=True)
    (scoped / "a-result.json").write_text('{"status":"passed","start":0,"stop":10}', encoding="utf-8")
    (other / "b-result.json").write_text('{"status":"failed","start":0,"stop":10}', encoding="utf-8")

    captured: dict[str, object] = {}
    monkeypatch.setattr(rh, "_snapshot_reports", lambda **_: None)
    monkeypatch.setattr(rh, "update_run_status", lambda _run_id, *, status, metadata: captured.update(metadata))

    cmd = BuiltCommand(
        argv=["pytest"],
        cwd=tmp_path,
        env={"UQO_RUN_ID": "rid", "UQO_SHARED_ALLURE_RESULTS_DIR": str(scoped)},
    )
    rr = RunResult(returncode=0, started_at=0.0, finished_at=1.0, command=cmd)

    record_completed_run(rr=rr, artifacts_root=tmp_path / "artifacts", test_kind="pytest")

    assert captured["total_tests"] == 1
    assert captured["passed"] == 1
    assert captured["failed"] == 0
