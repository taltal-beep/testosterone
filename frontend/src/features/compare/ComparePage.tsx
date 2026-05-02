import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { DeltaMetricNode, apiClient } from "../../lib/api-client";

const RELIABILITY_ORDER: Array<{ key: keyof ReturnType<typeof getReliabilityMetrics>; label: string }> = [
  { key: "total_tests", label: "Total Tests" },
  { key: "passed", label: "Passed" },
  { key: "failed", label: "Failed" },
  { key: "broken", label: "Broken" },
  { key: "skipped", label: "Skipped" },
  { key: "health_pct", label: "Health %" }
];

const PERFORMANCE_ORDER: Array<{ key: keyof ReturnType<typeof getPerformanceMetrics>; label: string }> = [
  { key: "wall_duration_ms", label: "Wall Duration (ms)" },
  { key: "metrics_duration_ms", label: "Metrics Duration (ms)" },
  { key: "avg_case_ms", label: "Avg Case (ms)" }
];

export function ComparePage() {
  const [searchParams] = useSearchParams();
  const [currentRunId, setCurrentRunId] = useState(searchParams.get("current_run_id") ?? "");
  const [baselineRunId, setBaselineRunId] = useState(searchParams.get("baseline_run_id") ?? "");
  const runsQuery = useQuery({
    queryKey: ["runs"],
    queryFn: () => apiClient.listRuns()
  });
  const compareQuery = useQuery({
    queryKey: ["delta-comparison", currentRunId, baselineRunId],
    queryFn: () => apiClient.getDeltaComparison(currentRunId, baselineRunId),
    enabled: Boolean(currentRunId && baselineRunId && currentRunId !== baselineRunId)
  });

  const options = useMemo(() => runsQuery.data?.items ?? [], [runsQuery.data?.items]);

  if (runsQuery.isLoading) {
    return <p>Loading runs for comparison...</p>;
  }
  if (runsQuery.isError) {
    return <p>Failed to load runs for comparison.</p>;
  }
  if (options.length < 2) {
    return <p>At least two completed runs are required for comparison.</p>;
  }

  const comparisonReady = Boolean(currentRunId && baselineRunId && currentRunId !== baselineRunId);
  const payload = compareQuery.data;

  return (
    <section>
      <h2>Run Comparison</h2>
      <p>Select baseline and current runs to identify regressions and improvements.</p>
      <div style={{ display: "flex", gap: "1rem", marginBottom: "1rem" }}>
        <label>
          Current run
          <select
            aria-label="Current run"
            value={currentRunId}
            onChange={(event) => setCurrentRunId(event.target.value)}
            style={{ marginLeft: "0.5rem" }}
          >
            <option value="">Select run</option>
            {options.map((run) => (
              <option key={run.run_id} value={run.run_id}>
                {run.run_id}
              </option>
            ))}
          </select>
        </label>
        <label>
          Baseline run
          <select
            aria-label="Baseline run"
            value={baselineRunId}
            onChange={(event) => setBaselineRunId(event.target.value)}
            style={{ marginLeft: "0.5rem" }}
          >
            <option value="">Select run</option>
            {options.map((run) => (
              <option key={run.run_id} value={run.run_id}>
                {run.run_id}
              </option>
            ))}
          </select>
        </label>
      </div>

      {!comparisonReady && <p>Select two different runs to start comparison.</p>}
      {comparisonReady && compareQuery.isLoading && <p>Loading delta comparison...</p>}
      {comparisonReady && compareQuery.isError && <p>Failed to load delta comparison.</p>}
      {comparisonReady && payload && (
        <>
          <p>
            Comparing <strong>{payload.comparison.current_run_id}</strong> against baseline{" "}
            <strong>{payload.comparison.baseline_run_id}</strong>.
          </p>
          <h3>Reliability</h3>
          <ul>
            {RELIABILITY_ORDER.map(({ key, label }) => (
              <li key={key}>
                <strong>{label}</strong>: <MetricRow metric={getReliabilityMetrics(payload)[key]} />
              </li>
            ))}
          </ul>
          <h3>Performance</h3>
          <ul>
            {PERFORMANCE_ORDER.map(({ key, label }) => (
              <li key={key}>
                <strong>{label}</strong>: <MetricRow metric={getPerformanceMetrics(payload)[key]} />
              </li>
            ))}
          </ul>
          <h3>Status Summary</h3>
          <p>
            regressions={payload.status_summary.regressions.length} improvements={payload.status_summary.improvements.length}{" "}
            unchanged={payload.status_summary.unchanged.length} unknown={payload.status_summary.unknown.length}
          </p>
          <h3>Highlights</h3>
          {payload.highlights.length === 0 ? (
            <p>No major changes detected.</p>
          ) : (
            <ul>
              {payload.highlights.map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
          )}
        </>
      )}
    </section>
  );
}

function MetricRow({ metric }: { metric: DeltaMetricNode }) {
  const absolute = metric.absolute_delta == null ? "n/a" : metric.absolute_delta.toFixed(2);
  const relative = metric.relative_delta_pct == null ? "n/a" : `${metric.relative_delta_pct.toFixed(2)}%`;
  const reason = metric.reason ? ` (${metric.reason})` : "";
  return (
    <span>
      current={formatMetricValue(metric.current_value, metric.unit)} baseline={formatMetricValue(metric.baseline_value, metric.unit)} delta=
      {absolute} relative={relative} state={metric.classification}
      {reason}
    </span>
  );
}

function formatMetricValue(value: number | null, unit: DeltaMetricNode["unit"]): string {
  if (value == null) {
    return "n/a";
  }
  if (unit === "tests") {
    return `${Math.round(value)}`;
  }
  if (unit === "pct") {
    return `${value.toFixed(2)}%`;
  }
  return `${value.toFixed(2)}ms`;
}

function getReliabilityMetrics(payload: Awaited<ReturnType<typeof apiClient.getDeltaComparison>>) {
  return payload.metrics.reliability;
}

function getPerformanceMetrics(payload: Awaited<ReturnType<typeof apiClient.getDeltaComparison>>) {
  return payload.metrics.performance;
}

