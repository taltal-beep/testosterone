from __future__ import annotations

import time

import pytest

from testo_core.services.headless_engine import EngineRunRecord, EngineSummary


@pytest.mark.contract
def test_ghost_summary_includes_sync_and_failure_fields() -> None:
    summary = EngineSummary(
        schema_version="1",
        trigger_source="ci",
        ci_mode=True,
        persist=True,
        exit_code=0,
        aggregate_returncode=0,
        started_at=time.time() - 1.0,
        finished_at=time.time(),
        runs=(
            EngineRunRecord(
                test_type="pytest",
                run_id="rid-1",
                returncode=0,
                started_at=time.time() - 1.0,
                finished_at=time.time(),
                duration_s=1.0,
                cwd="/tmp/repo",
            ),
        ),
        execution_mode="ghost",
        failure_type=None,
        sync={"status": "success", "runs": []},
    ).to_dict()

    assert summary["execution_mode"] == "ghost"
    assert "failure_type" in summary
    assert "sync" in summary
    assert isinstance(summary["sync"], dict)
