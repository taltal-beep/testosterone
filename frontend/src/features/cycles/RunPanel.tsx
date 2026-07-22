import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import { apiClient, type CycleExecutionRequest } from "../../lib/api-client";
import { subscribeToCycleExecutionEvents, type CycleNdjsonEvent } from "../../lib/sse-client";
import { Badge, Button, Card, Spinner, StatusPill } from "../../components/ui";
import { MuscleDefeated, MuscleFlex } from "../../components/mascot";

const REPORTERS = ["allure", "extent", "reportportal", "testbeats"] as const;

type RunPhase = "idle" | "starting" | "running" | "passed" | "failed" | "aborted";

type StageRow = {
  stage: string;
  framework?: string;
  index?: number;
  returncode?: number;
  duration_s?: number;
  status: "pending" | "running" | "completed";
};

export interface RunPanelProps {
  /** Pre-selected cycle; when set the dropdown starts on it. */
  initialCycle?: string;
  /** Hide the cycle selector entirely (cycle detail page context). */
  lockCycle?: boolean;
  /** Open the panel ready-to-run (e.g. arriving from a card's Run button). */
  autoFocusRun?: boolean;
}

export function RunPanel({ initialCycle, lockCycle = false }: RunPanelProps) {
  const cyclesQuery = useQuery({
    queryKey: ["cycles"],
    queryFn: () => apiClient.listCycles(),
    enabled: !lockCycle
  });

  const [cycle, setCycle] = useState(initialCycle ?? "");
  const [stream, setStream] = useState(true);
  const [persist, setPersist] = useState(true);
  const [failFast, setFailFast] = useState(false);
  const [force, setForce] = useState(false);

  const [showAdvanced, setShowAdvanced] = useState(false);
  const [workersOverride, setWorkersOverride] = useState("");
  const [reporters, setReporters] = useState<string[]>([]);
  const [reportDb, setReportDb] = useState(true);
  const [asyncReportDb, setAsyncReportDb] = useState(false);
  const [configPath, setConfigPath] = useState("");
  const [artifactsRoot, setArtifactsRoot] = useState("");

  const [phase, setPhase] = useState<RunPhase>("idle");
  const [executionId, setExecutionId] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [exitCode, setExitCode] = useState<number | null>(null);
  const [events, setEvents] = useState<CycleNdjsonEvent[]>([]);
  const [stages, setStages] = useState<Record<string, StageRow>>({});
  const unsubscribeRef = useRef<null | (() => void)>(null);

  useEffect(() => () => unsubscribeRef.current?.(), []);

  // Default the dropdown to the first cycle once loaded.
  useEffect(() => {
    if (!cycle && cyclesQuery.data?.items.length) {
      setCycle(initialCycle ?? cyclesQuery.data.items[0].name);
    }
  }, [cycle, cyclesQuery.data, initialCycle]);

  function applyEvent(evt: CycleNdjsonEvent) {
    setEvents((prev) => [...prev, evt]);
    if (evt.event === "plan_started") {
      setPhase("running");
    }
    if (evt.event === "stage_started") {
      setStages((prev) => ({
        ...prev,
        [evt.stage]: { stage: evt.stage, framework: evt.framework, index: evt.index, status: "running" }
      }));
    }
    if (evt.event === "stage_finished") {
      setStages((prev) => ({
        ...prev,
        [evt.stage]: {
          ...(prev[evt.stage] ?? { stage: evt.stage, status: "pending" }),
          status: "completed",
          returncode: evt.returncode,
          duration_s: evt.duration_s
        }
      }));
    }
    if (evt.event === "plan_aborted") {
      setPhase("aborted");
      stopStream();
    }
    if (evt.event === "plan_finished") {
      setExitCode(evt.exit_code);
      setPhase(evt.exit_code === 0 ? "passed" : "failed");
      stopStream();
    }
    if (evt.event === "error") {
      setErrorMessage(evt.message);
      setPhase("failed");
      stopStream();
    }
  }

  function stopStream() {
    unsubscribeRef.current?.();
    unsubscribeRef.current = null;
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!cycle) return;
    setPhase("starting");
    setErrorMessage(null);
    setExitCode(null);
    setEvents([]);
    setStages({});
    setExecutionId(null);
    stopStream();

    const payload: CycleExecutionRequest = {
      stream,
      persist,
      fail_fast: failFast,
      force,
      report_db: reportDb,
      async_report_db: asyncReportDb
    };
    const workers = Number.parseInt(workersOverride, 10);
    if (Number.isFinite(workers) && workers > 0) payload.workers_override = workers;
    if (reporters.length > 0) payload.reporter_override = reporters;
    if (configPath.trim()) payload.config_path = configPath.trim();
    if (artifactsRoot.trim()) payload.artifacts_root = artifactsRoot.trim();

    try {
      const created = await apiClient.createCycleExecution(cycle, payload);
      setExecutionId(created.execution_id);
      setPhase("running");
      unsubscribeRef.current = subscribeToCycleExecutionEvents(created.events_url, {
        onEvent: applyEvent,
        onError: () => {
          // EventSource fires error on normal server close too; only fail if still mid-run.
          setPhase((current) => (current === "running" || current === "starting" ? "failed" : current));
          stopStream();
        }
      });
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : String(err));
      setPhase("failed");
    }
  }

  const stageRows = useMemo(
    () => Object.values(stages).sort((a, b) => (a.index ?? 0) - (b.index ?? 0)),
    [stages]
  );
  const busy = phase === "starting" || phase === "running";
  const finished = phase === "passed" || phase === "failed" || phase === "aborted";

  return (
    <div className="space-y-4">
      <Card title={lockCycle ? "Run this cycle" : "Run a cycle"}>
        <form onSubmit={onSubmit} className="space-y-4" data-testid="run-panel-form">
          {!lockCycle ? (
            <label className="grid max-w-sm gap-1">
              <span className="text-xs font-medium text-ink-300">Cycle</span>
              <select
                className="rounded-md border border-ink-600 bg-ink-950 px-3 py-2 text-sm text-ink-100"
                value={cycle}
                onChange={(ev) => setCycle(ev.target.value)}
                disabled={cyclesQuery.isLoading || busy}
              >
                {cyclesQuery.isLoading ? <option value="">Loading cycles…</option> : null}
                {(cyclesQuery.data?.items ?? []).map((item) => (
                  <option key={item.name} value={item.name}>
                    {item.name} — {item.stage_count} stage{item.stage_count === 1 ? "" : "s"}
                  </option>
                ))}
              </select>
            </label>
          ) : null}

          <div className="flex flex-wrap gap-4">
            <Toggle label="Live log stream" checked={stream} onChange={setStream} disabled={busy} />
            <Toggle label="Persist run" checked={persist} onChange={setPersist} disabled={busy} />
            <Toggle label="Fail fast" checked={failFast} onChange={setFailFast} disabled={busy} />
            <Toggle label="Force (ignore triggers)" checked={force} onChange={setForce} disabled={busy} />
          </div>

          <div>
            <button
              type="button"
              onClick={() => setShowAdvanced((v) => !v)}
              className="text-xs font-medium text-brand-300 hover:text-brand-400"
              aria-expanded={showAdvanced}
            >
              {showAdvanced ? "▾ Hide advanced options" : "▸ Advanced options"}
            </button>
            {showAdvanced ? (
              <div className="mt-3 grid gap-4 rounded-lg border border-ink-700 bg-ink-950/60 p-4 sm:grid-cols-2">
                <label className="grid gap-1">
                  <span className="text-xs font-medium text-ink-300">Workers override</span>
                  <input
                    type="number"
                    min={1}
                    className="rounded-md border border-ink-600 bg-ink-950 px-3 py-2 text-sm text-ink-100"
                    value={workersOverride}
                    onChange={(ev) => setWorkersOverride(ev.target.value)}
                    placeholder="engine default"
                    disabled={busy}
                  />
                </label>
                <div className="grid gap-1">
                  <span className="text-xs font-medium text-ink-300">Reporters override</span>
                  <div className="flex flex-wrap gap-3 pt-1.5">
                    {REPORTERS.map((rep) => (
                      <Toggle
                        key={rep}
                        label={rep}
                        checked={reporters.includes(rep)}
                        onChange={(checked) =>
                          setReporters((prev) => (checked ? [...prev, rep] : prev.filter((r) => r !== rep)))
                        }
                        disabled={busy}
                      />
                    ))}
                  </div>
                </div>
                <Toggle label="Archive to report DB" checked={reportDb} onChange={setReportDb} disabled={busy} />
                <Toggle
                  label="Archive in background"
                  checked={asyncReportDb}
                  onChange={setAsyncReportDb}
                  disabled={busy || !reportDb}
                />
                <label className="grid gap-1">
                  <span className="text-xs font-medium text-ink-300">Config path</span>
                  <input
                    className="rounded-md border border-ink-600 bg-ink-950 px-3 py-2 font-mono text-sm text-ink-100"
                    value={configPath}
                    onChange={(ev) => setConfigPath(ev.target.value)}
                    placeholder="testosterone.yaml (auto-discover)"
                    disabled={busy}
                  />
                </label>
                <label className="grid gap-1">
                  <span className="text-xs font-medium text-ink-300">Artifacts root</span>
                  <input
                    className="rounded-md border border-ink-600 bg-ink-950 px-3 py-2 font-mono text-sm text-ink-100"
                    value={artifactsRoot}
                    onChange={(ev) => setArtifactsRoot(ev.target.value)}
                    placeholder="artifacts/"
                    disabled={busy}
                  />
                </label>
              </div>
            ) : null}
          </div>

          <div className="flex items-center gap-3">
            <Button type="submit" disabled={busy || !cycle}>
              {busy ? (
                <>
                  <Spinner className="h-3.5 w-3.5 border-white/40 border-t-white" /> Running…
                </>
              ) : (
                "Run cycle"
              )}
            </Button>
            {executionId ? (
              <span className="font-mono text-xs text-ink-400">execution {executionId}</span>
            ) : null}
          </div>
        </form>
      </Card>

      {finished ? (
        <Card>
          <div className="flex items-center gap-4" data-testid="run-outcome">
            {phase === "passed" ? <MuscleFlex size={72} animate /> : <MuscleDefeated size={72} animate />}
            <div>
              <p className="text-base font-semibold text-ink-100">
                {phase === "passed"
                  ? "Cycle passed. Gains secured. 💪"
                  : phase === "aborted"
                    ? "Cycle aborted (fail fast)."
                    : "Cycle failed."}
              </p>
              <p className="mt-0.5 text-sm text-ink-300">
                {exitCode !== null ? `Exit code ${exitCode}. ` : ""}
                {errorMessage ?? ""}
                {persist ? (
                  <>
                    See <Link to="/runs" className="text-brand-300 hover:underline">Runs</Link> for the archived
                    result.
                  </>
                ) : null}
              </p>
            </div>
          </div>
        </Card>
      ) : null}

      {(stageRows.length > 0 || events.length > 0) && (
        <div className="grid gap-4 lg:grid-cols-2">
          <Card title="Stage timeline">
            {stageRows.length === 0 ? (
              <p className="text-sm text-ink-400">Waiting for stage events…</p>
            ) : (
              <ul className="space-y-2">
                {stageRows.map((s) => (
                  <li key={s.stage} className="rounded-md border border-ink-700 bg-ink-950 p-2.5 text-sm">
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-mono text-ink-100">{s.stage}</span>
                      <StatusPill
                        status={s.status === "completed" ? (s.returncode === 0 ? "passed" : "failed") : s.status === "running" ? "running" : "queued"}
                      />
                    </div>
                    <div className="mt-1 flex items-center gap-2 text-xs text-ink-400">
                      {s.framework ? <Badge tone="brand">{s.framework}</Badge> : null}
                      {typeof s.duration_s === "number" ? <span>{s.duration_s.toFixed(1)}s</span> : null}
                      {typeof s.returncode === "number" ? <span>rc={s.returncode}</span> : null}
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </Card>
          <Card title="Event stream">
            <pre className="max-h-[420px] overflow-auto whitespace-pre-wrap break-words rounded-md bg-ink-950 p-3 font-mono text-xs leading-relaxed text-ink-200">
              {events.map((e) => JSON.stringify(e)).join("\n") || "(no events yet)"}
            </pre>
          </Card>
        </div>
      )}
    </div>
  );
}

function Toggle({
  label,
  checked,
  onChange,
  disabled
}: {
  label: string;
  checked: boolean;
  onChange: (value: boolean) => void;
  disabled?: boolean;
}) {
  return (
    <label className={`flex items-center gap-2 text-sm ${disabled ? "text-ink-500" : "text-ink-200"}`}>
      <input
        type="checkbox"
        checked={checked}
        onChange={(ev) => onChange(ev.target.checked)}
        disabled={disabled}
        className="h-4 w-4 rounded border-ink-600 bg-ink-950 accent-brand-500"
      />
      {label}
    </label>
  );
}
