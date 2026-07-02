export interface ExecutionRequest {
  runs: Array<{
    test_type: "pytest" | "behavex" | "behave_native" | "locust";
    target_repo: string;
    cli_args?: string[];
    timeout_s?: number;
  }>;
  persist?: boolean;
  trigger_source?: "ui";
  ci_mode?: boolean;
}

export interface ExecutionAccepted {
  execution_id: string;
  status: "queued" | "running";
  events_url: string;
  summary_url: string;
}

export interface CycleExecutionRequest {
  config_path?: string | null;
  artifacts_root?: string | null;
  stream?: boolean;
  persist?: boolean;
  fail_fast?: boolean;
  force?: boolean;
  workers_override?: number | null;
  report_db?: boolean;
  async_report_db?: boolean;
  reporter_override?: string[] | null;
}

export interface CycleExecutionAccepted {
  execution_id: string;
  status: "queued" | "running";
  events_url: string;
  summary_url: string;
}

export interface ExecutionStatus {
  execution_id: string;
  status: "queued" | "running" | "completed" | "failed";
  summary: Record<string, unknown> | null;
  run_ids: string[];
  error: string | null;
}

export interface RunListItem {
  run_id: string;
  created_at: number;
  returncode: number;
  status: string | null;
  health_pct: number | null;
  links_under_static: Record<string, string>;
}

export type DeltaClassification = "regression" | "improvement" | "neutral" | "unknown";

export interface DeltaMetricNode {
  current_value: number | null;
  baseline_value: number | null;
  absolute_delta: number | null;
  relative_delta_pct: number | null;
  classification: DeltaClassification;
  reason: string | null;
  direction: "higher_is_better" | "lower_is_better";
  unit: "tests" | "pct" | "ms";
}

export interface DeltaComparisonResponse {
  comparison: {
    current_run_id: string;
    baseline_run_id: string;
    current_test_kind: string;
    baseline_test_kind: string;
  };
  metrics: {
    reliability: {
      total_tests: DeltaMetricNode;
      passed: DeltaMetricNode;
      failed: DeltaMetricNode;
      broken: DeltaMetricNode;
      skipped: DeltaMetricNode;
      health_pct: DeltaMetricNode;
    };
    performance: {
      wall_duration_ms: DeltaMetricNode;
      metrics_duration_ms: DeltaMetricNode;
      avg_case_ms: DeltaMetricNode;
    };
  };
  status_summary: {
    regressions: string[];
    improvements: string[];
    unchanged: string[];
    unknown: string[];
  };
  highlights: string[];
}

export interface RunDetailResponse {
  run: {
    run_id: string;
    test_kind: string;
    returncode: number;
    created_at: number;
    started_at: number;
    finished_at: number;
    wall_duration_ms: number;
    health_pct: number | null;
  };
}

export interface AiConfigStatus {
  enabled: boolean;
  configured: boolean;
  provider: "openai" | "anthropic";
  model: string;
  api_key_source: "env" | "runtime_input";
  api_key_env_var: string | null;
  key_present: boolean | null;
  timeout_s: number;
  retry_count: number;
  max_input_chars: number;
  max_output_tokens: number;
}

export interface UpdateAiConfigRequest {
  enabled: boolean;
  provider: "openai" | "anthropic";
  model: string;
  api_key_source: "env" | "runtime_input";
  api_key_env_var?: string | null;
  api_key_input?: string;
  timeout_s: number;
  retry_count: number;
  max_input_chars: number;
  max_output_tokens: number;
}

export interface AiSummaryResponse {
  schema_version: "v1";
  run_id: string;
  status: "available" | "no_summary_generated";
  summary_text: string | null;
  confidence: "low" | "medium" | "high" | null;
  limitations: string[];
  provider: string | null;
  model: string | null;
  generated_at: number;
  context_stats: Record<string, number>;
  error_code: string | null;
}

export interface DashboardTrendIndicator {
  direction: "up" | "down" | "flat" | "unknown";
  delta_abs: number | null;
  delta_pct: number | null;
}

