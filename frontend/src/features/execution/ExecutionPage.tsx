import { FormEvent, useMemo, useState } from "react";

import { apiClient } from "../../lib/api-client";
import { subscribeToExecutionEvents } from "../../lib/sse-client";

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
    <section>
      <h2>Execution</h2>
      <form onSubmit={onSubmit}>
        <label>
          Target Repo
          <input value={targetRepo} onChange={(e) => setTargetRepo(e.target.value)} />
        </label>
        <label>
          Test Type
          <select value={testType} onChange={(e) => setTestType(e.target.value as typeof testType)}>
            <option value="pytest">pytest</option>
            <option value="behavex">behavex</option>
            <option value="behave_native">behave_native</option>
            <option value="locust">locust</option>
          </select>
        </label>
        <label>
          CLI Args
          <input value={cliArgs} onChange={(e) => setCliArgs(e.target.value)} />
        </label>
        <button type="submit">Run</button>
      </form>
      <p>Status: {status}</p>
      {executionId ? <p>Execution ID: {executionId}</p> : null}
      <pre data-testid="log-console">{consoleText}</pre>
      {summary ? <pre data-testid="summary-json">{JSON.stringify(summary, null, 2)}</pre> : null}
    </section>
  );
}
