import type { ReactNode } from "react";

import { usePageTitle } from "../../lib/usePageTitle";

export interface PageHeaderProps {
  title: ReactNode;
  subtitle?: ReactNode;
  actions?: ReactNode;
  /** The browser tab's title, when `title` isn't plain text. */
  documentTitle?: string;
}

export function PageHeader({ title, subtitle, actions, documentTitle }: PageHeaderProps) {
  usePageTitle(documentTitle ?? (typeof title === "string" ? title : undefined));
  return (
    <div className="mb-6 flex flex-wrap items-start justify-between gap-3">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-white">{title}</h1>
        {subtitle ? <p className="mt-1 text-sm text-ink-300">{subtitle}</p> : null}
      </div>
      {actions ? <div className="flex items-center gap-2">{actions}</div> : null}
    </div>
  );
}
