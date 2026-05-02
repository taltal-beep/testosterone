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
  const aiSummaryQuery = useQuery({
    queryKey: ["run-ai-summary", runId],
    queryFn: () => apiClient.getRunAiSummary(runId),
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
      <h3>AI Failure Summary</h3>
      {runQuery.data.run.returncode === 0 ? (
        <p>Summary only applies to failed runs.</p>
      ) : aiSummaryQuery.isLoading ? (
        <p>Loading AI summary...</p>
      ) : aiSummaryQuery.isError ? (
        <p>Failed to load AI summary.</p>
      ) : aiSummaryQuery.data.status === "available" ? (
        <article>
          <p>{aiSummaryQuery.data.summary_text}</p>
          <p>
            Confidence: {aiSummaryQuery.data.confidence ?? "unknown"} | Model: {aiSummaryQuery.data.model ?? "unknown"}
          </p>
        </article>
      ) : (
        <p>No summary generated ({aiSummaryQuery.data.error_code ?? "not_available"}).</p>
      )}
      <button
        type="button"
        onClick={async () => {
          await apiClient.generateRunAiSummary(runId, true);
          await aiSummaryQuery.refetch();
        }}
      >
        Generate AI Summary
      </button>
      <Link to="/history">Back to history</Link>
    </section>
  );
}
