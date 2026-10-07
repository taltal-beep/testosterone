import { Link } from "react-router-dom";

import { formatRunLabel, shortRunId, type RunLike } from "../../lib/format";

export interface RunLabelProps {
  run: RunLike;
  /** Link the label to the run's detail page (or to `href` when given). */
  linked?: boolean;
  href?: string;
  className?: string;
}

/** Cycle + start time as the primary label, short run id as secondary text (full id on hover). */
export function RunLabel({ run, linked = false, href, className }: RunLabelProps) {
  const label = formatRunLabel(run);
  return (
    <span className={`inline-flex min-w-0 flex-wrap items-baseline gap-x-2 ${className ?? ""}`}>
      {linked ? (
        <Link to={href ?? `/runs/${run.run_id}`} className="font-medium text-brand-300 hover:text-brand-400 hover:underline">
          {label}
        </Link>
      ) : (
        <span className="font-medium text-ink-100">{label}</span>
      )}
      <span className="font-mono text-xs text-ink-500" title={run.run_id}>
        {shortRunId(run.run_id)}
      </span>
    </span>
  );
}
