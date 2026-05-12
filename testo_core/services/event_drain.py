"""
Service: normalize queued worker output (log lines vs terminal run records).

Presentation code should iterate drained items and update UI state; this module stays
free of Streamlit imports for testability.
"""

from __future__ import annotations

import queue
import time
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any, TypeGuard

from testo_core.runners import LogEvent, RunResult

# region agent log
_UQO_DEBUG_LOG_PATH = "/Users/taltal/unified-quality-orchestration-reporting-dashboard/.cursor/debug-075c10.log"
_UQO_DEBUG_SESSION_ID = "075c10"
_UQO_DEBUG_DRAIN_SEEN = 0


def _uqo_debug_log(*, hypothesis_id: str, location: str, message: str, data: dict[str, Any] | None = None) -> None:
    # NDJSON append; best-effort only.
    try:
        payload = {
            "sessionId": _UQO_DEBUG_SESSION_ID,
            "runId": "pre-fix",
            "hypothesisId": str(hypothesis_id),
            "location": str(location),
            "message": str(message),
            "data": data or {},
            "timestamp": int(time.time() * 1000),
        }
        with open(_UQO_DEBUG_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(__import__("json").dumps(payload, ensure_ascii=True) + "\n")
    except Exception:
        return


# endregion agent log


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

        # region agent log
        global _UQO_DEBUG_DRAIN_SEEN
        if _UQO_DEBUG_DRAIN_SEEN < 25:
            _UQO_DEBUG_DRAIN_SEEN += 1
            _uqo_debug_log(
                hypothesis_id="H1",
                location="testo_core/services/event_drain.py:iter_drained_queue_items",
                message="drain item",
                data={
                    "seen": int(_UQO_DEBUG_DRAIN_SEEN),
                    "type": str(type(item)),
                    "type_module": str(getattr(type(item), "__module__", "")),
                    "type_qualname": str(getattr(type(item), "__qualname__", "")),
                    "isinstance_RunResult": bool(isinstance(item, RunResult)),
                    "isinstance_LogEvent": bool(isinstance(item, LogEvent)),
                    "has_returncode": bool(hasattr(item, "returncode")),
                    "has_command": bool(hasattr(item, "command")),
                    "has_stream_line": bool(hasattr(item, "stream") and hasattr(item, "line")),
                },
            )
        # endregion agent log

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

        # region agent log
        # If this looks like a RunResult but failed isinstance, that's a likely module-reload mismatch.
        if hasattr(item, "returncode") and hasattr(item, "command"):
            _uqo_debug_log(
                hypothesis_id="H1",
                location="testo_core/services/event_drain.py:iter_drained_queue_items",
                message="skipped runresult-like item (isinstance failed)",
                data={
                    "type": str(type(item)),
                    "type_module": str(getattr(type(item), "__module__", "")),
                    "type_qualname": str(getattr(type(item), "__qualname__", "")),
                },
            )
        else:
            _uqo_debug_log(
                hypothesis_id="H2",
                location="testo_core/services/event_drain.py:iter_drained_queue_items",
                message="skipped unknown item",
                data={"type": str(type(item))},
            )
        # endregion agent log
