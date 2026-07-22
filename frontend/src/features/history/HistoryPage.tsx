import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { apiClient } from "../../lib/api-client";
import { Button, EmptyState, PageHeader, Spinner, StatusPill } from "../../components/ui";
import { MuscleShrug } from "../../components/mascot";
import { formatRunName } from "../../lib/format";

export function HistoryPage() {
  const runsQuery = useQuery({
    queryKey: ["runs"],
    queryFn: () => apiClient.listRuns()
  });

  if (runsQuery.isLoading) {
    return (
      <div className="flex items-center gap-2 text-sm text-ink-300">
        <Spinner /> Loading run history...
      </div>
    );
  }
  if (runsQuery.isError) {
    return <p className="text-sm text-danger-400">Failed to load runs.</p>;
  }

  const items = runsQuery.data?.items ?? [];

  return (
    <section>
      <PageHeader
        title="Runs"
        subtitle="Every archived cycle run, newest first."
        actions={
          items.length >= 2 ? (
            <Link to={`/compare?current_run_id=${items[0].run_id}&baseline_run_id=${items[1].run_id}`}>
              <Button variant="secondary" size="sm">
                Compare latest two
              </Button>
            </Link>
          ) : undefined
        }
      />
      {items.length === 0 ? (
        <EmptyState
          mascot={<MuscleShrug />}
          title="No runs yet"
          message="Run a cycle and its archived result will show up here."
          action={
            <Link to="/cycles">
              <Button size="sm">Browse cycles</Button>
            </Link>
          }
        />
      ) : (
        <ul className="divide-y divide-ink-800 rounded-xl border border-ink-700 bg-ink-900">
          {items.map((run) => (
            <li key={run.run_id} className="flex flex-wrap items-center justify-between gap-2 px-4 py-3 text-sm">
              <div className="flex items-center gap-3">
                <StatusPill status={run.status ?? "unknown"} returncode={run.returncode} />
                <Link to={`/runs/${run.run_id}`} className="text-brand-300 hover:text-brand-400 hover:underline">
                  {formatRunName(run.cycle, run.created_at)}
                </Link>
                <span className="font-mono text-xs text-ink-500">{run.run_id}</span>
              </div>
              <span className="text-xs text-ink-400">
                {run.health_pct != null ? `health ${run.health_pct.toFixed(2)}%` : ""}
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
