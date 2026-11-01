import { Link } from "react-router-dom";
import type { AiConfigStatus } from "../lib/api-client";

/**
 * Why AI features can't run yet. A provider that is found but switched off
 * (for example Claude Code, which needs no key) gets "switched off", not
 * "add a provider", so the fix the note points to is the right one.
 */
export function AiNotReadyNote({ status }: { status: AiConfigStatus }) {
  const settingsLink = (
    <Link to="/settings/ai" className="font-semibold text-brand-300 hover:underline">
      Open AI settings
    </Link>
  );
  return (
    <p className="mt-3 rounded-xl border border-warn-500/30 bg-warn-500/10 px-3 py-2 text-sm text-warn-200" data-testid="ai-not-ready">
      {status.configured && !status.enabled ? (
        <>
          AI is switched off. {settingsLink}, tick <span className="font-semibold">Enable AI failure summaries</span> and save.
        </>
      ) : (
        <>
          AI is not set up yet. {settingsLink} to add a provider (a free Gemini key works).
        </>
      )}
    </p>
  );
}
