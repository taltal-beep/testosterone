import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { DashboardTrendIndicator, apiClient } from "../../lib/api-client";
import { Badge, Card, PageHeader, Spinner, StatusPill } from "../../components/ui";
import { MuscleShrug } from "../../components/mascot";

export function DashboardPage() {
  const overviewQuery = useQuery({
    queryKey: ["dashboard-overview"],
    queryFn: () => apiClient.getDashboardOverview(6)
  });

  if (overviewQuery.isLoading) {
    return (
      <div className="flex items-center gap-2 text-sm text-ink-300">
        <Spinner /> Loading dashboard overview...
      </div>
    );
  }
  if (overviewQuery.isError) {
    return <p className="text-sm text-danger-400">Failed to load dashboard overview.</p>;
  }

  const data = overviewQuery.data;
  if (!data) {
    return <p className="text-sm text-ink-300">No dashboard data available.</p>;
  }
  const recentRuns = data.recent_runs ?? [];
  const latestRunId = data.headline_kpis?.latest_run_id;

  // First-run experience: nothing has ever executed, so guide instead of showing n/a walls.
  if (!latestRunId && recentRuns.length === 0) {
    return <FirstRunGuide />;
  }

  return (
    <section className="space-y-5">
      <PageHeader
        title="Dashboard"
        subtitle="Health, reliability, and performance at a glance."
      />
      {data.data_freshness?.degraded ? (
        <p role="status" className="rounded-md border border-warn-500/40 bg-warn-500/10 px-3 py-2 text-sm text-warn-300">
          Some metrics are degraded: {data.data_freshness.notes?.join(", ") || "unknown source issue"}.
        </p>
      ) : null}

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
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

      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Rollups">
          <ul className="space-y-2 text-sm text-ink-300">
            <li className="flex flex-wrap items-center gap-2">
              <strong className="text-ink-100">Reliability</strong>
              <RollupBadges summary={data.reliability_rollup.status_summary} />
            </li>
            <li className="flex flex-wrap items-center gap-2">
              <strong className="text-ink-100">Performance</strong>
              <RollupBadges summary={data.performance_rollup.status_summary} />
            </li>
          </ul>
        </Card>

        <Card title="Quick Links">
          <ul className="space-y-1.5 text-sm">
            {latestRunId ? (
              <li>
                <Link to={`/runs/${latestRunId}`} className="text-brand-300 hover:text-brand-400 hover:underline">
                  Latest run details
                </Link>
              </li>
            ) : (
              <li className="text-ink-400">Latest run details unavailable</li>
            )}
            {recentRuns[0]?.compare_url ? (
              <li>
                <Link to={recentRuns[0].compare_url} className="text-brand-300 hover:text-brand-400 hover:underline">
                  Compare latest two runs
                </Link>
              </li>
            ) : (
              <li className="text-ink-400">Compare view unavailable</li>
            )}
            <li className="text-ink-300">{reportLink("Allure report", data.report_links?.allure ?? { url: null, state: "unknown" })}</li>
            <li className="text-ink-300">{reportLink("Locust report", data.report_links?.locust ?? { url: null, state: "unknown" })}</li>
            <li className="text-ink-300">{reportLink("Behave report", data.report_links?.behave ?? { url: null, state: "unknown" })}</li>
          </ul>
        </Card>
      </div>

      <Card title="Recent Runs">
        {recentRuns.length === 0 ? (
          <p className="text-sm text-ink-400">No recent runs available.</p>
        ) : (
          <ul className="divide-y divide-ink-800">
            {recentRuns.map((run) => (
              <li key={run.run_id} className="flex flex-wrap items-center justify-between gap-2 py-2.5 text-sm">
                <div className="flex items-center gap-3">
                  <StatusPill status={run.status ?? "unknown"} returncode={run.returncode} />
                  <Link to={run.run_detail_url} className="font-mono text-brand-300 hover:text-brand-400 hover:underline">
                    {run.run_id}
                  </Link>
                </div>
                <div className="flex items-center gap-3 text-xs text-ink-400">
                  <span>health {formatPct(run.health_pct)}</span>
                  {run.compare_url ? (
                    <Link to={run.compare_url} className="text-brand-300 hover:underline">
                      compare
                    </Link>
                  ) : null}
                </div>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </section>
  );
}

function FirstRunGuide() {
  return (
    <section className="space-y-6">
      <PageHeader title="Welcome to Testo" subtitle="Three steps to your first quality cycle." />
      <div className="flex flex-col items-center gap-2 py-4">
        <MuscleShrug size={112} />
        <p className="text-sm text-ink-300">No runs yet — let&apos;s change that.</p>
      </div>
      <ol className="grid gap-4 md:grid-cols-3" data-testid="first-run-guide">
        <GuideStep
          step={1}
          title="Check system health"
          body="The dot in the top-right corner shows engine readiness. Green means go."
        />
        <GuideStep
          step={2}
          title="Pick a cycle"
          body={
            <>
              Browse the cycles defined in your config —{" "}
              <Link to="/cycles" className="text-brand-300 hover:underline">
                see what you have
              </Link>
              .
            </>
          }
        />
        <GuideStep
          step={3}
          title="Run it"
          body="Hit Run on any cycle card and watch stages stream live. Results land here."
        />
      </ol>
    </section>
  );
}

function GuideStep({ step, title, body }: { step: number; title: string; body: React.ReactNode }) {
  return (
    <li>
      <Card className="h-full">
        <span className="inline-flex h-7 w-7 items-center justify-center rounded-full bg-brand-600/20 font-mono text-sm font-bold text-brand-300">
          {step}
        </span>
        <h3 className="mt-2 text-sm font-semibold text-ink-100">{title}</h3>
        <p className="mt-1 text-sm text-ink-300">{body}</p>
      </Card>
    </li>
  );
}

function RollupBadges({
  summary
}: {
  summary: { regressions: number; improvements: number; unchanged: number; unknown: number };
}) {
  return (
    <span className="flex flex-wrap gap-1.5">
      <Badge tone={summary.regressions > 0 ? "danger" : "neutral"}>{summary.regressions} regressions</Badge>
      <Badge tone={summary.improvements > 0 ? "success" : "neutral"}>{summary.improvements} improvements</Badge>
      <Badge>{summary.unchanged} unchanged</Badge>
      <Badge>{summary.unknown} unknown</Badge>
    </span>
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
      ? "text-success-400"
      : semantic.label === "regressed"
        ? "text-danger-400"
        : "text-ink-400";
  return (
    <article className="rounded-xl border border-ink-700 bg-ink-900 p-4">
      <strong className="text-sm font-medium text-ink-300">{label}</strong>
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

function reportLink(
  label: string,
  report: { url: string | null; state: "available" | "missing" | "unknown" }
) {
  if (report.state === "available" && report.url) {
    return (
      <a href={report.url} target="_blank" rel="noreferrer" className="text-brand-300 hover:text-brand-400 hover:underline">
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
