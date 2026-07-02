from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from testo_api.cycle_execution_manager import CycleExecutionManager, iter_sse_from_ndjson_file
from testo_api.dependencies import get_cycle_execution_manager
from testo_api.models import (
    CycleExecutionAcceptedResponse,
    CycleExecutionRequest,
    CycleExecutionStatusResponse,
)

router = APIRouter(prefix="/api/v1", tags=["cycles"])


@router.post("/cycles/{cycle}/executions", response_model=CycleExecutionAcceptedResponse, status_code=202)
def create_cycle_execution(
    cycle: str,
    payload: CycleExecutionRequest,
    request: Request,
    manager: CycleExecutionManager = Depends(get_cycle_execution_manager),
) -> CycleExecutionAcceptedResponse:
    try:
        state = manager.create_execution(
            cycle=str(cycle),
            config_path=Path(payload.config_path).expanduser().resolve() if payload.config_path else None,
            artifacts_root_override=Path(payload.artifacts_root).expanduser().resolve() if payload.artifacts_root else None,
            persist=bool(payload.persist),
            force=bool(payload.force),
            fail_fast=bool(payload.fail_fast),
            reporter_override=list(payload.reporter_override) if payload.reporter_override else None,
            report_db=bool(payload.report_db),
            async_report_db=bool(payload.async_report_db),
            workers_override=payload.workers_override,
            stream=bool(payload.stream),
            ci=True,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    base = str(request.base_url).rstrip("/")
    return CycleExecutionAcceptedResponse(
        execution_id=state.execution_id,
        status="queued",
        events_url=f"{base}/api/v1/cycle-executions/{state.execution_id}/events",
        summary_url=f"{base}/api/v1/cycle-executions/{state.execution_id}",
    )


@router.get("/cycle-executions/{execution_id}", response_model=CycleExecutionStatusResponse)
def get_cycle_execution(
    execution_id: str,
    manager: CycleExecutionManager = Depends(get_cycle_execution_manager),
) -> CycleExecutionStatusResponse:
    state = manager.get(execution_id)
    if state is None:
        raise HTTPException(status_code=404, detail=f"Execution not found: {execution_id}")
    with state.lock:
        return CycleExecutionStatusResponse(
            execution_id=execution_id,
            cycle=state.cycle,
            status=state.status,
            artifacts_root=str(state.artifacts_root) if state.artifacts_root else None,
            events_path=str(state.events_path) if state.events_path else None,
            plan_result_path=str(state.plan_result_path) if state.plan_result_path else None,
            error=state.error,
        )


@router.get("/cycle-executions/{execution_id}/events")
def stream_cycle_execution_events(
    execution_id: str,
    manager: CycleExecutionManager = Depends(get_cycle_execution_manager),
) -> StreamingResponse:
    state = manager.get(execution_id)
    if state is None:
        raise HTTPException(status_code=404, detail=f"Execution not found: {execution_id}")

    try:
        events_path, start_offset, _done = manager.resolve_events_path(execution_id)
    except RuntimeError:
        # execution exists but events not ready yet; treat as empty stream until initialized
        with state.lock:
            events_path = state.events_path or Path("artifacts") / state.cycle / "events.ndjson"
            start_offset = int(state.events_start_offset_bytes or 0)

    def is_done() -> bool:
        s = manager.get(execution_id)
        if s is None:
            return True
        with s.lock:
            return bool(s.done)

    return StreamingResponse(
        iter_sse_from_ndjson_file(
            events_path=events_path,
            start_offset_bytes=start_offset,
            is_done=is_done,
        ),
        media_type="text/event-stream",
    )

