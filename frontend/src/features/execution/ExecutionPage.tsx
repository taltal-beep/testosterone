import { FormEvent, useMemo, useState } from "react";

import { apiClient } from "../../lib/api-client";
import { subscribeToExecutionEvents } from "../../lib/sse-client";

const inputClass = "rounded border border-slate-800 bg-slate-950 px-3 py-2 text-sm text-slate-100";
const labelClass = "grid gap-1 text-xs font-medium text-slate-300";

export function ExecutionPage() {
  const [targetRepo, setTargetRepo] = useState(".");
  const [testType, setTestType] = useState<"pytest" | "behavex" | "behave_native" | "locust">("pytest");
  const [cliArgs, setCliArgs] = useState("-q");
  const [executionId, setExecutionId] = useState<string | null>(null);
  const [status, setStatus] = useState<string>("idle");
  const [logs, setLogs] = useState<string[]>([]);
  const [summary, setSummary] = useState<Record<string, unknown> | null>(null);

  const consoleText = useMemo(() => logs.join("\n"), [logs]);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setLogs([]);
    setSummary(null);
    setStatus("starting");
    const created = await apiClient.createExecution({
      runs: [{ test_type: testType, target_repo: targetRepo, cli_args: cliArgs ? cliArgs.split(" ") : [] }]
    });
    setExecutionId(created.execution_id);
    setStatus(created.status);
    const unsubscribe = subscribeToExecutionEvents(created.events_url, {
      onEvent: (evt) => {
        if (evt.event === "log") {
          setLogs((prev) => [...prev, `[${evt.data.stream}] ${evt.data.line}`]);
        } else if (evt.event === "run_result") {
          setLogs((prev) => [...prev, `[run_result] ${evt.data.run_id ?? "unknown"} rc=${evt.data.returncode}`]);
        } else {
          setSummary(evt.data);
          setStatus(String(evt.data.exit_code === 0 ? "completed" : "failed"));
          unsubscribe();
        }
      },
      onError: () => {
        setStatus("error");
        unsubscribe();
      }
    });
  }

  return (
    <section className="space-y-4">
      <header className="space-y-1">
        <h2 className="text-xl font-semibold">Execution</h2>
      </header>

      <form onSubmit={onSubmit} className="grid gap-3 rounded-lg border border-slate-800 bg-slate-900/40 p-4">
        <label className={labelClass}>
          Target Repo
          <input className={inputClass} value={targetRepo} onChange={(e) => setTargetRepo(e.target.value)} />
        </label>
        <label className={labelClass}>
          Test Type
          <select className={inputClass} value={testType} onChange={(e) => setTestType(e.target.value as typeof testType)}>
            <option value="pytest">pytest</option>
            <option value="behavex">behavex</option>
            <option value="behave_native">behave_native</option>
            <option value="locust">locust</option>
          </select>
        </label>
        <label className={labelClass}>
          CLI Args
          <input className={inputClass} value={cliArgs} onChange={(e) => setCliArgs(e.target.value)} />
        </label>
        <div>
          <button
            type="submit"
            className="rounded bg-indigo-600 px-3 py-2 text-sm font-medium text-white hover:bg-indigo-500"
          >
            Run
          </button>
        </div>
      </form>

      <div className="text-sm text-slate-300">
        Status: <span className="font-mono">{status}</span>
      </div>
      {executionId ? <p className="text-xs text-slate-400">Execution ID: {executionId}</p> : null}
      <pre
        data-testid="log-console"
        className="max-h-[420px] overflow-auto whitespace-pre-wrap break-words rounded-lg border border-slate-800 bg-slate-950 p-3 text-xs text-slate-200"
      >
        {consoleText}
      </pre>
      {summary ? (
        <pre
          data-testid="summary-json"
          className="max-h-[420px] overflow-auto whitespace-pre-wrap break-words rounded-lg border border-slate-800 bg-slate-950 p-3 text-xs text-slate-200"
        >
          {JSON.stringify(summary, null, 2)}
        </pre>
      ) : null}
    </section>
  );
}
