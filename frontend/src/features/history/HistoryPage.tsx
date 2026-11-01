import { useQuery } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router-dom";

import { apiClient } from "../../lib/api-client";
import { formatPercent, passRateLine } from "../../lib/format";
import { Button, EmptyState, PageHeader, RunLabel, Spinner, StatusPill } from "../../components/ui";
import { MuscleShrug } from "../../components/mascot";

const selectClass =
  "rounded-xl border border-ink-600 bg-ink-950/80 px-3 py-2 text-sm text-ink-100 focus:border-brand-500 focus:outline-none";

export function HistoryPage() {
  const [params, setParams] = useSearchParams();
  const cycle = params.get("cycle") ?? "";
  const runsQuery = useQuery({
    queryKey: ["runs", cycle],
    queryFn: () => apiClient.listRuns(cycle || undefined)
  });
  const cyclesQuery = useQuery({ queryKey: ["cycles"], queryFn: () => apiClient.listCycles() });
  const cycleNames = (cyclesQuery.data?.items ?? []).map((item) => item.name);

  function pickCycle(name: string) {
    setParams(name ? { cycle: name } : {}, { replace: true });
  }

  if (runsQuery.isLoading) {
    return (
      <div className="flex items-center gap-2 text-sm text-ink-300">
        <Spinner /> Loading run history...
      </div>
    );
  }
  if (runsQuery.isError) {
    return <p className="text-sm text-danger-400">Couldn't load runs. Check that the API is running, then reload.</p>;
  }

  const items = runsQuery.data?.items ?? [];
  // Baseline must come from the same cycle; comparing different cycles reports every test as removed.
  const latest = items[0];
  const baseline = latest?.cycle ? items.slice(1).find((run) => run.cycle === latest.cycle) : undefined;

  return (
    <section>
      <PageHeader
        title="Runs"
        subtitle={cycle ? `Runs of ${cycle}, newest first.` : "Every recorded run, newest first."}
        actions={
          latest && baseline ? (
            <Link to={`/compare?current_run_id=${latest.run_id}&baseline_run_id=${baseline.run_id}`}>
              <Button variant="secondary" size="sm">
                Compare latest two
              </Button>
            </Link>
          ) : undefined
        }
      />
      <div className="mb-4 flex flex-wrap items-end gap-3">
        <div className="grid gap-1">
          <label htmlFor="runs-cycle" className="text-xs font-medium text-ink-300">
            Cycle
          </label>
          <select id="runs-cycle" className={selectClass} value={cycle} onChange={(event) => pickCycle(event.target.value)}>
            <option value="">All cycles</option>
            {[...new Set([...cycleNames, ...(cycle ? [cycle] : [])])].map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </select>
        </div>
        {cycle && items.length > 0 ? (
          <p className="pb-2 text-sm text-ink-200" data-testid="pass-rate">
            {passRateLine(items)}
          </p>
        ) : null}
      </div>
      {items.length === 0 && cycle ? (
        <p className="text-sm text-ink-400">No recorded runs of {cycle} yet.</p>
      ) : items.length === 0 ? (
        <EmptyState
          mascot={<MuscleShrug />}
          title="No runs yet"
          message="Run a cycle or record a report with testo ingest, and it will show up here."
          action={
            <Link to="/cycles">
              <Button size="sm">Browse cycles</Button>
            </Link>
          }
        />
      ) : (
        <ul className="divide-y divide-white/5 glass-card">
          {items.map((run) => (
            <li key={run.run_id} className="flex flex-wrap items-center justify-between gap-2 px-4 py-3 text-sm">
              <div className="flex min-w-0 items-center gap-3">
                <StatusPill status={run.status ?? "unknown"} returncode={run.returncode} />
                <RunLabel run={run} linked relative />
              </div>
              <span className="text-xs text-ink-400">
                {run.health_pct != null ? `${formatPercent(run.health_pct)} passed` : ""}
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
