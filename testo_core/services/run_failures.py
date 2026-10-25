"""The failing tests of one run, for the run page: what failed, since when, and why.

Per-test outcomes come from each run's artifact snapshot (the Allure
``*-result.json`` files), the same source Compare and flaky detection read, so
this needs no schema change and works for engine and ingested runs alike.

For each failing test it reports how many runs in a row it has been failing
(``failing_runs``; 1 means it broke in this run), whether it is flaky in the
cycle's recent history, and the first line of its failure message. Tests that
fail with the same message are grouped, so ten tests that all hit
``ConnectionRefusedError`` read as one cause, not ten.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from testo_core import paths
from testo_core.history.read_model import get_run, list_recent_runs
from testo_core.history.views import CompletedRunView
from testo_core.services import flaky_service
from testo_core.services.report_archive_diff import _load_cases

# Runs of the cycle (this one included) looked at for "failing since" and flakiness.
DEFAULT_WINDOW = flaky_service.DEFAULT_WINDOW
_SCAN_LIMIT = 500
_FAILED = frozenset({"failed", "broken"})
# Numbers, hex ids and quoted values vary between otherwise identical failures.
_VOLATILE = re.compile(r"0x[0-9a-fA-F]+|\d+(?:\.\d+)?|'[^']*'|\"[^\"]*\"")


@dataclass(frozen=True)
class FailingTest:
    key: str
    name: str
    full_name: str
    group: str
    stage: str
    status: str
    message: str
    duration_ms: int | None
    # Consecutive runs of the cycle, ending with this one, in which the test failed.
    failing_runs: int
    # The oldest run of that streak (this run when ``failing_runs`` is 1).
    failing_since_run_id: str
    flaky: bool


@dataclass(frozen=True)
class FailureGroup:
    message: str
    count: int
    keys: tuple[str, ...]


@dataclass(frozen=True)
class RunFailures:
    run_id: str
    runs_considered: int
    tests: tuple[FailingTest, ...]
    # Messages shared by two or more failing tests, largest group first.
    groups: tuple[FailureGroup, ...]

    @property
    def new_failures(self) -> int:
        return sum(1 for t in self.tests if t.failing_runs == 1)


def message_signature(message: str) -> str:
    """``message`` with the parts that vary between runs (numbers, ids, quoted values) blanked."""
    return _VOLATILE.sub("…", message).strip().lower()


def _cases(run: CompletedRunView) -> dict[str, dict[str, Any]]:
    if not run.snapshot_dir:
        return {}
    return _load_cases(paths.ORCHESTRATOR_ROOT / run.snapshot_dir)


def _earlier_runs(run: CompletedRunView, window: int) -> list[CompletedRunView]:
    """Up to ``window - 1`` runs of ``run``'s cycle before it, newest first."""
    if not run.cycle:
        return []
    earlier = [
        r
        for r in list_recent_runs(limit=_SCAN_LIMIT)
        if r.cycle == run.cycle and r.created_at < run.created_at and r.run_id != run.run_id
    ]
    return earlier[: max(0, window - 1)]


def _groups(tests: list[FailingTest]) -> tuple[FailureGroup, ...]:
    by_sig: dict[str, list[FailingTest]] = {}
    for test in tests:
        if test.message:
            by_sig.setdefault(message_signature(test.message), []).append(test)
    groups = [
        FailureGroup(
            message=members[0].message, count=len(members), keys=tuple(t.key for t in members)
        )
        for members in by_sig.values()
        if len(members) > 1
    ]
    groups.sort(key=lambda g: (-g.count, g.message))
    return tuple(groups)


def load_run_failures(run_id: str, *, window: int = DEFAULT_WINDOW) -> RunFailures | None:
    """``run_id``'s failing tests, newest breakages first; ``None`` if the run doesn't exist."""
    run = get_run(run_id=run_id)
    if run is None:
        return None
    window = max(2, int(window))
    current = _cases(run)
    failing = {k: c for k, c in current.items() if c["status"] in _FAILED}
    if not failing:
        return RunFailures(run_id=run.run_id, runs_considered=1, tests=(), groups=())

    earlier = _earlier_runs(run, window)
    earlier_cases = [(r, _cases(r)) for r in earlier]
    earlier_cases = [(r, c) for r, c in earlier_cases if c]

    # Flaky over the same window, ending at this run (oldest first for flaky_service).
    observations: dict[str, list[dict[str, Any]]] = {}
    for _, cases in reversed(earlier_cases):
        for key in failing:
            if key in cases:
                observations.setdefault(key, []).append(cases[key])
    for key, case in failing.items():
        observations.setdefault(key, []).append(case)

    tests: list[FailingTest] = []
    for key, case in failing.items():
        streak, since = 1, run.run_id
        for older, cases in earlier_cases:
            prev = cases.get(key)
            if prev is None or prev["status"] not in _FAILED:
                break
            streak, since = streak + 1, older.run_id
        tests.append(
            FailingTest(
                key=key[:200],
                name=str(case["name"]),
                full_name=str(case.get("full_name") or ""),
                group=str(case.get("group") or ""),
                stage=str(case.get("stage") or ""),
                status=str(case["status"]),
                message=str(case.get("message") or ""),
                duration_ms=case.get("duration_ms"),
                failing_runs=streak,
                failing_since_run_id=since,
                flaky=flaky_service.classify(key, observations.get(key, [])) is not None,
            )
        )
    # New breakages first, then the longest-standing ones; ties by stage and name.
    tests.sort(key=lambda t: (t.failing_runs != 1, -t.failing_runs, t.stage, t.name))
    return RunFailures(
        run_id=run.run_id,
        runs_considered=1 + len(earlier_cases),
        tests=tuple(tests),
        groups=_groups(tests),
    )
