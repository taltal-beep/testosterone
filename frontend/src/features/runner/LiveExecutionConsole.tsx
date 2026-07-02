import { FormEvent, useMemo, useRef, useState } from "react";

import { apiClient } from "../../lib/api-client";
import { subscribeToCycleExecutionEvents, type CycleNdjsonEvent } from "../../lib/sse-client";

type StageRow = {
  stage: string;
  framework?: string;
  index?: number;
  returncode?: number;
  duration_s?: number;
  status: "pending" | "running" | "completed";
};

export function LiveExecutionConsole() {
  const [cycle, setCycle] = useState("sample-pytests");
  const [executionId, setExecutionId] = useState<string | null>(null);
  const [status, setStatus] = useState<string>("idle");
  const [events, setEvents] = useState<Array<{ name: string; raw: Record<string, unknown> }>>([]);
  const [stages, setStages] = useState<Record<string, StageRow>>({});
  const unsubscribeRef = useRef<null | (() => void)>(null);

  const consoleText = useMemo(() => events.map((e) => JSON.stringify(e.raw)).join("\n"), [events]);

  function applyEvent(evt: CycleNdjsonEvent) {
    setEvents((prev) => [...prev, { name: evt.event, raw: evt as unknown as Record<string, unknown> }]);

    if (evt.event === "stage_started") {
      const stage = String((evt as CycleNdjsonEvent & { stage: string }).stage);
      setStages((prev) => ({
        ...prev,
        [stage]: {
          stage,
          framework: String((evt as CycleNdjsonEvent & { framework?: string }).framework ?? ""),
          index: Number((evt as CycleNdjsonEvent & { index?: number }).index ?? 0),
          status: "running"
        }
      }));
    }
    if (evt.event === "stage_finished") {
      const stage = String((evt as CycleNdjsonEvent & { stage: string }).stage);
      setStages((prev) => ({
        ...prev,
        [stage]: {
          ...(prev[stage] ?? { stage, status: "pending" }),
          status: "completed",
          returncode: Number((evt as CycleNdjsonEvent & { returncode?: number }).returncode ?? 0),
          duration_s: Number((evt as CycleNdjsonEvent & { duration_s?: number }).duration_s ?? 0)
        }
      }));
    }
    if (evt.event === "plan_finished") {
      setStatus("completed");
      unsubscribeRef.current?.();
      unsubscribeRef.current = null;
    }
    if (evt.event === "error") {
      setStatus("failed");
      unsubscribeRef.current?.();
      unsubscribeRef.current = null;
    }
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setStatus("starting");
    setEvents([]);
    setStages({});
    unsubscribeRef.current?.();
    unsubscribeRef.current = null;

    const created = await apiClient.createCycleExecution(cycle, {
      persist: true,
      stream: false,
      fail_fast: false,
      force: false
    });

    setExecutionId(created.execution_id);
    setStatus(created.status);
    unsubscribeRef.current = subscribeToCycleExecutionEvents(created.events_url, {
      onEvent: applyEvent,
      onError: () => setStatus("error")
    });
  }

  const stageRows = Object.values(stages).sort((a, b) => (a.index ?? 0) - (b.index ?? 0));

  return (
    <section className="space-y-4">
      <header className="space-y-1">
        <h2 className="text-xl font-semibold">Live Execution Console</h2>
        <p className="text-sm text-slate-300">
          Starts a cycle run and streams NDJSON engine events over SSE (plan/stage lifecycle).
        </p>
      </header>

      <form onSubmit={onSubmit} className="grid gap-3 rounded-lg border border-slate-800 bg-slate-900/40 p-4">
        <label className="grid gap-1">
          <span className="text-xs font-medium text-slate-300">Cycle name</span>
          <input
            className="rounded border border-slate-800 bg-slate-950 px-3 py-2 text-sm"
            value={cycle}
            onChange={(ev) => setCycle(ev.target.value)}
            placeholder="e.g. sample-pytests"
          />
        </label>
        <div className="flex items-center gap-3">
          <button
            type="submit"
            className="rounded bg-indigo-600 px-3 py-2 text-sm font-medium text-white hover:bg-indigo-500"
          >
            Run cycle
          </button>
          <div className="text-sm text-slate-300">
            Status: <span className="font-mono">{status}</span>
          </div>
          {executionId ? (
            <div className="text-xs text-slate-400">
              execution_id: <span className="font-mono">{executionId}</span>
            </div>
          ) : null}
        </div>
      </form>

      <section className="grid gap-3 md:grid-cols-2">
        <div className="rounded-lg border border-slate-800 bg-slate-900/40 p-4">
          <h3 className="mb-2 text-sm font-semibold text-slate-200">Stage timeline</h3>
          {stageRows.length === 0 ? (
            <p className="text-sm text-slate-400">No stage events yet.</p>
          ) : (
            <ul className="space-y-2">
              {stageRows.map((s) => (
                <li key={s.stage} className="rounded border border-slate-800 bg-slate-950 p-2 text-sm">
                  <div className="flex items-center justify-between">
                    <span className="font-mono">{s.stage}</span>
                    <span className="text-xs text-slate-400">{s.status}</span>
                  </div>
                  <div className="mt-1 text-xs text-slate-400">
                    framework={s.framework ?? "?"} rc={s.returncode ?? "?"} duration_s={s.duration_s ?? "?"}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="rounded-lg border border-slate-800 bg-slate-900/40 p-4">
          <h3 className="mb-2 text-sm font-semibold text-slate-200">Raw NDJSON stream</h3>
          <pre className="max-h-[420px] overflow-auto whitespace-pre-wrap break-words rounded bg-slate-950 p-3 text-xs text-slate-200">
            {consoleText || "(no events yet)"}
          </pre>
        </div>
      </section>
    </section>
  );
}

