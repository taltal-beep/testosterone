import type { ReactNode } from "react";

export interface KeyValueProps {
  items: Array<{ label: string; value: ReactNode }>;
  className?: string;
}

export function KeyValue({ items, className }: KeyValueProps) {
  return (
    <dl className={`grid grid-cols-[max-content_1fr] gap-x-6 gap-y-1.5 text-sm ${className ?? ""}`}>
      {items.map(({ label, value }) => (
        <div key={label} className="contents">
          <dt className="text-ink-400">{label}</dt>
          <dd className="text-ink-100">{value}</dd>
        </div>
      ))}
    </dl>
  );
}
