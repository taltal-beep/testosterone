import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { CaseChangeKind, DeltaClassification, DeltaMetricNode, apiClient } from "../../lib/api-client";
import { formatRunName } from "../../lib/format";
import { StackedBar, type StackedBarSegment } from "../../components/ui";

const CASE_KIND_TONE: Record<CaseChangeKind, string> = {
  regression: "text-danger-300",
  fix: "text-success-300",
  added: "text-brand-300",
  removed: "text-warn-300",
  status_change: "text-ink-300"
};

const CASE_KIND_LABELS: CaseChangeKind[] = ["regression", "fix", "added", "removed", "status_change"];

const CLASSIFICATION_TONE: Record<DeltaClassification, string> = {
  regression: "text-danger-300",
  improvement: "text-success-300",
  neutral: "text-ink-300",
  unknown: "text-ink-400"
};

const CLASSIFICATION_BADGE: Record<DeltaClassification, string> = {
  regression: "border-danger-400/40 bg-danger-400/10 text-danger-300",
  improvement: "border-success-400/40 bg-success-400/10 text-success-300",
  neutral: "border-ink-700 text-ink-300",
  unknown: "border-ink-700 text-ink-400"
};

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

const selectClass = "rounded border border-ink-700 bg-ink-950 px-3 py-2 text-sm text-ink-100";
const labelClass = "grid gap-1 text-xs font-medium text-ink-300";

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
  const runLabel = (runId: string) => {
    const run = options.find((item) => item.run_id === runId);
    return run ? formatRunName(run.cycle ?? null, run.created_at) : runId;
  };

  if (runsQuery.isLoading) {
    return <p className="text-sm text-ink-300">Loading runs for comparison...</p>;
  }
  if (runsQuery.isError) {
    return <p className="text-sm text-danger-400">Failed to load runs for comparison.</p>;
  }
  if (options.length < 2) {
    return <p className="text-sm text-ink-300">At least two completed runs are required for comparison.</p>;
  }

  const comparisonReady = Boolean(currentRunId && baselineRunId && currentRunId !== baselineRunId);
  const payload = compareQuery.data;

  return (
    <section className="space-y-4">
      <header className="space-y-1">
        <h2 className="text-xl font-semibold">Run Comparison</h2>
        <p className="text-sm text-ink-300">Select baseline and current runs to identify regressions and improvements.</p>
      </header>

      <div className="flex flex-wrap gap-4 rounded-xl border border-ink-700 bg-ink-900 p-4">
        <label className={labelClass}>
          Current run
          <select
            aria-label="Current run"
            value={currentRunId}
            onChange={(event) => setCurrentRunId(event.target.value)}
            className={selectClass}
          >
            <option value="">Select run</option>
            {options.map((run) => (
              <option key={run.run_id} value={run.run_id}>
                {formatRunName(run.cycle ?? null, run.created_at)}
              </option>
            ))}
          </select>
        </label>
        <label className={labelClass}>
          Baseline run
          <select
            aria-label="Baseline run"
            value={baselineRunId}
            onChange={(event) => setBaselineRunId(event.target.value)}
            className={selectClass}
          >
            <option value="">Select run</option>
            {options.map((run) => (
              <option key={run.run_id} value={run.run_id}>
                {formatRunName(run.cycle ?? null, run.created_at)}
              </option>
            ))}
          </select>
        </label>
      </div>

      {!comparisonReady && <p className="text-sm text-ink-400">Select two different runs to start comparison.</p>}
      {comparisonReady && compareQuery.isLoading && <p className="text-sm text-ink-300">Loading delta comparison...</p>}
      {comparisonReady && compareQuery.isError && <p className="text-sm text-danger-400">Failed to load delta comparison.</p>}
      {comparisonReady && payload && (
        <>
          <p className="text-sm text-ink-300">
            Comparing <strong className="text-ink-100">{runLabel(payload.comparison.current_run_id)}</strong> against
            baseline <strong className="text-ink-100">{runLabel(payload.comparison.baseline_run_id)}</strong>.
          </p>

          <section className="rounded-xl border border-ink-700 bg-ink-900 p-4">
            <h3 className="mb-3 text-sm font-semibold text-ink-100">Outcome Mix</h3>
            <div className="space-y-3">
              <div>
                <p className="mb-1 text-xs font-medium text-ink-400">
                  Baseline ({runLabel(payload.comparison.baseline_run_id)})
                </p>
                <StackedBar segments={outcomeSegments(getReliabilityMetrics(payload), "baseline_value")} />
              </div>
              <div>
                <p className="mb-1 text-xs font-medium text-ink-400">
                  Current ({runLabel(payload.comparison.current_run_id)})
                </p>
                <StackedBar segments={outcomeSegments(getReliabilityMetrics(payload), "current_value")} />
              </div>
            </div>
          </section>

          <MetricTable title="Reliability" rows={RELIABILITY_ORDER} metrics={getReliabilityMetrics(payload)} />
          <MetricTable title="Performance" rows={PERFORMANCE_ORDER} metrics={getPerformanceMetrics(payload)} />

          {(payload.stage_deltas ?? []).length > 0 && (
            <section className="rounded-xl border border-ink-700 bg-ink-900 p-4">
              <h3 className="mb-2 text-sm font-semibold text-ink-100">Per-Stage Health</h3>
              <table className="w-full text-left text-sm text-ink-300">
                <thead>
                  <tr className="text-xs text-ink-400">
                    <th className="pb-1 pr-2 font-medium">Stage</th>
                    <th className="pb-1 pr-2 font-medium">Baseline</th>
                    <th className="pb-1 pr-2 font-medium">Current</th>
                    <th className="pb-1 font-medium">Delta</th>
                  </tr>
                </thead>
                <tbody>
                  {payload.stage_deltas.map((stage) => (
                    <tr key={stage.stage_name} className="border-t border-ink-800">
                      <td className="py-1.5 pr-2 text-ink-100">
                        {stage.stage_name}
                        {stage.framework ? <span className="ml-2 text-xs text-ink-400">{stage.framework}</span> : null}
                      </td>
                      <td className="py-1.5 pr-2 font-mono text-xs">
                        {stage.baseline_health_pct != null ? `${stage.baseline_health_pct.toFixed(1)}%` : "n/a"}
                      </td>
                      <td className="py-1.5 pr-2 font-mono text-xs">
                        {stage.current_health_pct != null ? `${stage.current_health_pct.toFixed(1)}%` : "n/a"}
                      </td>
                      <td className={`py-1.5 font-mono text-xs ${CLASSIFICATION_TONE[stage.classification]}`}>
                        {stage.health_pct_delta != null ? `${stage.health_pct_delta > 0 ? "+" : ""}${stage.health_pct_delta.toFixed(1)}pp` : "n/a"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
          )}

          <TestLevelChanges currentRunId={payload.comparison.current_run_id} baselineRunId={payload.comparison.baseline_run_id} />

          <section className="rounded-xl border border-ink-700 bg-ink-900 p-4">
            <h3 className="mb-2 text-sm font-semibold text-ink-100">Status Summary</h3>
            <div className="flex flex-wrap gap-2 text-xs">
              <SummaryBadge tone="regression" count={payload.status_summary.regressions.length} label="regressions" />
              <SummaryBadge tone="improvement" count={payload.status_summary.improvements.length} label="improvements" />
              <SummaryBadge tone="neutral" count={payload.status_summary.unchanged.length} label="unchanged" />
              <SummaryBadge tone="unknown" count={payload.status_summary.unknown.length} label="unknown" />
            </div>
          </section>

          <section className="rounded-xl border border-ink-700 bg-ink-900 p-4">
            <h3 className="mb-2 text-sm font-semibold text-ink-100">Highlights</h3>
            {payload.highlights.length === 0 ? (
              <p className="text-sm text-ink-400">No major changes detected.</p>
            ) : (
              <ul className="space-y-1 text-sm text-ink-300">
                {payload.highlights.map((line) => (
                  <li key={line}>{line}</li>
                ))}
              </ul>
            )}
          </section>
        </>
      )}
    </section>
  );
}

function MetricTable({
  title,
  rows,
  metrics
}: {
  title: string;
  rows: Array<{ key: string; label: string }>;
  metrics: Record<string, DeltaMetricNode>;
}) {
  return (
    <section className="rounded-xl border border-ink-700 bg-ink-900 p-4">
      <h3 className="mb-2 text-sm font-semibold text-ink-100">{title}</h3>
      <table className="w-full text-left text-sm text-ink-300">
        <thead>
          <tr className="text-xs text-ink-400">
            <th className="pb-1 pr-2 font-medium">Metric</th>
            <th className="pb-1 pr-2 font-medium">Baseline</th>
            <th className="pb-1 pr-2 font-medium">Current</th>
            <th className="pb-1 font-medium">Change</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(({ key, label }) => {
            const metric = metrics[key];
            return (
              <tr key={key} className="border-t border-ink-800">
                <td className="py-1.5 pr-2 text-ink-100">{label}</td>
                <td className="py-1.5 pr-2 font-mono text-xs">{formatMetricValue(metric.baseline_value, metric.unit)}</td>
                <td className="py-1.5 pr-2 font-mono text-xs">{formatMetricValue(metric.current_value, metric.unit)}</td>
                <td className={`py-1.5 font-mono text-xs ${CLASSIFICATION_TONE[metric.classification]}`}>{formatChange(metric)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </section>
  );
}

function formatChange(metric: DeltaMetricNode): string {
  if (metric.absolute_delta == null) {
    return "n/a";
  }
  if (metric.absolute_delta === 0) {
    return "no change";
  }
  const sign = metric.absolute_delta > 0 ? "+" : "\u2212";
  const magnitude = formatMetricValue(Math.abs(metric.absolute_delta), metric.unit);
  const relative = metric.relative_delta_pct == null ? "" : ` (${sign}${Math.abs(metric.relative_delta_pct).toFixed(1)}%)`;
  return `${sign}${magnitude}${relative}`;
}

function SummaryBadge({ tone, count, label }: { tone: DeltaClassification; count: number; label: string }) {
  return (
    <span className={`rounded-full border px-2.5 py-0.5 ${CLASSIFICATION_BADGE[tone]}`}>
      {count} {label}
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

function outcomeSegments(
  reliability: ReturnType<typeof getReliabilityMetrics>,
  field: "current_value" | "baseline_value"
): StackedBarSegment[] {
  return [
    { label: "Passed", value: reliability.passed[field] ?? 0, colorClass: "bg-success-400" },
    { label: "Failed", value: reliability.failed[field] ?? 0, colorClass: "bg-danger-400" },
    { label: "Broken", value: reliability.broken[field] ?? 0, colorClass: "bg-danger-300" },
    { label: "Skipped", value: reliability.skipped[field] ?? 0, colorClass: "bg-warn-400" }
  ];
}

function getPerformanceMetrics(payload: Awaited<ReturnType<typeof apiClient.getDeltaComparison>>) {
  return payload.metrics.performance;
}

function TestLevelChanges({ currentRunId, baselineRunId }: { currentRunId: string; baselineRunId: string }) {
  const [expanded, setExpanded] = useState(false);
  const [kindFilter, setKindFilter] = useState<CaseChangeKind | "all">("all");

  const casesQuery = useQuery({
    queryKey: ["delta-case-changes", currentRunId, baselineRunId],
    queryFn: () => apiClient.getDeltaCaseChanges(currentRunId, baselineRunId),
    enabled: expanded
  });

  const changes = casesQuery.data?.changes ?? [];
  const filtered = kindFilter === "all" ? changes : changes.filter((c) => c.kind === kindFilter);
  const grouped = useMemo(() => {
    const byGroup = new Map<string, typeof filtered>();
    for (const change of filtered) {
      const list = byGroup.get(change.group) ?? [];
      list.push(change);
      byGroup.set(change.group, list);
    }
    return [...byGroup.entries()].sort(([a], [b]) => a.localeCompare(b));
  }, [filtered]);

  return (
    <section className="rounded-xl border border-ink-700 bg-ink-900 p-4">
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="flex items-center gap-2 text-sm font-semibold text-ink-100"
        aria-expanded={expanded}
      >
        <span className={`transition-transform ${expanded ? "rotate-90" : ""}`}>&#9656;</span>
        Test-Level Changes
      </button>
      <p className="mt-1 text-xs text-ink-400">
        Computed on demand from each run&apos;s artifact snapshot (per-test added/removed/regression/fix), same as{" "}
        <code>testo diff</code>.
      </p>

      {expanded && (
        <div className="mt-3 space-y-3">
          <div className="flex flex-wrap gap-2">
            <FilterButton label="All" active={kindFilter === "all"} onClick={() => setKindFilter("all")} />
            {CASE_KIND_LABELS.map((kind) => (
              <FilterButton key={kind} label={kind} active={kindFilter === kind} onClick={() => setKindFilter(kind)} />
            ))}
          </div>

          {casesQuery.isLoading && <p className="text-sm text-ink-300">Loading test-level changes...</p>}
          {casesQuery.isError && <p className="text-sm text-danger-400">Failed to load test-level changes.</p>}
          {casesQuery.data && filtered.length === 0 && (
            <p className="text-sm text-ink-400">No matching test changes.</p>
          )}
          {grouped.map(([group, groupChanges]) => (
            <div key={group}>
              <p className="mb-1 font-mono text-xs text-ink-400">{group}</p>
              <ul className="space-y-1 border-l border-ink-800 pl-3">
                {groupChanges.map((change) => (
                  <li key={change.key} className="flex flex-wrap items-center gap-2 text-sm">
                    <span className={`text-xs font-semibold uppercase ${CASE_KIND_TONE[change.kind]}`}>{change.kind}</span>
                    <span className="text-ink-100">{change.name}</span>
                    <span className="font-mono text-xs text-ink-400">
                      {change.baseline_status ?? "—"} → {change.current_status ?? "—"}
                      {change.duration_delta_ms != null ? ` (${change.duration_delta_ms >= 0 ? "+" : ""}${change.duration_delta_ms}ms)` : ""}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

function FilterButton({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-full border px-3 py-1 text-xs font-medium capitalize ${
        active ? "border-brand-400 bg-brand-500/20 text-brand-200" : "border-ink-700 text-ink-300 hover:border-ink-600"
      }`}
    >
      {label}
    </button>
  );
}
