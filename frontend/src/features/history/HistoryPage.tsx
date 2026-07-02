import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { apiClient } from "../../lib/api-client";

export function HistoryPage() {
  const runsQuery = useQuery({
    queryKey: ["runs"],
    queryFn: () => apiClient.listRuns()
  });

  if (runsQuery.isLoading) {
    return <p className="text-sm text-slate-300">Loading run history...</p>;
  }
  if (runsQuery.isError) {
    return <p className="text-sm text-red-400">Failed to load runs.</p>;
  }

  return (
    <section className="space-y-4">
      <header className="space-y-1">
        <h2 className="text-xl font-semibold">Run History</h2>
        {runsQuery.data.items.length >= 2 && (
          <p className="text-sm">
            <Link
              to={`/compare?current_run_id=${runsQuery.data.items[0].run_id}&baseline_run_id=${runsQuery.data.items[1].run_id}`}
              className="text-indigo-400 hover:text-indigo-300"
            >
              Compare latest two runs
            </Link>
          </p>
        )}
      </header>
      <ul className="space-y-2">
        {runsQuery.data.items.map((run) => (
          <li key={run.run_id} className="rounded border border-slate-800 bg-slate-900/40 p-3 text-sm text-slate-300">
            <Link to={`/runs/${run.run_id}`} className="font-mono text-indigo-400 hover:text-indigo-300">
              {run.run_id}
            </Link>{" "}
            - status={run.status ?? "unknown"} rc={run.returncode}
          </li>
        ))}
      </ul>
    </section>
  );
}
