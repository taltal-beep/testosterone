export function formatRunTimestamp(createdAtSeconds: number): string {
  return new Date(createdAtSeconds * 1000).toLocaleString(undefined, {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit"
  });
}

export function formatRunName(cycle: string | null, createdAtSeconds: number): string {
  return `${cycle ?? "run"} — ${formatRunTimestamp(createdAtSeconds)}`;
}
