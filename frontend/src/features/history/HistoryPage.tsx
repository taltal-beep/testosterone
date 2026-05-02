import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { apiClient } from "../../lib/api-client";

export function HistoryPage() {
  const runsQuery = useQuery({
    queryKey: ["runs"],
    queryFn: () => apiClient.listRuns()
  });

  if (runsQuery.isLoading) {
    return <p>Loading run history...</p>;
  }
  if (runsQuery.isError) {
    return <p>Failed to load runs.</p>;
  }

  return (
    <section>
      <h2>Run History</h2>
      <ul>
        {runsQuery.data.items.map((run) => (
          <li key={run.run_id}>
            <Link to={`/runs/${run.run_id}`}>{run.run_id}</Link> - status={run.status ?? "unknown"} rc={run.returncode}
          </li>
        ))}
      </ul>
    </section>
  );
}
