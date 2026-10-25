from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ApiModel(BaseModel):
    """Base for every request/response body in the HTTP contract.

    The response always contains fields that have a default, so the OpenAPI
    schema marks them required in responses. That keeps the generated
    frontend types (``frontend/src/lib/api-schema.ts``) from turning every
    defaulted field into an optional one. Request schemas are unaffected.
    """

    model_config = ConfigDict(json_schema_serialization_defaults_required=True)


class StageSummary(ApiModel):
    name: str
    equipment: str
    target_repo: str
    args: list[str] = Field(default_factory=list)
    timeout_s: float | None = None
    workers: int | None = None


class CycleSummary(ApiModel):
    name: str
    description: str | None = None
    stage_count: int
    equipment: list[str] = Field(default_factory=list)
    # "config": defined in testosterone.yaml, so it can be run from here.
    # "history": only recorded (``testo ingest``, CI, another machine); read-only.
    source: Literal["config", "history"] = "config"


class CycleListResponse(ApiModel):
    items: list[CycleSummary]
    config_path: str | None = None


class CycleTriggerSummary(ApiModel):
    paths: list[str] = Field(default_factory=list)
    since_ref: str | None = None


class CycleDetailResponse(ApiModel):
    name: str
    description: str | None = None
    stages: list[StageSummary]
    trigger: CycleTriggerSummary | None = None
    source: Literal["config", "history"] = "config"


class CycleExecutionRequest(ApiModel):
    config_path: str | None = None
    artifacts_root: str | None = None
    stream: bool = False
    persist: bool = True
    fail_fast: bool = False
    force: bool = False
    workers_override: int | None = None
    report_db: bool = True
    async_report_db: bool = False
    reporter_override: list[str] | None = None


class AdhocExecutionRequest(ApiModel):
    """Run one framework directly, without a cycle in ``testosterone.yaml``."""

    framework: Literal["pytest", "behave", "behavex", "command", "playwright"]
    target_repo: str
    args: list[str] = Field(default_factory=list)
    timeout_s: float | None = None
    extra_env: dict[str, str] | None = None
    config_path: str | None = None
    artifacts_root: str | None = None
    persist: bool = True
    report_db: bool = True


class CycleExecutionAcceptedResponse(ApiModel):
    execution_id: str
    status: Literal["queued", "running"]
    events_url: str
    summary_url: str


class CycleExecutionStatusResponse(ApiModel):
    execution_id: str
    cycle: str
    status: Literal["queued", "running", "completed", "failed"]
    artifacts_root: str | None = None
    events_path: str | None = None
    plan_result_path: str | None = None
    error: str | None = None


class ErrorPayload(ApiModel):
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


class ErrorResponse(ApiModel):
    error: ErrorPayload
    request_id: str


class RunListItem(ApiModel):
    run_id: str
    created_at: float
    returncode: int
    status: str | None = None
    cycle: str | None = None
    health_pct: float | None = None
    total_tests: int | None = None
    passed: int | None = None
    failed: int | None = None
    skipped: int | None = None
    broken: int | None = None
    links_under_static: dict[str, str] = Field(default_factory=dict)
    branch: str | None = None


class RunListResponse(ApiModel):
    items: list[RunListItem]
    next_cursor: str | None = None


class StageHealth(ApiModel):
    name: str
    framework: str | None = None
    total_tests: int | None = None
    passed: int | None = None
    failed: int | None = None
    broken: int | None = None
    skipped: int | None = None
    health_pct: float | None = None


class RunDetail(ApiModel):
    run_id: str
    status: str | None = None
    created_at: float
    started_at: float
    finished_at: float
    test_kind: str
    cycle: str | None = None
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
    stage_health: list[StageHealth] = Field(default_factory=list)
    # What the run tested, when recorded (CI provenance or the local checkout).
    branch: str | None = None
    commit: str | None = None
    base_branch: str | None = None
    repository: str | None = None


class RunDetailResponse(ApiModel):
    run: RunDetail
    metrics: dict[str, Any] | None = None
    sync: dict[str, Any] | None = None


class RunReportsResponse(ApiModel):
    allure_server_url: str | None = None
    static_links: dict[str, str] = Field(default_factory=dict)
    artifact_links: list[str] = Field(default_factory=list)


class RunPyramidResponse(ApiModel):
    unit: int
    integration: int
    e2e: int
    shape: Literal["healthy", "top_heavy", "mid_bulge", "irregular"]
    message: str


class FailingTestItem(ApiModel):
    key: str
    name: str
    full_name: str
    group: str
    stage: str
    status: str
    message: str
    duration_ms: int | None = None
    failing_runs: int
    failing_since_run_id: str
    flaky: bool
    # Broke in this run: passing (or absent) on the baseline run, or, with none, in the run before.
    new: bool


class FailureGroupItem(ApiModel):
    message: str
    count: int
    keys: list[str]


