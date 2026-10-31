import type { ReactNode } from "react";

export interface EmptyStateProps {
  mascot?: ReactNode;
  title: ReactNode;
  message?: ReactNode;
  action?: ReactNode;
  /** Heading level; `h1` when the empty state is the whole page (the 404). */
  headingLevel?: "h1" | "h2";
}

export function EmptyState({ mascot, title, message, action, headingLevel = "h2" }: EmptyStateProps) {
  const Heading = headingLevel;
  return (
    <div className="flex flex-col items-center justify-center gap-3 rounded-xl border border-dashed border-ink-600 bg-ink-900/40 backdrop-blur px-6 py-12 text-center">
      {mascot}
      <Heading className="text-base font-semibold text-ink-100">{title}</Heading>
      {message ? <div className="max-w-md text-sm text-ink-300">{message}</div> : null}
      {action ? <div className="mt-2">{action}</div> : null}
    </div>
  );
}
