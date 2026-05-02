"""
Service: normalize queued worker output (log lines vs terminal run records).

Presentation code should iterate drained items and update UI state; this module stays
free of Streamlit imports for testability.
"""

from __future__ import annotations

import queue
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any, TypeGuard

from uqo_core.runners import LogEvent, RunResult


@dataclass(frozen=True)
class RunLogLine:
    """One stdout/stderr/meta line emitted by the runner worker."""

    stream: str
    line: str


def next_multi_run_remaining(remaining_before: int | None) -> int:
    """Return the child-run count after applying one multi-run RunResult."""
    return max(0, int(remaining_before or 0) - 1)


def apply_completed_multi_run(*, remaining_before: int | None) -> tuple[int, bool]:
    """
    Return ``(remaining_after, batch_complete)`` after one child run completes.

    Multi-run workers enqueue each child run's normal done marker and RunResult. The UI
    should stay locked until the final child RunResult has been applied.
    """
    remaining = next_multi_run_remaining(remaining_before)
    return remaining, remaining == 0


def _is_log_like(item: Any) -> TypeGuard[Any]:
    return hasattr(item, "stream") and hasattr(item, "line")


def iter_drained_queue_items(q: queue.Queue[Any]) -> Iterator[RunResult | RunLogLine]:
    """
    Drain ``q`` non-blocking and yield each item as either a terminal :class:`RunResult`
    or a :class:`RunLogLine`.

    Unknown queue payloads are skipped (defensive against mixed producer versions).
    """
    while True:
        try:
            item = q.get_nowait()
        except queue.Empty:
            break

        if isinstance(item, RunResult):
            yield item
            continue

        if isinstance(item, LogEvent):
            yield RunLogLine(stream=item.stream, line=item.line)
            continue

        if _is_log_like(item):
            try:
                stream = str(getattr(item, "stream", "meta"))
                line = str(getattr(item, "line", ""))
            except Exception:
                continue
            yield RunLogLine(stream=stream, line=line)
