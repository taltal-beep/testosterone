export type RunUiStatus =
  | "queued"
  | "running"
  | "passed"
  | "failed"
  | "aborted"
  | "completed"
  | "unknown";

const STATUS_STYLES: Record<RunUiStatus, { dot: string; text: string; label: string }> = {
  queued: { dot: "bg-ink-400", text: "text-ink-300", label: "Queued" },
  running: { dot: "bg-brand-400 animate-pulse", text: "text-brand-300", label: "Running" },
  passed: { dot: "bg-success-400", text: "text-success-300", label: "Passed" },
  completed: { dot: "bg-success-400", text: "text-success-300", label: "Completed" },
  failed: { dot: "bg-danger-400", text: "text-danger-300", label: "Failed" },
  aborted: { dot: "bg-warn-400", text: "text-warn-300", label: "Aborted" },
  unknown: { dot: "bg-ink-500", text: "text-ink-400", label: "Unknown" }
};

export function normalizeRunStatus(value: string | null | undefined, returncode?: number | null): RunUiStatus {
  const v = (value ?? "").toLowerCase();
  if (v in STATUS_STYLES) return v as RunUiStatus;
  if (v === "success" || v === "ok") return "passed";
  if (v === "failure" || v === "error") return "failed";
  if (typeof returncode === "number") return returncode === 0 ? "passed" : "failed";
  return "unknown";
}

export interface StatusPillProps {
  status: RunUiStatus | string;
  returncode?: number | null;
  className?: string;
}

export function StatusPill({ status, returncode, className }: StatusPillProps) {
  const normalized = normalizeRunStatus(String(status), returncode);
  const style = STATUS_STYLES[normalized];
  return (
    <span className={`inline-flex items-center gap-1.5 text-xs font-medium ${style.text} ${className ?? ""}`}>
      <span className={`h-2 w-2 rounded-full ${style.dot}`} aria-hidden />
      {style.label}
    </span>
  );
}
