"""A run as GitHub-flavored Markdown: a job summary or a pull request comment.

``testo report markdown`` prints it; the GitHub Action writes it to the job
summary and, when asked, keeps one comment per cycle on the pull request up to
date (the first line is a hidden marker it finds that comment by).

Everything comes from stored run records and their artifact snapshots, so the
same text can be rebuilt for any past run.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from testo_core import paths
from testo_core.history.read_model import get_run, list_cycle_runs, list_recent_runs
from testo_core.history.views import CompletedRunView
from testo_core.services.report_archive_diff import CaseChange, _load_cases, diff_case_maps

MAX_ROWS = 20
_FAILED = frozenset({"failed", "broken"})
_CHANGE_ORDER = {"regression": 0, "added": 1, "fix": 2, "removed": 3, "status_change": 4}
_CHANGE_TALLY = {
    "regression": ("regression", "regressions"),
    "fix": ("fixed", "fixed"),
    "added": ("new test", "new tests"),
    "removed": ("removed", "removed"),
    "status_change": ("changed", "changed"),
}
_CHANGE_LABEL = {
    "regression": "🔴 regression",
    "fix": "🟢 fixed",
    "added": "🆕 new",
    "removed": "➖ removed",
    "status_change": "🔁 changed",
}


def comment_marker(cycle: str | None) -> str:
    """Hidden first line that identifies this cycle's comment on a pull request."""
    # "--" and ">" would end the HTML comment early; plain cycle names are unchanged.
    safe = re.sub(r"-{2,}|>", "_", cycle or "-")
    return f"<!-- testo-summary:{safe} -->"


@dataclass(frozen=True)
class RunSummary:
    run: CompletedRunView
    previous: CompletedRunView | None
    failing: tuple[str, ...]
    changes: tuple[CaseChange, ...]
    # The branch ``previous`` was taken from; ``None`` means simply the run before.
    baseline_branch: str | None = None
    # False when ``previous`` has no stored test results (it crashed, or its
    # snapshot was pruned): then "no test changed" would be a guess.
    compared: bool = True

    @property
    def baseline_label(self) -> str:
        if self.baseline_branch:
            return f"the last run on {_code(self.baseline_branch)}"
        return "the previous run"


def _cases(run: CompletedRunView | None) -> dict[str, dict[str, Any]]:
    if run is None or not run.snapshot_dir:
        return {}
    return _load_cases(paths.ORCHESTRATOR_ROOT / run.snapshot_dir)


def _cycle_runs(cycle: str, *, before_run_id: str | None = None) -> list[CompletedRunView]:
    return list_cycle_runs(cycle, before_run_id=before_run_id)


def pick_baseline(
    run: CompletedRunView, older: list[CompletedRunView], branch: str | None
) -> tuple[CompletedRunView | None, str | None]:
    """The run to compare ``run`` with, newest first in ``older``, and the branch it came from.

    A pull request is judged against its target branch (``branch``, else the
    run's recorded ``base_branch``), so a parallel PR's run never becomes the
    baseline. Without a target, or with no run on it yet, it is the previous
    run on the run's own branch (any previous run when the run has no branch
    recorded): a push to ``main`` is never compared with a feature branch's run.
    """
    target = branch or run.base_branch
    if target and target != run.branch:
        on_target = next((r for r in older if r.branch == target), None)
        if on_target is not None:
            return on_target, target
    if run.branch:
        return next((r for r in older if r.branch == run.branch), None), None
    return (older[0] if older else None), None


def load_run_summary(
    *,
    cycle: str | None = None,
    run_id: str | None = None,
    baseline_branch: str | None = None,
) -> RunSummary | None:
    """The given run (or ``cycle``'s latest) with its failures and changes since its baseline."""
    if run_id:
        run = get_run(run_id=run_id)
        if run is None:
            return None
        older = _cycle_runs(run.cycle, before_run_id=run.run_id) if run.cycle else []
    elif cycle:
        runs = _cycle_runs(cycle)
        if not runs:
            return None
        run, older = runs[0], runs[1:]
    else:
        recent = list_recent_runs(limit=1)
        if not recent:
            return None
        return load_run_summary(run_id=recent[0].run_id, baseline_branch=baseline_branch)
    previous, from_branch = pick_baseline(run, older, baseline_branch)

    current_cases = _cases(run)
    failing = tuple(
        sorted(str(c["name"]) for c in current_cases.values() if c["status"] in _FAILED)
    )
    changes: tuple[CaseChange, ...] = ()
    compared = False
    if previous is not None:
        previous_cases = _cases(previous)
        compared = bool(previous_cases) or not current_cases
        if previous_cases and current_cases:
            changes = tuple(
                sorted(
                    diff_case_maps(previous_cases, current_cases),
                    key=lambda c: (_CHANGE_ORDER.get(c.kind, 9), c.name),
                )
            )
    return RunSummary(
        run=run,
        previous=previous,
        failing=failing,
        changes=changes,
        baseline_branch=from_branch,
        compared=compared,
    )


def _seconds(ms: float | None) -> str:
    if ms is None:
        return "—"
    return f"{ms / 1000:.1f}s"