export interface DashboardOverviewResponse {
  headline_kpis: {
    latest_run_id: string | null;
    latest_status: string | null;
    health_pct: number | null;
    pass_count: number | null;
    fail_count: number | null;
    duration_ms: number | null;
  };
  trend_indicators: {
    health: DashboardTrendIndicator;
    failed_count: DashboardTrendIndicator;
    duration: DashboardTrendIndicator;
  };
  reliability_rollup: {
    status_summary: {
      regressions: number;
      improvements: number;
      unchanged: number;
      unknown: number;
    };
    top_highlights: string[];
  };
  performance_rollup: {
    status_summary: {
      regressions: number;
      improvements: number;
      unchanged: number;
      unknown: number;
    };
    top_highlights: string[];
  };
  report_links: {
    allure: { url: string | null; state: "available" | "missing" | "unknown" };
    locust: { url: string | null; state: "available" | "missing" | "unknown" };
    behave: { url: string | null; state: "available" | "missing" | "unknown" };
  };
  recent_runs: Array<{
    run_id: string;
    created_at: number;
    status: string | null;
    returncode: number;
    health_pct: number | null;
    duration_ms: number | null;
    run_detail_url: string;
    compare_url: string | null;
  }>;
  data_freshness: {
    generated_at: number;
    source_window_size: number;
    degraded: boolean;
    notes: string[];
  };
}

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init
  });
  if (!resp.ok) {
    throw new Error(`API error ${resp.status}`);
  }
  return (await resp.json()) as T;
}

export const apiClient = {
  createExecution(payload: ExecutionRequest): Promise<ExecutionAccepted> {
    return api<ExecutionAccepted>("/api/v1/executions", {
      method: "POST",
      body: JSON.stringify({
        persist: true,
        trigger_source: "ui",
        ci_mode: false,
        ...payload
      })
    });
  },
  createCycleExecution(cycle: string, payload: CycleExecutionRequest): Promise<CycleExecutionAccepted> {
    return api<CycleExecutionAccepted>(`/api/v1/cycles/${encodeURIComponent(cycle)}/executions`, {
      method: "POST",
      body: JSON.stringify(payload)
    });
  },
  getExecution(executionId: string): Promise<ExecutionStatus> {
    return api<ExecutionStatus>(`/api/v1/executions/${executionId}`);
  },
  listRuns(): Promise<{ items: RunListItem[] }> {
    return api<{ items: RunListItem[] }>("/api/v1/runs");
  },
  getRun(runId: string): Promise<RunDetailResponse> {
    return api<RunDetailResponse>(`/api/v1/runs/${runId}`);
  },
  getRunReports(runId: string): Promise<{ static_links: Record<string, string>; artifact_links: string[] }> {
    return api<{ static_links: Record<string, string>; artifact_links: string[] }>(`/api/v1/runs/${runId}/reports`);
  },
  getDeltaComparison(currentRunId: string, baselineRunId: string): Promise<DeltaComparisonResponse> {
    const params = new URLSearchParams({
      current_run_id: currentRunId,
      baseline_run_id: baselineRunId
    });
    return api<DeltaComparisonResponse>(`/api/v1/analytics/delta?${params.toString()}`);
  },
  getDashboardOverview(recentLimit = 5): Promise<DashboardOverviewResponse> {
    return api<DashboardOverviewResponse>(`/api/v1/dashboard/overview?recent_limit=${recentLimit}`);
  },
  getDashboardRecentRuns(limit = 10): Promise<{ items: DashboardOverviewResponse["recent_runs"]; generated_at: number }> {
    return api<{ items: DashboardOverviewResponse["recent_runs"]; generated_at: number }>(
      `/api/v1/dashboard/runs/recent?limit=${limit}`
    );
  },
  getAiConfigStatus(): Promise<AiConfigStatus> {
    return api<AiConfigStatus>("/api/v1/ai/config/status");
  },
  updateAiConfig(payload: UpdateAiConfigRequest): Promise<AiConfigStatus> {
    return api<AiConfigStatus>("/api/v1/ai/config", {
      method: "PUT",
      body: JSON.stringify(payload)
    });
  },
  getRunAiSummary(runId: string): Promise<AiSummaryResponse> {
    return api<AiSummaryResponse>(`/api/v1/runs/${runId}/ai-summary`);
  },
  generateRunAiSummary(runId: string, forceRefresh = false): Promise<AiSummaryResponse> {
    return api<AiSummaryResponse>(`/api/v1/runs/${runId}/ai-summary:generate`, {
      method: "POST",
      body: JSON.stringify({ force_refresh: forceRefresh })
    });
  }
};
