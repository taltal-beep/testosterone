"""Flaky test detection over a cycle's run history.

A test is flaky when, across the last ``window`` runs of a cycle, it both
passed and failed and its outcome flipped at least twice. One flip is a plain
regression or fix, which Compare already shows; flipping back and forth is the
signal that the test, not the code, is unreliable.

Per-test outcomes come from the ``test_result`` rows each run stores
(:mod:`testo_core.history.cases`; older runs are read from their artifact
snapshot once and stored), so this works on every database backend. The CLI (``testo flaky``) and the API (``/analytics/flaky``) both call
:func:`find_flaky_tests`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from testo_core.history.cases import cases_for_run
from testo_core.history.read_model import list_cycle_runs
from testo_core.history.views import CompletedRunView

DEFAULT_WINDOW = 20
MIN_FLIPS = 2
# How many recent runs (any cycle) to scan when looking for one cycle's window.

_PASS = "passed"
_FAIL = frozenset({"failed", "broken"})


@dataclass(frozen=True)
class FlakyTest:
    key: str
    name: str
    group: str
    runs: int
    passed: int
    failed: int
    flips: int
    flip_rate: float
    last_status: str
    # Oldest first, one of "passed" / "failed" / "broken" / "skipped" / "unknown"
    # per run the test appeared in.
    history: tuple[str, ...]
    full_name: str = ""
    # Matches a ``quarantine:`` rule of the cycle (set by callers that load the config).
    quarantined: bool = False


@dataclass(frozen=True)
class FlakyReport:
    cycle: str
    window: int
    runs_analyzed: int
    tests_analyzed: int
    flaky: tuple[FlakyTest, ...]


def _outcomes(statuses: list[str]) -> list[str]:
    """Pass/fail outcomes only; skipped and unknown runs neither pass nor fail."""
    return ["fail" if s in _FAIL else "pass" for s in statuses if s == _PASS or s in _FAIL]


def classify(key: str, observations: list[dict[str, Any]]) -> FlakyTest | None:
    """Score one test from its per-run observations (oldest first); ``None`` if not flaky."""
    statuses = [str(o["status"]) for o in observations]
    outcomes = _outcomes(statuses)
    passed = outcomes.count("pass")
    failed = outcomes.count("fail")
    flips = sum(1 for a, b in zip(outcomes, outcomes[1:], strict=False) if a != b)
    if passed == 0 or failed == 0 or flips < MIN_FLIPS:
        return None
    latest = observations[-1]
    return FlakyTest(
        key=key[:80],
        name=str(latest.get("name") or key)[:120],
        group=str(latest.get("group") or "(ungrouped)")[:100],
        runs=len(outcomes),
        passed=passed,
        failed=failed,
        flips=flips,
        flip_rate=round(flips / (len(outcomes) - 1), 3),
        last_status=statuses[-1],
        history=tuple(statuses),
        full_name=str(latest.get("full_name") or ""),
    )


def _cases_for_run(run: CompletedRunView) -> dict[str, dict[str, Any]]:
    return cases_for_run(run)


def _cycle_runs(cycle: str, *, limit: int | None = None) -> list[CompletedRunView]:
    """``cycle``'s recorded runs, newest first (at most ``limit``)."""
    return list_cycle_runs(cycle) if limit is None else list_cycle_runs(cycle, limit=limit)


def _report(cycle: str, runs: list[CompletedRunView], window: int) -> FlakyReport:
    """Score the tests in ``runs`` (newest first, already cut to the window)."""
    per_test: dict[str, list[dict[str, Any]]] = {}
    analyzed = 0
    for run in reversed(runs):  # oldest first, so flips are counted in order
        cases = _cases_for_run(run)
        if not cases:
            continue
        analyzed += 1
        for key, case in cases.items():
            per_test.setdefault(key, []).append(case)

    flaky = [t for key, obs in per_test.items() if (t := classify(key, obs)) is not None]
    flaky.sort(key=lambda t: (-t.flip_rate, -t.flips, t.name))
    return FlakyReport(
        cycle=cycle,
        window=window,
        runs_analyzed=analyzed,
        tests_analyzed=len(per_test),
        flaky=tuple(flaky),
    )


def find_flaky_tests(*, cycle: str, window: int = DEFAULT_WINDOW) -> FlakyReport:
    """Flaky tests across the last ``window`` runs of ``cycle``, most flips first."""
    window = max(2, int(window))
    return _report(cycle, _cycle_runs(cycle, limit=window), window)


def newly_flaky_tests(
    *, cycle: str, run_id: str | None = None, window: int = DEFAULT_WINDOW
) -> tuple[FlakyTest, ...]:
    """Tests that ``run_id`` (default: the cycle's latest run) made flaky.

    Flaky in the ``window`` runs ending at that run, and not in the ``window``
    runs ending at the run before it. Alerts and ``testo flaky --new`` use this
    so a test is announced once, when it starts flipping, not on every run.
    """
    window = max(2, int(window))
    runs = _cycle_runs(cycle)
    start = next((i for i, r in enumerate(runs) if r.run_id == run_id), None) if run_id else 0
    if start is None:
        return ()
    now = _report(cycle, runs[start : start + window], window).flaky
    if not now:
        return ()
    before = {t.key for t in _report(cycle, runs[start + 1 : start + 1 + window], window).flaky}
    return tuple(t for t in now if t.key not in before)
