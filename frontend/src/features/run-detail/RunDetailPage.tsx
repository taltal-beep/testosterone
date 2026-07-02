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
    return <p className="text-sm text-red-400">Missing run id.</p>;
  }
  if (runQuery.isLoading || reportsQuery.isLoading) {
    return <p className="text-sm text-slate-300">Loading run details...</p>;
  }
  if (runQuery.isError || reportsQuery.isError) {
    return <p className="text-sm text-red-400">Failed to load run details.</p>;
  }

  return (
    <section className="space-y-4">
      <header className="space-y-1">
        <h2 className="text-xl font-semibold">Run Details</h2>
        <p className="text-sm text-slate-300">Run ID: {runQuery.data.run.run_id}</p>
        <p className="text-sm text-slate-300">Type: {runQuery.data.run.test_kind}</p>
        <p className="text-sm text-slate-300">Return code: {runQuery.data.run.returncode}</p>
      </header>

      <section className="rounded-lg border border-slate-800 bg-slate-900/40 p-4">
        <h3 className="mb-2 text-sm font-semibold text-slate-200">Report Links</h3>
        <ul className="space-y-1 text-sm">
          {Object.entries(reportsQuery.data.static_links).map(([name, url]) => (
            <li key={name}>
              <a href={url} target="_blank" rel="noreferrer" className="text-indigo-400 hover:text-indigo-300">
                {name}
              </a>
            </li>
          ))}
        </ul>
      </section>

      <section className="rounded-lg border border-slate-800 bg-slate-900/40 p-4">
        <h3 className="mb-2 text-sm font-semibold text-slate-200">Artifacts</h3>
        <ul className="space-y-1 text-sm text-slate-300">
          {reportsQuery.data.artifact_links.map((artifact) => (
            <li key={artifact} className="font-mono text-xs">{artifact}</li>
          ))}
        </ul>
      </section>

      <section className="rounded-lg border border-slate-800 bg-slate-900/40 p-4">
        <h3 className="mb-2 text-sm font-semibold text-slate-200">AI Failure Summary</h3>
        {runQuery.data.run.returncode === 0 ? (
          <p className="text-sm text-slate-400">Summary only applies to failed runs.</p>
        ) : aiSummaryQuery.isLoading ? (
          <p className="text-sm text-slate-300">Loading AI summary...</p>
        ) : aiSummaryQuery.isError ? (
          <p className="text-sm text-red-400">Failed to load AI summary.</p>
        ) : aiSummaryQuery.data.status === "available" ? (
          <article className="space-y-1">
            <p className="text-sm text-slate-200">{aiSummaryQuery.data.summary_text}</p>
            <p className="text-xs text-slate-400">
              Confidence: {aiSummaryQuery.data.confidence ?? "unknown"} | Model: {aiSummaryQuery.data.model ?? "unknown"}
            </p>
          </article>
        ) : (
          <p className="text-sm text-slate-400">No summary generated ({aiSummaryQuery.data.error_code ?? "not_available"}).</p>
        )}
        <button
          type="button"
          onClick={async () => {
            await apiClient.generateRunAiSummary(runId, true);
            await aiSummaryQuery.refetch();
          }}
          className="mt-3 rounded bg-indigo-600 px-3 py-2 text-sm font-medium text-white hover:bg-indigo-500"
        >
          Generate AI Summary
        </button>
      </section>

      <Link to="/history" className="text-sm text-indigo-400 hover:text-indigo-300">
        Back to history
      </Link>
    </section>
  );
}
