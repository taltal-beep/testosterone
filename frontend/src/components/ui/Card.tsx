import type { HTMLAttributes, ReactNode } from "react";

export interface CardProps extends Omit<HTMLAttributes<HTMLDivElement>, "title"> {
  title?: ReactNode;
  actions?: ReactNode;
}

export function Card({ title, actions, className, children, ...props }: CardProps) {
  return (
    <div
      className={`rounded-xl border border-ink-700 bg-ink-900 p-4 ${className ?? ""}`}
      {...props}
    >
      {(title || actions) && (
        <div className="mb-3 flex items-center justify-between gap-2">
          {title ? <h3 className="text-sm font-semibold text-ink-100">{title}</h3> : <span />}
          {actions}
        </div>
      )}
      {children}
    </div>
  );
}
