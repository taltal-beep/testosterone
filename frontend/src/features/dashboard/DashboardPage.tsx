import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { DashboardTrendIndicator, apiClient } from "../../lib/api-client";

export function DashboardPage() {
  const overviewQuery = useQuery({
    queryKey: ["dashboard-overview"],
    queryFn: () => apiClient.getDashboardOverview(6)
  });

  if (overviewQuery.isLoading) {
    return <p>Loading dashboard overview...</p>;
  }
  if (overviewQuery.isError) {
    return <p>Failed to load dashboard overview.</p>;
  }

  const data = overviewQuery.data;
  const recentRuns = data.recent_runs;
  const latestRunId = data.headline_kpis.latest_run_id;

  return (
    <section>
      <h2>Dashboard Overview</h2>
      <p>Health, reliability, and performance at a glance with direct drill-down paths.</p>
      {data.data_freshness.degraded ? (
        <p role="status">Some metrics are degraded: {data.data_freshness.notes.join(", ") || "unknown source issue"}.</p>
      ) : null}

      <div style={{ display: "grid", gridTemplateColumns: "repeat(2, minmax(0, 1fr))", gap: "0.75rem" }}>
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

      <h3 style={{ marginTop: "1rem" }}>Rollups</h3>
      <ul>
        <li>
          <strong>Reliability</strong>: {renderSummary(data.reliability_rollup.status_summary)}
        </li>
        <li>
          <strong>Performance</strong>: {renderSummary(data.performance_rollup.status_summary)}
        </li>
      </ul>

      <h3>Quick Links</h3>
      <ul>
        {latestRunId ? (
          <li>
            <Link to={`/runs/${latestRunId}`}>Latest run details</Link>
          </li>
        ) : (
          <li>Latest run details unavailable</li>
        )}
        {recentRuns[0]?.compare_url ? (
          <li>
            <Link to={recentRuns[0].compare_url}>Compare latest two runs</Link>
          </li>
        ) : (
          <li>Compare view unavailable</li>
        )}
        <li>{reportLink("Allure report", data.report_links.allure)}</li>
        <li>{reportLink("Locust report", data.report_links.locust)}</li>
        <li>{reportLink("Behave report", data.report_links.behave)}</li>
      </ul>

      <h3>Recent Runs</h3>
      {recentRuns.length === 0 ? (
        <p>No recent runs available.</p>
      ) : (
        <ul>
          {recentRuns.map((run) => (
            <li key={run.run_id}>
              <Link to={run.run_detail_url}>{run.run_id}</Link> status={run.status ?? "unknown"} rc={run.returncode} health=
              {formatPct(run.health_pct)}
            </li>
          ))}
        </ul>
      )}
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
  return (
    <article style={{ border: "1px solid #ccc", borderRadius: "0.5rem", padding: "0.75rem" }}>
      <strong>{label}</strong>
      <p style={{ margin: "0.35rem 0" }}>{value}</p>
      <p data-testid={`${label.toLowerCase().replace(/\s+/g, "-")}-trend`}>Trend: {semantic.label}</p>
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
      <a href={report.url} target="_blank" rel="noreferrer">
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
