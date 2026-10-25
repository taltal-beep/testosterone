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

/** "1 regression", "3 regressions": a count with its noun in the right number. */
export function countLabel(count: number, singular: string, plural = `${singular}s`): string {
  return `${count} ${count === 1 ? singular : plural}`;
}

/** A duration the way people read it: "850 ms" under a second, "6.4 s" under a minute, then "2 min 5 s". */
export function formatDuration(ms: number | null | undefined): string {
  if (ms == null || !Number.isFinite(ms)) return "n/a";
  if (ms < 1000) return `${Math.round(ms)} ms`;
  const seconds = ms / 1000;
  if (seconds < 60) return `${seconds.toFixed(1)} s`;
  const minutes = Math.floor(seconds / 60);
  return `${minutes} min ${Math.round(seconds - minutes * 60)} s`;
}

/** What an engine exit code means (Architecture Overview § Exit code contract). */
export function describeExitCode(code: number | null | undefined): string {
  switch (code) {
    case null:
    case undefined:
      return "n/a";
    case 0:
      return "0 (passed)";
    case 1:
      return "1 (tests failed)";
    case 2:
      return "2 (invalid config or input)";
    case 3:
      return "3 (infrastructure error)";
    case 4:
      return "4 (internal error)";
    default:
      return String(code);
  }
}

/** The per-test page: `/cycles/<cycle>/test?key=<key>` (keys can hold any character). */
export function testPath(cycle: string, key: string): string {
  return `/cycles/${encodeURIComponent(cycle)}/test?${new URLSearchParams({ key }).toString()}`;
}

/**
 * A percentage as a whole number ("80%"), except that a value just under 100
 * or just over 0 keeps one decimal, so a run with one failure never reads 100%.
 */
export function formatPercent(value: number | null | undefined): string {
  if (value == null) return "n/a";
  const whole = Math.round(value);
  if (whole === 100 && value < 100) return `${Math.floor(value * 10) / 10}%`;
  if (whole === 0 && value > 0) return `${Math.ceil(value * 10) / 10}%`;
  return `${whole}%`;
}
