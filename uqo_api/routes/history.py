from __future__ import annotations

import os

from fastapi import APIRouter, HTTPException

from uqo_api.models import RunDetail, RunDetailResponse, RunListItem, RunListResponse, RunReportsResponse
from uqo_core.run_history import get_run, list_run_sessions, snapshot_files_for_download

router = APIRouter(prefix="/api/v1", tags=["history"])


@router.get("/runs", response_model=RunListResponse)
def list_runs(limit: int = 30) -> RunListResponse:
    sessions = list_run_sessions(limit=limit)
    items = [
        RunListItem(
            run_id=s.run_id,
            created_at=s.created_at,
            returncode=s.returncode,
            status=s.status.value if s.status is not None else None,
            health_pct=s.health_pct,
            total_tests=s.total_tests,
            passed=s.passed,
            failed=s.failed,
            skipped=s.skipped,
            broken=s.broken,
            links_under_static=s.links_under_static,
        )
        for s in sessions
    ]
    return RunListResponse(items=items)


@router.get("/runs/{run_id}", response_model=RunDetailResponse)
def get_run_detail(run_id: str) -> RunDetailResponse:
    record = get_run(run_id=run_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")
    return RunDetailResponse(
        run=RunDetail(
            run_id=record.run_id,
            status=record.status.value if record.status is not None else None,
            created_at=record.created_at,
            started_at=record.started_at,
            finished_at=record.finished_at,
            test_kind=record.test_kind,
            returncode=record.returncode,
            wall_duration_ms=record.wall_duration_ms,
            metrics_duration_ms=record.metrics_duration_ms,
            total_tests=record.total_tests,
            passed=record.passed,
            failed=record.failed,
            broken=record.broken,
            skipped=record.skipped,
            avg_case_ms=record.avg_case_ms,
            health_pct=record.health_pct,
            target_repo=record.target_repo,
            snapshot_dir=record.snapshot_dir,
            audit_json=record.audit_json,
        ),
        metrics=None,
        sync=None,
    )


@router.get("/runs/{run_id}/reports", response_model=RunReportsResponse)
def get_run_reports(run_id: str) -> RunReportsResponse:
    sessions = list_run_sessions(limit=200)
    session = next((s for s in sessions if s.run_id == run_id), None)
    if session is None:
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")
    record = get_run(run_id=run_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")
    artifact_links = [name for name, _ in snapshot_files_for_download(record=record)]
    allure_base = os.getenv("ALLURE_SERVER_URL", "").rstrip("/")
    allure_url = None
    if allure_base:
        allure_url = f"{allure_base}/allure-docker-service/projects/{run_id}/reports/latest/index.html"
    return RunReportsResponse(
        allure_server_url=allure_url,
        static_links=session.links_under_static,
        artifact_links=artifact_links,
    )
