from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from uqo_core.services.headless_engine import EngineSummary


class RunSpecRequest(BaseModel):
    test_type: Literal["pytest", "behavex", "behave_native", "locust"]
    target_repo: str
    cli_args: list[str] = Field(default_factory=list)
    timeout_s: float | None = None
    extra_env: dict[str, str] | None = None
    locust_users: int = 10
    locust_spawn_rate: int = 2
    locust_run_time: str = "1m"
    locust_only_summary: bool = True


class CreateExecutionRequest(BaseModel):
    runs: list[RunSpecRequest]
    persist: bool = True
    trigger_source: Literal["ui"] = "ui"
    ci_mode: bool = False


class ExecutionAcceptedResponse(BaseModel):
    execution_id: str
    status: Literal["queued", "running"]
    events_url: str
    summary_url: str


class ExecutionStatusResponse(BaseModel):
    execution_id: str
    status: Literal["queued", "running", "completed", "failed"]
    summary: dict[str, Any] | None = None
    run_ids: list[str] = Field(default_factory=list)
    error: str | None = None

    @classmethod
    def from_summary(
        cls,
        *,
        execution_id: str,
        status: Literal["queued", "running", "completed", "failed"],
        summary: EngineSummary | None,
        error: str | None = None,
    ) -> "ExecutionStatusResponse":
        payload = summary.to_dict() if summary else None
        run_ids = []
        if payload:
            run_ids = [str(run.get("run_id")) for run in payload.get("runs", []) if run.get("run_id")]
        return cls(
            execution_id=execution_id,
            status=status,
            summary=payload,
            run_ids=run_ids,
            error=error,
        )


class ErrorPayload(BaseModel):
    code: Literal["invalid_input", "not_found", "domain_failure", "infra_failure", "internal_error"]
    message: str
    details: dict[str, Any] | None = None


class ErrorResponse(BaseModel):
    error: ErrorPayload
    request_id: str


class RunListItem(BaseModel):
    run_id: str
    created_at: float
    returncode: int
    status: str | None = None
    health_pct: float | None = None
    total_tests: int | None = None
    passed: int | None = None
    failed: int | None = None
    skipped: int | None = None
    broken: int | None = None
    links_under_static: dict[str, str] = Field(default_factory=dict)


class RunListResponse(BaseModel):
    items: list[RunListItem]
    next_cursor: str | None = None


class RunDetail(BaseModel):
    run_id: str
    status: str | None = None
    created_at: float
    started_at: float
    finished_at: float
    test_kind: str
    returncode: int
    wall_duration_ms: float
    metrics_duration_ms: int | None = None
    total_tests: int | None = None
    passed: int | None = None
    failed: int | None = None
    broken: int | None = None
    skipped: int | None = None
    avg_case_ms: float | None = None
    health_pct: float | None = None
    target_repo: str | None = None
    snapshot_dir: str | None = None
    audit_json: str | None = None


class RunDetailResponse(BaseModel):
    run: RunDetail
    metrics: dict[str, Any] | None = None
    sync: dict[str, Any] | None = None


class RunReportsResponse(BaseModel):
    allure_server_url: str | None = None
    static_links: dict[str, str] = Field(default_factory=dict)
    artifact_links: list[str] = Field(default_factory=list)


class HealthLiveResponse(BaseModel):
    status: Literal["ok"]


class ReadinessCheck(BaseModel):
    status: Literal["ok", "degraded"]
    detail: str | None = None


class HealthReadyResponse(BaseModel):
    status: Literal["ready", "degraded"]
    checks: dict[str, ReadinessCheck]
