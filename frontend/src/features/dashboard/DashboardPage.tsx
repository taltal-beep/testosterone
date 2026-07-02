import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { DashboardTrendIndicator, apiClient } from "../../lib/api-client";

export function DashboardPage() {
  const overviewQuery = useQuery({
    queryKey: ["dashboard-overview"],
    queryFn: () => apiClient.getDashboardOverview(6)
  });

  if (overviewQuery.isLoading) {
    return <p className="text-sm text-slate-300">Loading dashboard overview...</p>;
  }
  if (overviewQuery.isError) {
    return <p className="text-sm text-red-400">Failed to load dashboard overview.</p>;
  }

  const data = overviewQuery.data;
  if (!data) {
    return <p className="text-sm text-slate-300">No dashboard data available.</p>;
  }
  const recentRuns = data.recent_runs ?? [];
  const latestRunId = data.headline_kpis?.latest_run_id;

  return (
    <section className="space-y-4">
      <header className="space-y-1">
        <h2 className="text-xl font-semibold">Dashboard Overview</h2>
        <p className="text-sm text-slate-300">
          Health, reliability, and performance at a glance with direct drill-down paths.
        </p>
        {data.data_freshness?.degraded ? (
          <p role="status" className="text-sm text-amber-400">
            Some metrics are degraded: {data.data_freshness.notes?.join(", ") || "unknown source issue"}.
          </p>
        ) : null}
      </header>

      <div className="grid gap-3 sm:grid-cols-2">
        <KpiCard label="Health" value={formatPct(data.headline_kpis.health_pct)} trend={data.trend_indicators.health} />
        <KpiCard
          label="Failed"
          value={formatInt(data.headline_kpis.fail_count)}
          trend={data.trend_indicators.failed_count}
          lowerIsBetter
        />
        <KpiCard
          label="Pass Count"
          value={formatInt(data.headline_kpis.pass_count)}
          trend={{ direction: "unknown", delta_abs: null, delta_pct: null }}
        />
        <KpiCard
          label="Duration"
          value={formatMs(data.headline_kpis.duration_ms)}
          trend={data.trend_indicators.duration}
          lowerIsBetter
        />
      </div>

      <section className="rounded-lg border border-slate-800 bg-slate-900/40 p-4">
        <h3 className="mb-2 text-sm font-semibold text-slate-200">Rollups</h3>
        <ul className="space-y-1 text-sm text-slate-300">
          <li>
            <strong className="text-slate-200">Reliability</strong>: {renderSummary(data.reliability_rollup.status_summary)}
          </li>
          <li>
            <strong className="text-slate-200">Performance</strong>: {renderSummary(data.performance_rollup.status_summary)}
          </li>
        </ul>
      </section>

      <section className="rounded-lg border border-slate-800 bg-slate-900/40 p-4">
        <h3 className="mb-2 text-sm font-semibold text-slate-200">Quick Links</h3>
        <ul className="space-y-1 text-sm">
          {latestRunId ? (
            <li>
              <Link to={`/runs/${latestRunId}`} className="text-indigo-400 hover:text-indigo-300">
                Latest run details
              </Link>
            </li>
          ) : (
            <li className="text-slate-400">Latest run details unavailable</li>
          )}
          {recentRuns[0]?.compare_url ? (
            <li>
              <Link to={recentRuns[0].compare_url} className="text-indigo-400 hover:text-indigo-300">
                Compare latest two runs
              </Link>
            </li>
          ) : (
            <li className="text-slate-400">Compare view unavailable</li>
          )}
          <li className="text-slate-300">{reportLink("Allure report", data.report_links?.allure ?? { url: null, state: "unknown" })}</li>
          <li className="text-slate-300">{reportLink("Locust report", data.report_links?.locust ?? { url: null, state: "unknown" })}</li>
          <li className="text-slate-300">{reportLink("Behave report", data.report_links?.behave ?? { url: null, state: "unknown" })}</li>
        </ul>
      </section>

      <section className="rounded-lg border border-slate-800 bg-slate-900/40 p-4">
        <h3 className="mb-2 text-sm font-semibold text-slate-200">Recent Runs</h3>
        {recentRuns.length === 0 ? (
          <p className="text-sm text-slate-400">No recent runs available.</p>
        ) : (
          <ul className="space-y-2">
            {recentRuns.map((run) => (
              <li key={run.run_id} className="rounded border border-slate-800 bg-slate-950 p-2 text-sm text-slate-300">
                <Link to={run.run_detail_url} className="font-mono text-indigo-400 hover:text-indigo-300">
                  {run.run_id}
                </Link>{" "}
                status={run.status ?? "unknown"} rc={run.returncode} health=
                {formatPct(run.health_pct)}
              </li>
            ))}
          </ul>
        )}
      </section>
    </section>
  );
}

function KpiCard({
  label,
  value,
  trend,
  lowerIsBetter = false
}: {
  label: string;
  value: string;
  trend: DashboardTrendIndicator;
  lowerIsBetter?: boolean;
}) {
  const semantic = trendSemantic(trend, lowerIsBetter);
  const trendColor =
    semantic.label === "improved"
      ? "text-emerald-400"
      : semantic.label === "regressed"
        ? "text-red-400"
        : "text-slate-400";
  return (
    <article className="rounded-lg border border-slate-800 bg-slate-900/40 p-4">
      <strong className="text-sm font-medium text-slate-300">{label}</strong>
      <p className="my-1 text-2xl font-semibold text-white">{value}</p>
      <p data-testid={`${label.toLowerCase().replace(/\s+/g, "-")}-trend`} className={`text-xs ${trendColor}`}>
        Trend: {semantic.label}
      </p>
    </article>
  );
}

export function trendSemantic(
  trend: DashboardTrendIndicator,
  lowerIsBetter: boolean
): { label: "improved" | "regressed" | "flat" | "unknown" } {
  if (trend.direction === "unknown") {
    return { label: "unknown" };
  }
  if (trend.direction === "flat") {
    return { label: "flat" };
  }
  if (lowerIsBetter) {
    return { label: trend.direction === "down" ? "improved" : "regressed" };
  }
  return { label: trend.direction === "up" ? "improved" : "regressed" };
}

function renderSummary(summary: { regressions: number; improvements: number; unchanged: number; unknown: number }) {
  return `regressions=${summary.regressions} improvements=${summary.improvements} unchanged=${summary.unchanged} unknown=${summary.unknown}`;
}

function reportLink(
  label: string,
  report: { url: string | null; state: "available" | "missing" | "unknown" }
) {
  if (report.state === "available" && report.url) {
    return (
      <a href={report.url} target="_blank" rel="noreferrer" className="text-indigo-400 hover:text-indigo-300">
        {label}
      </a>
    );
  }
  if (report.state === "unknown") {
    return `${label} (state unknown)`;
  }
  return `${label} (not available)`;
}

function formatPct(value: number | null): string {
  if (value == null) {
    return "n/a";
  }
  return `${value.toFixed(2)}%`;
}

function formatMs(value: number | null): string {
  if (value == null) {
    return "n/a";
  }
  return `${value.toFixed(0)} ms`;
}

function formatInt(value: number | null): string {
  if (value == null) {
    return "n/a";
  }
  return `${Math.round(value)}`;
}