class RunFailuresResponse(ApiModel):
    run_id: str
    runs_considered: int
    new_failures: int
    # The run "new" is judged against: the latest run on the PR's target branch,
    # else the run before on the same branch. ``baseline_branch`` is set only in
    # the first case (the target branch's name).
    baseline_run_id: str | None = None
    baseline_branch: str | None = None
    # Commands that rerun just these tests (pytest node ids, Playwright --grep, Behave --name).
    rerun_commands: list[str] = Field(default_factory=list)
    tests: list[FailingTestItem]
    groups: list[FailureGroupItem]


class DeltaMetricNode(ApiModel):
    current_value: float | None = None
    baseline_value: float | None = None
    absolute_delta: float | None = None
    relative_delta_pct: float | None = None
    classification: Literal["regression", "improvement", "neutral", "unknown"]
    reason: str | None = None
    direction: Literal["higher_is_better", "lower_is_better"]
    unit: Literal["tests", "pct", "ms"]


class DeltaReliabilityMetrics(ApiModel):
    total_tests: DeltaMetricNode
    passed: DeltaMetricNode
    failed: DeltaMetricNode
    broken: DeltaMetricNode
    skipped: DeltaMetricNode
    health_pct: DeltaMetricNode


class DeltaPerformanceMetrics(ApiModel):
    wall_duration_ms: DeltaMetricNode
    metrics_duration_ms: DeltaMetricNode
    avg_case_ms: DeltaMetricNode


class DeltaMetricsResponse(ApiModel):
    reliability: DeltaReliabilityMetrics
    performance: DeltaPerformanceMetrics


class DeltaComparisonMeta(ApiModel):
    current_run_id: str
    baseline_run_id: str
    current_test_kind: str
    baseline_test_kind: str


class DeltaStatusSummaryResponse(ApiModel):
    regressions: list[str] = Field(default_factory=list)
    improvements: list[str] = Field(default_factory=list)
    unchanged: list[str] = Field(default_factory=list)
    unknown: list[str] = Field(default_factory=list)


class DeltaStageDelta(ApiModel):
    stage_name: str
    framework: str | None = None
    baseline_total_tests: int | None = None
    current_total_tests: int | None = None
    baseline_passed: int | None = None
    current_passed: int | None = None
    baseline_health_pct: float | None = None
    current_health_pct: float | None = None
    health_pct_delta: float | None = None
    classification: Literal["regression", "improvement", "neutral", "unknown"]


class DeltaComparisonResponse(ApiModel):
    comparison: DeltaComparisonMeta
    metrics: DeltaMetricsResponse
    status_summary: DeltaStatusSummaryResponse
    highlights: list[str] = Field(default_factory=list)
    stage_deltas: list[DeltaStageDelta] = Field(default_factory=list)


class DeltaCaseChange(ApiModel):
    key: str
    name: str
    group: str
    baseline_status: str | None = None
    current_status: str | None = None
    kind: Literal["added", "removed", "regression", "fix", "status_change"]
    duration_delta_ms: int | None = None


class DeltaCaseChangesResponse(ApiModel):
    current_run_id: str
    baseline_run_id: str
    changes: list[DeltaCaseChange] = Field(default_factory=list)


class FlakyTestItem(ApiModel):
    key: str
    name: str
    group: str
    runs: int
    passed: int
    failed: int
    flips: int
    flip_rate: float
    last_status: str
    history: list[str] = Field(default_factory=list)
    # CODEOWNERS owners of the test's file, and GitHub's new-issue form prefilled for it.
    owners: list[str] = Field(default_factory=list)
    issue_url: str | None = None


class FlakyTestsResponse(ApiModel):
    cycle: str
    window: int
    runs_analyzed: int
    tests_analyzed: int
    items: list[FlakyTestItem] = Field(default_factory=list)


class TestSummaryItem(ApiModel):
    """One test across a cycle's recent runs (``testo_core/services/test_history.py``)."""

    key: str
    name: str
    full_name: str
    group: str
    stage: str
    runs: int
    passed: int
    failed: int
    last_status: str
    flaky: bool
    last_duration_ms: int | None = None
    median_duration_ms: int | None = None
    # Recent median minus the earlier one, only when that is more than timing noise.
    slowdown_ms: int | None = None
    slowdown_pct: float | None = None


class CycleTestsResponse(ApiModel):
    cycle: str
    runs_considered: int
    items: list[TestSummaryItem] = Field(default_factory=list)


class TestPointItem(ApiModel):
    run_id: str
    created_at: float
    status: str
    duration_ms: int | None = None
    message: str = ""
    branch: str | None = None


class AttachmentItem(ApiModel):
    name: str
    content_type: str
    kind: Literal["image", "video", "trace", "text", "file"]
    # Relative to the API root (``history/<run_id>/...``), like report links.
    url: str
    size_bytes: int


