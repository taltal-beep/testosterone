import { Link } from "react-router-dom";

import { formatProvenance, formatRelativeTime, formatRunLabel, shortRunId, type RunLike } from "../../lib/format";

export interface RunLabelProps {
  run: RunLike;
  /** Link the label to the run's detail page (or to `href` when given). */
  linked?: boolean;
  href?: string;
  /** Add "4 min ago" after the label (lists), where the absolute time alone reads the same on every row. */
  relative?: boolean;
  className?: string;
}

/**
 * Cycle + start time as the primary label, then what tells runs apart: the
 * branch and commit when the run has them, how long ago it ran when asked, and
 * the short run id as the last resort (full id on hover).
 */
export function RunLabel({ run, linked = false, href, relative = false, className }: RunLabelProps) {
  const label = formatRunLabel(run);
  const provenance = formatProvenance(run);
  return (
    <span className={`inline-flex min-w-0 flex-wrap items-baseline gap-x-2 ${className ?? ""}`}>
      {linked ? (
        <Link to={href ?? `/runs/${run.run_id}`} className="-my-1 inline-block py-1 font-medium text-brand-300 hover:text-brand-400 hover:underline">
          {label}
        </Link>
      ) : (
        <span className="font-medium text-ink-100">{label}</span>
      )}
      {provenance ? (
        <span className="font-mono text-xs text-ink-300" title={run.commit ?? undefined}>
          {provenance}
        </span>
      ) : null}
      {relative ? (
        <span className="text-xs text-ink-400" title={new Date(run.created_at * 1000).toLocaleString()}>
          {formatRelativeTime(run.created_at)}
        </span>
      ) : null}
      <span className="font-mono text-xs text-ink-500" title={run.run_id}>
        {shortRunId(run.run_id)}
      </span>
    </span>
  );
}
