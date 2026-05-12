"""Service layer: orchestration and use-cases (framework-agnostic where possible)."""

from .audit_service import AuditService
from .ai import (
    AiGenerationRequest,
    AiGenerationResult,
    AiIntegrationSettings,
    AiProvider,
    AiProviderConfig,
    AiProviderError,
    InMemoryAiSettingsStore,
    ProviderMisconfiguredError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    ProviderUnavailableError,
    UnsupportedProviderModelError,
    build_ai_provider,
)
from .ci_provenance import CIProvenance, detect_ci_environment, detect_ci_provenance
from .config_loader import load_run_specs_from_yaml
from .dashboard_service import (
    DashboardDataFreshness,
    DashboardHeadlineKpis,
    DashboardOverview,
    DashboardRecentRun,
    DashboardReportLink,
    DashboardReportLinks,
    DashboardRollup,
    DashboardRollupSummary,
    DashboardService,
    DashboardTrendIndicator,
)
from .delta_models import DeltaComparisonResult, DeltaStatusSummary, MetricDelta
from .delta_service import (
    DeltaComparisonError,
    DeltaComparisonService,
    IncompatibleRunDataError,
    InvalidRunIdError,
    RunNotFoundComparisonError,
)
from .event_drain import RunLogLine, apply_completed_multi_run, iter_drained_queue_items
from .failure_analysis_service import FailureAnalysisService, FailureAnalysisSummary
from .failure_context_builder import FailureContext, FailureContextBudget, build_failure_context
from .headless_engine import (
    SCHEMA_VERSION,
    ConfigValidationError,
    EngineEvent,
    EngineExitCode,
    EngineRequest,
    EngineRunSpec,
    EngineSummary,
    HeadlessEngineService,
    InfrastructureRuntimeError,
)
from .metrics_service import MetricsService
from .multi_run import MultiRunState, advance_after_run_result, stream_multi_run
from .ghost_policy import GhostModeResolution, resolve_ghost_mode
from .report_service import ReportService

__all__ = [
    "AiGenerationRequest",
    "AiGenerationResult",
    "AiIntegrationSettings",
    "AiProvider",
    "AiProviderConfig",
    "AiProviderError",
    "AuditService",
    "CIProvenance",
    "ConfigValidationError",
    "DashboardDataFreshness",
    "DashboardHeadlineKpis",
    "DashboardOverview",
    "DashboardRecentRun",
    "DashboardReportLink",
    "DashboardReportLinks",
    "DashboardRollup",
    "DashboardRollupSummary",
    "DashboardService",
    "DashboardTrendIndicator",
    "DeltaComparisonError",
    "DeltaComparisonResult",
    "DeltaComparisonService",
    "DeltaStatusSummary",
    "detect_ci_environment",
    "detect_ci_provenance",
    "EngineEvent",
    "FailureAnalysisService",
    "FailureAnalysisSummary",
    "FailureContext",
    "FailureContextBudget",
    "EngineExitCode",
    "EngineRequest",
    "EngineRunSpec",
    "EngineSummary",
    "HeadlessEngineService",
    "IncompatibleRunDataError",
    "InfrastructureRuntimeError",
    "InvalidRunIdError",
    "MetricDelta",
    "MetricsService",
    "MultiRunState",
    "GhostModeResolution",
    "InMemoryAiSettingsStore",
    "ReportService",
    "ProviderMisconfiguredError",
    "ProviderRateLimitError",
    "ProviderTimeoutError",
    "ProviderUnavailableError",
    "UnsupportedProviderModelError",
    "RunLogLine",
    "SCHEMA_VERSION",
    "apply_completed_multi_run",
    "build_failure_context",
    "advance_after_run_result",
    "iter_drained_queue_items",
    "load_run_specs_from_yaml",
    "resolve_ghost_mode",
    "build_ai_provider",
    "RunNotFoundComparisonError",
    "stream_multi_run",
]