class TestHistoryResponse(ApiModel):
    cycle: str
    test: TestSummaryItem
    # Newest first.
    points: list[TestPointItem] = Field(default_factory=list)
    last_failure: TestPointItem | None = None
    # Screenshots, videos, traces the last failing run kept for this test.
    last_failure_attachments: list[AttachmentItem] = Field(default_factory=list)
    owners: list[str] = Field(default_factory=list)
    issue_url: str | None = None


class DashboardHeadlineKpis(ApiModel):
    latest_run_id: str | None = None
    latest_status: str | None = None
    health_pct: float | None = None
    pass_count: int | None = None
    fail_count: int | None = None
    duration_ms: float | None = None
    # Trends compare the latest run with the previous run of the same cycle;
    # baseline_run_id is null when this is the cycle's first run.
    cycle: str | None = None
    baseline_run_id: str | None = None


class DashboardTrendIndicator(ApiModel):
    direction: Literal["up", "down", "flat", "unknown"]
    delta_abs: float | None = None
    delta_pct: float | None = None


class DashboardRollupSummaryResponse(ApiModel):
    regressions: int
    improvements: int
    unchanged: int
    unknown: int


class DashboardRollupResponse(ApiModel):
    status_summary: DashboardRollupSummaryResponse
    top_highlights: list[str] = Field(default_factory=list)


class DashboardReportLinkResponse(ApiModel):
    url: str | None = None
    state: Literal["available", "missing", "unknown"]


class DashboardReportLinksResponse(ApiModel):
    allure: DashboardReportLinkResponse
    behave: DashboardReportLinkResponse


class DashboardRecentRunItem(ApiModel):
    run_id: str
    cycle: str | None = None
    created_at: float
    status: str | None = None
    returncode: int
    health_pct: float | None = None
    duration_ms: float | None = None
    run_detail_url: str
    compare_url: str | None = None


class DashboardDataFreshnessResponse(ApiModel):
    generated_at: float
    source_window_size: int
    degraded: bool
    notes: list[str] = Field(default_factory=list)


class DashboardOverviewResponse(ApiModel):
    headline_kpis: DashboardHeadlineKpis
    trend_indicators: dict[Literal["health", "failed_count", "duration"], DashboardTrendIndicator]
    reliability_rollup: DashboardRollupResponse
    performance_rollup: DashboardRollupResponse
    report_links: DashboardReportLinksResponse
    recent_runs: list[DashboardRecentRunItem] = Field(default_factory=list)
    data_freshness: DashboardDataFreshnessResponse


class DashboardRecentRunsResponse(ApiModel):
    items: list[DashboardRecentRunItem] = Field(default_factory=list)
    generated_at: float


class AttentionFailingCycle(ApiModel):
    cycle: str
    run_id: str
    created_at: float
    branch: str | None = None
    failed_tests: int
    new_failures: int
    failing_runs: int


class AttentionTestItem(ApiModel):
    cycle: str
    key: str
    name: str
    slowdown_ms: int | None = None
    slowdown_pct: float | None = None


class DashboardAttentionResponse(ApiModel):
    """What needs someone now: red cycles, tests that just turned flaky, tests that got slower."""

    cycles: int
    passing_cycles: int
    failing: list[AttentionFailingCycle] = Field(default_factory=list)
    newly_flaky: list[AttentionTestItem] = Field(default_factory=list)
    slower: list[AttentionTestItem] = Field(default_factory=list)


class HealthLiveResponse(ApiModel):
    status: Literal["ok"]


class ReadinessCheck(ApiModel):
    status: Literal["ok", "degraded"]
    detail: str | None = None


class HealthReadyResponse(ApiModel):
    status: Literal["ready", "degraded"]
    checks: dict[str, ReadinessCheck]


class AiConfigUpdateRequest(ApiModel):
    enabled: bool = False
    provider: Literal["openai", "anthropic", "openai_compatible"] = "openai"
    model: str = "gpt-4.1-mini"
    api_key_source: Literal["env", "runtime_input"] = "env"
    api_key_env_var: str | None = None
    api_key_input: str | None = None
    timeout_s: float = 8.0
    retry_count: int = 1
    max_input_chars: int = 16000
    max_output_tokens: int = 300
    base_url: str | None = None


class AiConfigStatusResponse(ApiModel):
    enabled: bool
    configured: bool
    provider: Literal["openai", "anthropic", "openai_compatible"]
    model: str
    api_key_source: Literal["env", "runtime_input"]
    api_key_env_var: str | None = None
    key_present: bool | None = None
    timeout_s: float
    retry_count: int
    max_input_chars: int
    max_output_tokens: int
    base_url: str | None = None


class AiSummaryResponse(ApiModel):
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


class GenerateAiSummaryRequest(ApiModel):
    force_refresh: bool = False


class IngestResponse(ApiModel):
    """A recorded upload (``POST /api/v1/ingest``, what ``testo ingest --server`` sends)."""

    run_id: str | None = None
    cycle: str
    exit_code: int
    tests: int
    passed: int
    failed: int
    skipped: int
    run_url: str | None = None
