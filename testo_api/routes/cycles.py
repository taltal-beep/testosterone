from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from testo_api.cycle_execution_manager import CycleExecutionManager, iter_execution_sse
from testo_api.dependencies import get_cycle_execution_manager
from testo_api.models import (
    AdhocExecutionRequest,
    CycleDetailResponse,
    CycleExecutionAcceptedResponse,
    CycleExecutionRequest,
    CycleExecutionStatusResponse,
    CycleListResponse,
    CycleSummary,
    CycleTriggerSummary,
    StageSummary,
)
from testo_core.config.errors import ConfigError, ConfigValidationError
from testo_core.config.loader import discover_and_load
from testo_core.config.schema import PARALLEL_FRAMEWORKS

router = APIRouter(prefix="/api/v1", tags=["cycles"])


def _load_config(config_path: str | None = None):
    try:
        return discover_and_load(
            config_path=Path(config_path).expanduser().resolve() if config_path else None
        )
    except ConfigError as exc:
        raise HTTPException(status_code=503, detail=f"config error: {exc}") from exc


def _optional_path(raw: str | None) -> Path | None:
    return Path(raw).expanduser().resolve() if raw else None


def _accepted(request: Request, execution_id: str) -> CycleExecutionAcceptedResponse:
    base = str(request.base_url).rstrip("/")
    return CycleExecutionAcceptedResponse(
        execution_id=execution_id,
        status="queued",
        events_url=f"{base}/api/v1/cycle-executions/{execution_id}/events",
        summary_url=f"{base}/api/v1/cycle-executions/{execution_id}",
    )


@router.get("/cycles", response_model=CycleListResponse)
def list_cycles(config_path: str | None = None) -> CycleListResponse:
    """List every cycle defined in the resolved configuration (UI parity with ``testo cycles list``)."""
    cfg = _load_config(config_path)
    items = [
        CycleSummary(
            name=cycle.name,
            description=cycle.description,
            stage_count=len(cycle.stages),
            equipment=sorted({stage.framework for stage in cycle.stages}),
        )
        for cycle in cfg.cycles.values()
    ]
    return CycleListResponse(
        items=items,
        config_path=str(cfg.source_path) if cfg.source_path else None,
    )


@router.get("/cycles/{cycle}", response_model=CycleDetailResponse)
def get_cycle(cycle: str, config_path: str | None = None) -> CycleDetailResponse:
    """Resolved view of one cycle (UI parity with ``testo cycles show <name>``)."""
    cfg = _load_config(config_path)
    plan = cfg.cycles.get(cycle)
    if plan is None:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown cycle: {cycle}. Available cycles: {', '.join(sorted(cfg.cycles))}",
        )
    return CycleDetailResponse(
        name=plan.name,
        description=plan.description,
        stages=[
            StageSummary(
                name=stage.name,
                equipment=stage.framework,
                target_repo=str(stage.target_repo),
                args=list(stage.args),
                timeout_s=stage.timeout_s,
                # Only frameworks that act on it; showing "Workers 4" on a
                # single-process behave stage would claim parallelism it lacks.
                workers=stage.workers if stage.framework in PARALLEL_FRAMEWORKS else None,
            )
            for stage in plan.stages
        ],
        trigger=CycleTriggerSummary(
            paths=list(plan.trigger.paths), since_ref=plan.trigger.since_ref
        )
        if plan.trigger
        else None,
    )


@router.post(
    "/cycles/{cycle}/executions", response_model=CycleExecutionAcceptedResponse, status_code=202
)
def create_cycle_execution(
    cycle: str,
    payload: CycleExecutionRequest,
    request: Request,
    manager: CycleExecutionManager = Depends(get_cycle_execution_manager),
) -> CycleExecutionAcceptedResponse:
    try:
        state = manager.create_execution(
            cycle=str(cycle),
            config_path=_optional_path(payload.config_path),
            artifacts_root_override=_optional_path(payload.artifacts_root),
            persist=bool(payload.persist),
            force=bool(payload.force),
            fail_fast=bool(payload.fail_fast),
            reporter_override=list(payload.reporter_override)
            if payload.reporter_override
            else None,
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

    return _accepted(request, state.execution_id)


@router.post("/adhoc-executions", response_model=CycleExecutionAcceptedResponse, status_code=202)
def create_adhoc_execution(
    payload: AdhocExecutionRequest,
    request: Request,
    manager: CycleExecutionManager = Depends(get_cycle_execution_manager),
) -> CycleExecutionAcceptedResponse:
    """Run one framework directly as a one-stage ``adhoc`` cycle.

    Same engine, persistence and event stream as a named cycle: progress and
    status live under ``/cycle-executions/{execution_id}``.
    """
    try:
        state = manager.create_adhoc_execution(
            framework=payload.framework,
            target_repo=Path(payload.target_repo),
            args=payload.args,
            timeout_s=payload.timeout_s,
            extra_env=payload.extra_env,
            config_path=_optional_path(payload.config_path),
            artifacts_root_override=_optional_path(payload.artifacts_root),
            persist=bool(payload.persist),
            report_db=bool(payload.report_db),
        )
    except ConfigValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _accepted(request, state.execution_id)


def _execution_not_found(execution_id: str, manager: CycleExecutionManager) -> HTTPException:
    return HTTPException(
        status_code=404,
        detail=(
            f"Execution not found: {execution_id}. Only running executions and the last "
            f"{manager.max_finished} finished ones are kept in memory; completed runs "
            "remain in the run history (/api/v1/runs)."
        ),
    )


@router.get("/cycle-executions/{execution_id}", response_model=CycleExecutionStatusResponse)
def get_cycle_execution(
    execution_id: str,
    manager: CycleExecutionManager = Depends(get_cycle_execution_manager),
) -> CycleExecutionStatusResponse:
    state = manager.get(execution_id)
    if state is None:
        raise _execution_not_found(execution_id, manager)
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
    if manager.get(execution_id) is None:
        raise _execution_not_found(execution_id, manager)
    return StreamingResponse(
        iter_execution_sse(manager, execution_id),
        media_type="text/event-stream",
    )
