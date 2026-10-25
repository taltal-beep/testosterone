"""One test across a cycle's recent runs: its outcomes, durations and last failure.

Feeds the per-test page and test search (``GET /api/v1/cycles/{cycle}/tests``
and ``.../test-history``), and the cycle page's "Slowest tests" and "Got slower"
lists. Like :mod:`~testo_core.services.flaky_service`, per-test data comes from
each run's own Allure ``*-result.json`` snapshot, so it needs no schema change.
"""

from __future__ import annotations

from dataclasses import dataclass
from statistics import median
from typing import Any

from testo_core.history.views import CompletedRunView
from testo_core.services import flaky_service
from testo_core.services.delta_service import within_noise

DEFAULT_WINDOW = 20
# "Got slower" compares the median of the last RECENT_RUNS durations with the median before.
RECENT_RUNS = 3
# A single test's noise floor: below this a change is jitter, whatever its percentage.
SLOWDOWN_FLOOR_MS = 20.0

_FAIL = frozenset({"failed", "broken"})


@dataclass(frozen=True)
class TestPoint:
    """The test in one run."""

    __test__ = False  # not a pytest test class

    run_id: str
    created_at: float
    status: str
    duration_ms: int | None
    message: str
    branch: str | None


@dataclass(frozen=True)
class TestSummary:
    """One line of the cycle's test list."""

    __test__ = False  # not a pytest test class

    key: str
    name: str
    full_name: str
    group: str
    stage: str
    runs: int
    passed: int
    failed: int
    last_status: str
    flaky: bool
    last_duration_ms: int | None
    median_duration_ms: int | None
    # Recent median minus the median before; set only when that is more than noise.
    slowdown_ms: int | None
    slowdown_pct: float | None


@dataclass(frozen=True)
class CycleTests:
    cycle: str
    runs_considered: int
    tests: tuple[TestSummary, ...]


@dataclass(frozen=True)
class TestHistory:
    __test__ = False  # not a pytest test class

    cycle: str
    summary: TestSummary
    # Newest first.
    points: tuple[TestPoint, ...]

    @property
    def last_failure(self) -> TestPoint | None:
        return next((p for p in self.points if p.status in _FAIL), None)


def stable_id(key: str) -> str:
    """FNV-1a (32-bit) of ``key`` as 8 hex digits: a file name for the static demo export.

    ``frontend/src/lib/static-backend.ts`` computes the same hash to find the file.
    """
    h = 0x811C9DC5
    for byte in key.encode("utf-8"):
        h ^= byte
        h = (h * 0x01000193) & 0xFFFFFFFF
    return f"{h:08x}"


def _observations(
    cycle: str, window: int
) -> tuple[int, dict[str, list[tuple[CompletedRunView, dict[str, Any]]]]]:
    """Runs analysed, and each test's ``(run, case)`` pairs oldest first."""
    runs = flaky_service._cycle_runs(cycle)[: max(1, int(window))]
    per_test: dict[str, list[tuple[CompletedRunView, dict[str, Any]]]] = {}
    analysed = 0
    for run in reversed(runs):
        cases = flaky_service._cases_for_run(run)
        if not cases:
            continue
        analysed += 1
        for key, case in cases.items():
            per_test.setdefault(key, []).append((run, case))
    return analysed, per_test


def _slowdown(durations: list[int]) -> tuple[int | None, float | None]:
    """Change of the recent median over the earlier one, when it is more than noise."""
    if len(durations) < RECENT_RUNS + 2:
        return None, None
    before = median(durations[:-RECENT_RUNS])
    recent = median(durations[-RECENT_RUNS:])
    delta = recent - before
    if delta <= 0 or within_noise(
        absolute_delta=delta, baseline=before, floor_ms=SLOWDOWN_FLOOR_MS
    ):
        return None, None
    return int(delta), (round(100.0 * delta / before, 1) if before else None)


def _summarise(key: str, observed: list[tuple[CompletedRunView, dict[str, Any]]]) -> TestSummary:
    cases = [case for _, case in observed]
    latest = cases[-1]
    statuses = [str(c["status"]) for c in cases]
    durations = [int(c["duration_ms"]) for c in cases if isinstance(c.get("duration_ms"), int)]
    slowdown_ms, slowdown_pct = _slowdown(durations)
    return TestSummary(
        key=key,
        name=str(latest.get("name") or key),
        full_name=str(latest.get("full_name") or ""),
        group=str(latest.get("group") or "(ungrouped)"),
        stage=str(latest.get("stage") or ""),
        runs=len(cases),
        passed=statuses.count("passed"),
        failed=sum(1 for s in statuses if s in _FAIL),
        last_status=statuses[-1],
        flaky=flaky_service.classify(key, cases) is not None,
        last_duration_ms=latest.get("duration_ms")
        if isinstance(latest.get("duration_ms"), int)
        else None,
        median_duration_ms=int(median(durations)) if durations else None,
        slowdown_ms=slowdown_ms,
        slowdown_pct=slowdown_pct,
    )


def _matches(summary: TestSummary, query: str) -> bool:
    needle = query.casefold()
    return any(
        needle in field.casefold() for field in (summary.name, summary.full_name, summary.group)
    )


def list_cycle_tests(
    cycle: str, *, window: int = DEFAULT_WINDOW, query: str | None = None
) -> CycleTests:
    """Every test seen in ``cycle``'s last ``window`` runs, failing first, then by name."""
    analysed, per_test = _observations(cycle, window)
    tests = [_summarise(key, observed) for key, observed in per_test.items()]
    if query and query.strip():
        tests = [t for t in tests if _matches(t, query.strip())]
    tests.sort(key=lambda t: (t.last_status not in _FAIL, not t.flaky, t.name, t.key))
    return CycleTests(cycle=cycle, runs_considered=analysed, tests=tuple(tests))


def load_test_history(cycle: str, key: str, *, window: int = DEFAULT_WINDOW) -> TestHistory | None:
    """``key``'s outcome in each of ``cycle``'s last ``window`` runs; ``None`` if it never ran."""
    _, per_test = _observations(cycle, window)
    observed = per_test.get(key)
    if not observed:
        return None
    points = tuple(
        TestPoint(
            run_id=run.run_id,
            created_at=run.created_at,
            status=str(case["status"]),
            duration_ms=case.get("duration_ms")
            if isinstance(case.get("duration_ms"), int)
            else None,
            message=str(case.get("message") or ""),
            branch=run.branch,
        )
        for run, case in reversed(observed)
    )
    return TestHistory(cycle=cycle, summary=_summarise(key, observed), points=points)
