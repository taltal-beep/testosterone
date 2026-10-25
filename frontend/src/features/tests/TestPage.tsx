import { useQuery } from "@tanstack/react-query";
import { Link, useParams, useSearchParams } from "react-router-dom";

import { apiClient, type TestPointItem } from "../../lib/api-client";
import { Badge, Card, KeyValue, PageHeader, Spinner } from "../../components/ui";
import { countLabel, formatDuration, formatRunTime, shortRunId } from "../../lib/format";

const FAILED = new Set(["failed", "broken"]);

function statusTone(status: string): "success" | "danger" | "neutral" {
  if (status === "passed") return "success";
  return FAILED.has(status) ? "danger" : "neutral";
}

/** One bar per run, oldest on the left, height by duration and colour by outcome. */
function DurationBars({ points }: { points: TestPointItem[] }) {
  const oldestFirst = [...points].reverse();
  const longest = Math.max(1, ...oldestFirst.map((p) => p.duration_ms ?? 0));
  return (
    <div className="flex h-24 items-end gap-1" role="img" aria-label="Duration per run, oldest first">
      {oldestFirst.map((p) => (
        <span
          key={p.run_id}
          title={`${formatRunTime(p.created_at)} · ${p.status} · ${formatDuration(p.duration_ms)}`}
          className={`min-w-1.5 max-w-8 flex-1 rounded-t ${p.status === "passed" ? "bg-success-500/80" : FAILED.has(p.status) ? "bg-danger-500/80" : "bg-ink-600"}`}
          style={{ height: `${Math.max(4, ((p.duration_ms ?? 0) / longest) * 100)}%` }}
        />
      ))}
    </div>
  );
}

/** One test across its cycle's recent runs: outcome per run, duration trend and its last failure. */
export function TestPage() {
  const { name: cycle = "" } = useParams();
  const [searchParams] = useSearchParams();
  const key = searchParams.get("key") ?? "";
  const query = useQuery({
    queryKey: ["test-history", cycle, key],
    queryFn: () => apiClient.getTestHistory(cycle, key),
    enabled: Boolean(cycle && key)
  });

  const back = (
    <Link to={`/cycles/${encodeURIComponent(cycle)}`} className="text-sm text-brand-300 hover:underline">
      Back to {cycle || "the cycle"}
    </Link>
  );

  if (!key) {
    return <p className="text-sm text-ink-300">No test picked. {back}</p>;
  }
  if (query.isLoading) {
    return (
      <div className="flex items-center gap-2 text-sm text-ink-300">
        <Spinner /> Loading test history…
      </div>
    );
  }
  if (query.isError || !query.data) {
    return (
      <p className="text-sm text-danger-400">
        Couldn't find this test in the recent runs of {cycle}. It may have been renamed or removed. {back}
      </p>
    );
  }

  const { test, points, last_failure: lastFailure, owners, issue_url: issueUrl } = query.data;
  const passRate = test.runs > 0 ? Math.round((100 * test.passed) / test.runs) : null;

  return (
    <section className="space-y-4">
      <PageHeader
        title={
          <span className="flex flex-wrap items-center gap-3">
            <span className="break-all">{test.name}</span>
            <Badge tone={statusTone(test.last_status)}>last: {test.last_status}</Badge>
            {test.flaky ? <Badge tone="brand">Flaky</Badge> : null}
          </span>
        }
        subtitle={
          passRate != null
            ? `Passed ${test.passed} of ${countLabel(test.runs, "run")} (${passRate}%) in ${cycle}`
            : `No recorded outcome in ${cycle}`
        }
        actions={
          <span className="flex flex-wrap items-center gap-3">
            {issueUrl ? (
              <a href={issueUrl} target="_blank" rel="noreferrer" className="text-sm text-brand-300 hover:underline">
                Open an issue
              </a>
            ) : null}
            {back}
          </span>
        }
      />

      {lastFailure ? (
        <Card title="Last failure">
          <p className="break-words font-mono text-xs text-danger-300">{lastFailure.message || "No failure message recorded."}</p>
          <p className="mt-2 text-xs text-ink-400">
            <Link to={`/runs/${lastFailure.run_id}`} className="text-brand-300 hover:underline">
              Run {shortRunId(lastFailure.run_id)}
            </Link>{" "}
            · {formatRunTime(lastFailure.created_at)}
            {lastFailure.branch ? ` · ${lastFailure.branch}` : ""}
          </p>
        </Card>
      ) : null}

      <Card title="Duration">
        <DurationBars points={points} />
        <p className="mt-2 text-xs text-ink-400">
          Median {formatDuration(test.median_duration_ms)}
          {test.slowdown_ms != null
            ? `, and ${formatDuration(test.slowdown_ms)} slower over the last runs${test.slowdown_pct != null ? ` (+${test.slowdown_pct}%)` : ""}`
            : ""}
          .
        </p>
      </Card>

      <Card title={`Runs (${points.length})`}>
        <ul className="divide-y divide-white/5 text-sm">
          {points.map((p) => (
            <li key={p.run_id} className="flex flex-wrap items-center gap-x-3 gap-y-1 py-2 first:pt-0 last:pb-0">
              <Badge tone={statusTone(p.status)}>{p.status}</Badge>
              <Link to={`/runs/${p.run_id}`} className="text-brand-300 hover:underline">
                {formatRunTime(p.created_at)}
              </Link>
              <span className="text-xs text-ink-400">{formatDuration(p.duration_ms)}</span>
              {p.branch ? <span className="font-mono text-xs text-ink-400">{p.branch}</span> : null}
              {p.message && FAILED.has(p.status) ? (
                <span className="w-full break-words font-mono text-xs text-danger-300">{p.message}</span>
              ) : null}
            </li>
          ))}
        </ul>
      </Card>

      <Card title="Details">
        <KeyValue
          items={[
            { label: "Full name", value: <span className="break-all font-mono text-xs">{test.full_name || "—"}</span> },
            { label: "Group", value: test.group },
            { label: "Stage", value: test.stage || "—" },
            { label: "Owners", value: owners.length > 0 ? owners.join(", ") : "No CODEOWNERS rule matches this test" }
          ]}
        />
      </Card>
    </section>
  );
}
