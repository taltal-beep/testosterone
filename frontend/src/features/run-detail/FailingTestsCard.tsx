import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { apiClient, type FailingTestItem } from "../../lib/api-client";
import { Badge, Button, Card } from "../../components/ui";
import { countLabel, formatDuration, shortRunId, testPath } from "../../lib/format";

// Enough to read at a glance; the rest are one click away.
const INITIAL_ROWS = 15;

function Streak({ test, baselineBranch }: { test: FailingTestItem; baselineBranch?: string | null }) {
  if (test.new) {
    return (
      <Badge tone="danger" title={baselineBranch ? `Not failing on ${baselineBranch}` : undefined}>
        New
      </Badge>
    );
  }
  // Failing on the baseline too, though this branch only just ran it.
  if (test.failing_runs <= 1) {
    return <Badge tone="warn">{baselineBranch ? `Also failing on ${baselineBranch}` : "Failing before"}</Badge>;
  }
  return (
    <Badge tone="warn" title={`Failing since run ${shortRunId(test.failing_since_run_id)}`}>
      Failing for {test.failing_runs} runs
    </Badge>
  );
}

function FailingTestRow({
  test,
  cycle,
  baselineBranch
}: {
  test: FailingTestItem;
  cycle?: string | null;
  baselineBranch?: string | null;
}) {
  return (
    <li className="space-y-1 py-3 first:pt-0 last:pb-0">
      <div className="flex flex-wrap items-center gap-2">
        {cycle ? (
          <Link to={testPath(cycle, test.key)} className="break-all font-medium text-brand-300 hover:underline">
            {test.name}
          </Link>
        ) : (
          <span className="break-all font-medium text-ink-50">{test.name}</span>
        )}
        <Streak test={test} baselineBranch={baselineBranch} />
        {test.flaky ? <Badge tone="brand">Flaky</Badge> : null}
        {test.status === "broken" ? <Badge>Broken</Badge> : null}
      </div>
      {test.message ? (
        <p className="break-words font-mono text-xs text-danger-300" title={test.message}>
          {test.message}
        </p>
      ) : null}
      <p className="text-xs text-ink-400">
        {[test.stage, test.group, test.duration_ms != null ? formatDuration(test.duration_ms) : null]
          .filter(Boolean)
          .join(" · ")}
      </p>
    </li>
  );
}

/** The commands that rerun just these tests, one per runner, with a copy button. */
function RerunCommands({ commands }: { commands: string[] }) {
  const [copied, setCopied] = useState(false);
  const text = commands.join("\n");
  async function copy() {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
    } catch {
      // No clipboard (plain http, or denied): the command is still there to select.
      setCopied(false);
    }
  }
  return (
    <div className="mb-4 rounded-xl border border-white/10 bg-ink-900/60 p-3" data-testid="rerun-commands">
      <div className="mb-2 flex items-center justify-between gap-2">
        <p className="text-xs font-semibold uppercase tracking-wide text-ink-400">Rerun these tests</p>
        <Button variant="secondary" size="sm" onClick={copy} aria-label="Copy rerun command">
          {copied ? "Copied" : "Copy"}
        </Button>
      </div>
      <pre className="overflow-x-auto whitespace-pre-wrap break-all font-mono text-xs text-ink-100">{text}</pre>
    </div>
  );
}

/**
 * The first thing on a failed run's page: which tests failed, with their
 * message, whether they broke in this run or have been failing for a while,
 * and which ones are flaky. Failures that share a message are summarised on
 * top, so one root cause reads as one line.
 */
export function FailingTestsCard({ runId, cycle }: { runId: string; cycle?: string | null }) {
  const [showAll, setShowAll] = useState(false);
  const query = useQuery({
    queryKey: ["run-failures", runId],
    queryFn: () => apiClient.getRunFailures(runId)
  });

  if (query.isLoading) {
    return (
      <Card title="Failing tests">
        <p className="text-sm text-ink-300">Loading failing tests…</p>
      </Card>
    );
  }
  if (query.isError || !query.data) {
    return (
      <Card title="Failing tests">
        <p className="text-sm text-ink-400">
          Couldn't load the failing tests for this run. The stage results below still show which stage failed.
        </p>
      </Card>
    );
  }

  const {
    tests,
    groups,
    new_failures: newFailures,
    runs_considered: runsConsidered,
    baseline_run_id: baselineRunId,
    baseline_branch: baselineBranch,
    rerun_commands: rerunCommands = []
  } = query.data;
  if (tests.length === 0) {
    return (
      <Card title="Failing tests">
        <p className="text-sm text-ink-400">
          No individual test failed. A stage failed before or outside its tests: check its log in the stage results and
          reports below.
        </p>
      </Card>
    );
  }

  const visible = showAll ? tests : tests.slice(0, INITIAL_ROWS);
  const longStanding = tests.length - newFailures;

  return (
    <Card title="Failing tests" data-testid="failing-tests">
      <p className="mb-3 text-sm text-ink-200">
        {countLabel(tests.length, "test")} failed
        {newFailures > 0 ? <>, {newFailures} new {baselineBranch ? `since ${baselineBranch}` : "in this run"}</> : null}
        {longStanding > 0 && (baselineRunId || runsConsidered > 1) ? (
          <>, {longStanding} already failing {baselineBranch ? `on ${baselineBranch}` : "before"}</>
        ) : null}
        .
      </p>

      {rerunCommands.length > 0 ? <RerunCommands commands={rerunCommands} /> : null}

      {groups.length > 0 ? (
        <div className="mb-4 rounded-xl border border-white/10 bg-ink-900/60 p-3">
          <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-ink-400">Same cause</p>
          <ul className="space-y-1">
            {groups.map((group) => (
              <li key={group.message} className="flex gap-2 text-sm">
                <span className="shrink-0 font-semibold text-ink-100">{countLabel(group.count, "test")}:</span>
                <span className="break-words font-mono text-xs leading-5 text-danger-300">{group.message}</span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      <ul className="divide-y divide-white/5">
        {visible.map((test) => (
          <FailingTestRow key={test.key} test={test} cycle={cycle} baselineBranch={baselineBranch} />
        ))}
      </ul>

      <div className="mt-3 flex flex-wrap items-center gap-3">
        {tests.length > INITIAL_ROWS ? (
          <Button variant="secondary" size="sm" onClick={() => setShowAll((value) => !value)}>
            {showAll ? "Show fewer" : `Show all ${tests.length}`}
          </Button>
        ) : null}
        {cycle && tests.some((test) => test.flaky) ? (
          <Link to={`/cycles/${encodeURIComponent(cycle)}`} className="text-sm text-brand-300 hover:underline">
            See this cycle's flaky tests
          </Link>
        ) : null}
      </div>
    </Card>
  );
}
