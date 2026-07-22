export function Spinner({ className }: { className?: string }) {
  return (
    <span
      role="status"
      aria-label="Loading"
      className={`inline-block h-4 w-4 animate-spin rounded-full border-2 border-ink-500 border-t-brand-400 ${className ?? ""}`}
    />
  );
}
