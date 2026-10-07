/** The minimal shape every run-bearing API item shares (run list, dashboard, detail). */
export interface RunLike {
  run_id: string;
  created_at: number;
  cycle?: string | null;
}

/** The cycle a run belongs to; "run" for records that predate cycle names. */
export function runCycle(run: RunLike): string {
  return run.cycle || "run";
}

/** "Oct 7 03:21" in the viewer's locale and timezone; the year is added when it isn't the current one. */
export function formatRunTime(createdAtSeconds: number): string {
  const date = new Date(createdAtSeconds * 1000);
  const sameYear = date.getFullYear() === new Date().getFullYear();
  const day = date.toLocaleDateString(undefined, { month: "short", day: "numeric", year: sameYear ? undefined : "numeric" });
  const time = date.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit", hourCycle: "h23" });
  return `${day} ${time}`;
}

/** First 8 characters of a run id: enough to tell runs apart, short enough to scan. */
export function shortRunId(runId: string): string {
  return runId.slice(0, 8);
}

/** How a run is named to the user: "fake-api · Oct 7 03:21". The short id is shown alongside, never instead. */
export function formatRunLabel(run: RunLike): string {
  return `${runCycle(run)} · ${formatRunTime(run.created_at)}`;
}
