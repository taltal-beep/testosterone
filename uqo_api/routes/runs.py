from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from uqo_api.dependencies import get_execution_manager
from uqo_api.execution_manager import ExecutionManager
from uqo_api.models import CreateExecutionRequest, ExecutionAcceptedResponse, ExecutionStatusResponse

router = APIRouter(prefix="/api/v1", tags=["runs"])


@router.post("/executions", response_model=ExecutionAcceptedResponse, status_code=202)
def create_execution(
    payload: CreateExecutionRequest,
    request: Request,
    manager: ExecutionManager = Depends(get_execution_manager),
) -> ExecutionAcceptedResponse:
    if not payload.runs:
        raise HTTPException(status_code=400, detail="At least one run spec is required.")
    state = manager.create_execution(payload)
    base = str(request.base_url).rstrip("/")
    return ExecutionAcceptedResponse(
        execution_id=state.execution_id,
        status=state.status,
        events_url=f"{base}/api/v1/executions/{state.execution_id}/events",
        summary_url=f"{base}/api/v1/executions/{state.execution_id}",
    )


@router.get("/executions/{execution_id}", response_model=ExecutionStatusResponse)
def get_execution(
    execution_id: str,
    manager: ExecutionManager = Depends(get_execution_manager),
) -> ExecutionStatusResponse:
    state = manager.get(execution_id)
    if state is None:
        raise HTTPException(status_code=404, detail=f"Execution not found: {execution_id}")
    with state.lock:
        return ExecutionStatusResponse(
            execution_id=execution_id,
            status=state.status,
            summary=state.summary,
            run_ids=[str(run.get("run_id")) for run in (state.summary or {}).get("runs", []) if run.get("run_id")],
            error=state.error,
        )
