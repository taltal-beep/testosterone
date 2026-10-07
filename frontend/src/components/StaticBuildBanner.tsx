import { useEffect, useState } from "react";

import { IS_STATIC_BUILD, loadManifest, type StaticManifest } from "../lib/static-backend";

/**
 * Tells visitors of the published demo what they are looking at: a snapshot of
 * one pipeline run, what its two cycles are (and that fake-api's failures are
 * deliberate), with a link back to the pipeline that produced it. Renders
 * nothing in the normal build that talks to the API.
 */
export function StaticBuildBanner() {
  const [manifest, setManifest] = useState<StaticManifest | null>(null);

  useEffect(() => {
    if (!IS_STATIC_BUILD) return;
    let active = true;
    loadManifest().then((m) => {
      if (active) setManifest(m);
    });
    return () => {
      active = false;
    };
  }, []);

  if (!IS_STATIC_BUILD) return null;

  const generated = manifest ? new Date(manifest.generated_at * 1000).toUTCString() : null;
  const commit = manifest?.commit ? manifest.commit.slice(0, 8) : null;

  return (
    <div className="border-b border-warn-400/30 bg-warn-400/10 px-4 py-2 text-xs text-ink-200 sm:px-6" role="status">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-3 gap-y-1">
        <span className="font-semibold uppercase tracking-wider text-warn-400">Read-only demo</span>
        <span>
          Real results from <code className="font-mono">testo run</code> in CI: Testosterone testing itself (
          <code className="font-mono">self-test</code>) and{" "}
          <a
            href="https://github.com/taltal-beep/fake-api"
            target="_blank"
            rel="noreferrer"
            className="text-brand-300 hover:text-brand-400 hover:underline"
          >
            fake-api
          </a>
          , an app whose flaky, broken and slow routes fail on purpose, so red there is expected. Starting runs and
          saving settings are disabled.
        </span>
        {generated ? <span className="text-ink-400">Exported {generated}</span> : null}
        {commit ? (
          <span className="text-ink-400">
            Commit <code className="font-mono">{commit}</code>
            {manifest?.commit_ref ? ` (${manifest.commit_ref})` : ""}
          </span>
        ) : null}
        {manifest?.pipeline_url ? (
          <a
            href={manifest.pipeline_url}
            target="_blank"
            rel="noreferrer"
            className="text-brand-300 hover:text-brand-400 hover:underline"
          >
            View the pipeline
          </a>
        ) : null}
      </div>
    </div>
  );
}
