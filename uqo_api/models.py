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
    code: Literal[
        "invalid_input",
        "not_found",
        "domain_failure",
        "infra_failure",
        "internal_error",
        "provider_misconfigured",
        "provider_timeout",
        "provider_rate_limited",
        "unsupported_provider_model",
        "ai_feature_disabled",
        "summary_not_available",
    ]
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


class DeltaMetricNode(BaseModel):
    current_value: float | None = None
    baseline_value: float | None = None
    absolute_delta: float | None = None
    relative_delta_pct: float | None = None
    classification: Literal["regression", "improvement", "neutral", "unknown"]
    reason: str | None = None
    direction: Literal["higher_is_better", "lower_is_better"]
    unit: Literal["tests", "pct", "ms"]


class DeltaReliabilityMetrics(BaseModel):
    total_tests: DeltaMetricNode
    passed: DeltaMetricNode
    failed: DeltaMetricNode
    broken: DeltaMetricNode
    skipped: DeltaMetricNode
    health_pct: DeltaMetricNode


class DeltaPerformanceMetrics(BaseModel):
    wall_duration_ms: DeltaMetricNode
    metrics_duration_ms: DeltaMetricNode
    avg_case_ms: DeltaMetricNode


class DeltaMetricsResponse(BaseModel):
    reliability: DeltaReliabilityMetrics
    performance: DeltaPerformanceMetrics


class DeltaComparisonMeta(BaseModel):
    current_run_id: str
    baseline_run_id: str
    current_test_kind: str
    baseline_test_kind: str


class DeltaStatusSummaryResponse(BaseModel):
    regressions: list[str] = Field(default_factory=list)
    improvements: list[str] = Field(default_factory=list)
    unchanged: list[str] = Field(default_factory=list)
    unknown: list[str] = Field(default_factory=list)


class DeltaComparisonResponse(BaseModel):
    comparison: DeltaComparisonMeta
    metrics: DeltaMetricsResponse
    status_summary: DeltaStatusSummaryResponse
    highlights: list[str] = Field(default_factory=list)


class DashboardHeadlineKpis(BaseModel):
    latest_run_id: str | None = None
    latest_status: str | None = None
    health_pct: float | None = None
    pass_count: int | None = None
    fail_count: int | None = None
    duration_ms: float | None = None


class DashboardTrendIndicator(BaseModel):
    direction: Literal["up", "down", "flat", "unknown"]
    delta_abs: float | None = None
    delta_pct: float | None = None


class DashboardRollupSummaryResponse(BaseModel):
    regressions: int
    improvements: int
    unchanged: int
    unknown: int


class DashboardRollupResponse(BaseModel):
    status_summary: DashboardRollupSummaryResponse
    top_highlights: list[str] = Field(default_factory=list)


class DashboardReportLinkResponse(BaseModel):
    url: str | None = None
    state: Literal["available", "missing", "unknown"]


class DashboardReportLinksResponse(BaseModel):
    allure: DashboardReportLinkResponse
    locust: DashboardReportLinkResponse
    behave: DashboardReportLinkResponse


class DashboardRecentRunItem(BaseModel):
    run_id: str
    created_at: float
    status: str | None = None
    returncode: int
    health_pct: float | None = None
    duration_ms: float | None = None
    run_detail_url: str
    compare_url: str | None = None


class DashboardDataFreshnessResponse(BaseModel):
    generated_at: float
    source_window_size: int
    degraded: bool
    notes: list[str] = Field(default_factory=list)


class DashboardOverviewResponse(BaseModel):
    headline_kpis: DashboardHeadlineKpis
    trend_indicators: dict[Literal["health", "failed_count", "duration"], DashboardTrendIndicator]
    reliability_rollup: DashboardRollupResponse
    performance_rollup: DashboardRollupResponse
    report_links: DashboardReportLinksResponse
    recent_runs: list[DashboardRecentRunItem] = Field(default_factory=list)
    data_freshness: DashboardDataFreshnessResponse


class DashboardRecentRunsResponse(BaseModel):
    items: list[DashboardRecentRunItem] = Field(default_factory=list)
    generated_at: float


class HealthLiveResponse(BaseModel):
    status: Literal["ok"]


class ReadinessCheck(BaseModel):
    status: Literal["ok", "degraded"]
    detail: str | None = None


class HealthReadyResponse(BaseModel):
    status: Literal["ready", "degraded"]
    checks: dict[str, ReadinessCheck]


class AiConfigUpdateRequest(BaseModel):
    enabled: bool = False
    provider: Literal["openai", "anthropic"] = "openai"
    model: str = "gpt-4o-mini"
    api_key_source: Literal["env", "runtime_input"] = "env"
    api_key_env_var: str | None = None
    api_key_input: str | None = None
    timeout_s: float = 8.0
    retry_count: int = 1
    max_input_chars: int = 16000
    max_output_tokens: int = 300


class AiConfigStatusResponse(BaseModel):
    enabled: bool
    configured: bool
    provider: Literal["openai", "anthropic"]
    model: str
    api_key_source: Literal["env", "runtime_input"]
    api_key_env_var: str | None = None
    key_present: bool | None = None
    timeout_s: float
    retry_count: int
    max_input_chars: int
    max_output_tokens: int


class AiSummaryResponse(BaseModel):
    schema_version: Literal["v1"]
    run_id: str
    status: Literal["available", "no_summary_generated"]
    summary_text: str | None = None
    confidence: Literal["low", "medium", "high"] | None = None
    limitations: list[str] = Field(default_factory=list)
    provider: str | None = None
    model: str | None = None
    generated_at: float
    context_stats: dict[str, int] = Field(default_factory=dict)
    error_code: str | None = None


class GenerateAiSummaryRequest(BaseModel):
    force_refresh: bool = False
