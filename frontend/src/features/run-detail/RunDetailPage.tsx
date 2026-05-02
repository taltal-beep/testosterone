import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";

import { apiClient } from "../../lib/api-client";

export function RunDetailPage() {
  const params = useParams();
  const runId = params.runId ?? "";
  const runQuery = useQuery({
    queryKey: ["run", runId],
    queryFn: () => apiClient.getRun(runId),
    enabled: Boolean(runId)
  });
  const reportsQuery = useQuery({
    queryKey: ["reports", runId],
    queryFn: () => apiClient.getRunReports(runId),
    enabled: Boolean(runId)
  });

  if (!runId) {
    return <p>Missing run id.</p>;
  }
  if (runQuery.isLoading || reportsQuery.isLoading) {
    return <p>Loading run details...</p>;
  }
  if (runQuery.isError || reportsQuery.isError) {
    return <p>Failed to load run details.</p>;
  }

  return (
    <section>
      <h2>Run Details</h2>
      <p>Run ID: {runQuery.data.run.run_id}</p>
      <p>Type: {runQuery.data.run.test_kind}</p>
      <p>Return code: {runQuery.data.run.returncode}</p>
      <h3>Report Links</h3>
      <ul>
        {Object.entries(reportsQuery.data.static_links).map(([name, url]) => (
          <li key={name}>
            <a href={url} target="_blank" rel="noreferrer">
              {name}
            </a>
          </li>
        ))}
      </ul>
      <h3>Artifacts</h3>
      <ul>
        {reportsQuery.data.artifact_links.map((artifact) => (
          <li key={artifact}>{artifact}</li>
        ))}
      </ul>
      <Link to="/history">Back to history</Link>
    </section>
  );
}