def _count(value: Any) -> str:
    return "—" if value is None else str(value)


def _escape(text: str) -> str:
    """Plain text for a table cell: one line, ``|`` escaped, no live HTML or @mention."""
    text = " ".join(str(text).split())
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return text.replace("@", "&#64;").replace("|", "\\|")


def _code(text: str, *, in_table: bool = False) -> str:
    """``text`` as one inline code span that nothing in it can close.

    Test names come from the code under test, in a fork PR from its author: a
    backtick in one used to end the span, so ``@someone`` or ``<img>`` after it
    rendered live. The fence is one backtick longer than the longest run inside.
    """
    text = " ".join(str(text).split())
    if in_table:
        text = text.replace("|", "\\|")  # GitHub reads \| as | even inside a code span
    fence = "`" * (max((len(run) for run in re.findall(r"`+", text)), default=0) + 1)
    pad = " " if text.startswith("`") or text.endswith("`") else ""
    return f"{fence}{pad}{text}{pad}{fence}"


def render_markdown(summary: RunSummary, *, run_url: str | None = None) -> str:
    """Markdown for one run: headline, per-stage table, failing tests, changes since last run."""
    run = summary.run
    ok = run.returncode == 0
    name = run.cycle or "run"
    lines = [
        comment_marker(run.cycle),
        f"### {'✅' if ok else '❌'} Testosterone: {_code(name)} {'passed' if ok else 'failed'}",
        "",
    ]

    headline = f"Ran in {_seconds(run.wall_duration_ms)}"
    if run.total_tests is not None:
        failed = (run.failed or 0) + (run.broken or 0)
        headline = (
            f"**{run.passed or 0} passed · {failed} failed · {run.skipped or 0} skipped** "
            f"in {_seconds(run.wall_duration_ms)}"
        )
    if run.health_pct is not None:
        headline += f" · pass rate {run.health_pct:.1f}%"
    lines += [headline, ""]

    if run.stage_health:
        lines += [
            "| Stage | Runner | Result | Tests | Passed | Failed | Skipped | Time |",
            "|---|---|---|---:|---:|---:|---:|---:|",
        ]
        for s in run.stage_health:
            failed = (s.get("failed") or 0) + (s.get("broken") or 0)
            result = "✅ pass" if s.get("returncode") == 0 else "❌ fail"
            if s.get("quarantined"):
                result += f" · {len(s['quarantined'])} quarantined"
            duration = s.get("duration_s")
            lines.append(
                f"| {_escape(str(s.get('name', '?')))} | {_escape(str(s.get('framework') or ''))} "
                f"| {result} "
                f"| {_count(s.get('total_tests'))} | {_count(s.get('passed'))} | {failed} "
                f"| {_count(s.get('skipped'))} | {_seconds(duration * 1000 if duration is not None else None)} |"
            )
        lines.append("")

    if summary.failing:
        lines.append(f"<details{' open' if len(summary.failing) <= 5 else ''}>")
        lines.append(f"<summary><b>Failing tests ({len(summary.failing)})</b></summary>")
        lines.append("")
        quarantined = {str(n) for s in run.stage_health for n in (s.get("quarantined") or []) if n}
        lines += [
            f"- {_code(n)}" + (" _(quarantined)_" if n in quarantined else "")
            for n in summary.failing[:MAX_ROWS]
        ]
        if len(summary.failing) > MAX_ROWS:
            lines.append(f"- … and {len(summary.failing) - MAX_ROWS} more")
        lines += ["", "</details>", ""]

    if summary.previous is None:
        lines.append("_First recorded run of this cycle, so there is nothing to compare with yet._")
    elif not summary.changes and not summary.compared:
        lines.append(
            f"_No test results are stored for {summary.baseline_label}, so there is nothing to"
            " compare with._"
        )
    elif not summary.changes:
        lines.append(f"No test changed outcome since {summary.baseline_label}.")
    else:
        kinds: list[str] = [c.kind for c in summary.changes]
        tally = ", ".join(
            f"{n} {_CHANGE_TALLY[k][0 if n == 1 else 1]}"
            for k in _CHANGE_ORDER
            if (n := kinds.count(k))
        )
        lines += [
            f"**Since {summary.baseline_label}:** {tally}",
            "",
            "| Change | Test | Before | After |",
            "|---|---|---|---|",
        ]
        for c in summary.changes[:MAX_ROWS]:
            lines.append(
                f"| {_CHANGE_LABEL.get(c.kind, c.kind)} | {_code(c.name, in_table=True)} "
                f"| {c.baseline_status or '—'} | {c.current_status or '—'} |"
            )
        if len(summary.changes) > MAX_ROWS:
            lines.append(f"| | … and {len(summary.changes) - MAX_ROWS} more | | |")
    lines.append("")

    footer = f"<sub>Run `{run.run_id}`"
    if run_url:
        footer += f" · [workflow run]({run_url})"
    footer += " · generated by [Testosterone](https://github.com/taltal-beep/testosterone)</sub>"
    lines.append(footer)
    return "\n".join(lines) + "\n"
