from __future__ import annotations

import json
import queue
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal
from uuid import uuid4

from uqo_core.command_builders import TestType
from uqo_core.runners import LogEvent, RunResult
from uqo_core.services import EngineRequest, EngineRunSpec, HeadlessEngineService

from uqo_api.models import CreateExecutionRequest


ExecutionStatus = Literal["queued", "running", "completed", "failed"]


@dataclass
class ExecutionState:
    execution_id: str
    status: ExecutionStatus = "queued"
    events_q: queue.Queue[dict[str, object]] = field(default_factory=queue.Queue)
    event_history: list[dict[str, object]] = field(default_factory=list)
    summary: dict[str, object] | None = None
    error: str | None = None
    done: bool = False
    lock: threading.Lock = field(default_factory=threading.Lock)

    def append_event(self, event: dict[str, object]) -> None:
        with self.lock:
            self.event_history.append(event)
        self.events_q.put(event)

    def set_done(self, *, status: ExecutionStatus, summary: dict[str, object] | None, error: str | None) -> None:
        with self.lock:
            self.status = status
            self.summary = summary
            self.error = error
            self.done = True


class ExecutionManager:
    def __init__(self) -> None:
        self._engine = HeadlessEngineService()
        self._states: dict[str, ExecutionState] = {}
        self._states_lock = threading.Lock()

    def create_execution(self, request_model: CreateExecutionRequest) -> ExecutionState:
        if not request_model.runs:
            raise ValueError("At least one run spec is required.")
        execution_id = str(uuid4())
        state = ExecutionState(execution_id=execution_id)
        with self._states_lock:
            self._states[execution_id] = state
        threading.Thread(
            target=self._run_execution,
            args=(state, request_model),
            daemon=True,
        ).start()
        return state

    def get(self, execution_id: str) -> ExecutionState | None:
        with self._states_lock:
            return self._states.get(execution_id)

    def read_events_since(self, execution_id: str, offset: int) -> tuple[list[dict[str, object]], int, bool]:
        state = self.get(execution_id)
        if state is None:
            raise KeyError(execution_id)
        with state.lock:
            events = state.event_history[offset:]
            next_offset = len(state.event_history)
            done = state.done
        return events, next_offset, done

    def _run_execution(self, state: ExecutionState, request_model: CreateExecutionRequest) -> None:
        state.status = "running"
        try:
            specs = tuple(self._to_engine_spec(spec) for spec in request_model.runs)
            request = EngineRequest(
                runs=specs,
                trigger_source=request_model.trigger_source,
                ci_mode=bool(request_model.ci_mode),
                persist=bool(request_model.persist),
            )
            gen = self._engine.stream(request)
            while True:
                try:
                    event = next(gen)
                except StopIteration as stop:
                    summary = stop.value.to_dict() if stop.value is not None else None
                    if summary is not None:
                        state.append_event({"event": "summary", "data": summary})
                        status: ExecutionStatus = "completed" if int(summary.get("exit_code", 1)) == 0 else "failed"
                    else:
                        status = "failed"
                    state.set_done(status=status, summary=summary, error=None)
                    return
                payload = event.payload
                if isinstance(payload, LogEvent):
                    state.append_event(
                        {
                            "event": "log",
                            "data": {
                                "stream": payload.stream,
                                "line": payload.line.rstrip("\n"),
                                "ts": float(payload.ts),
                            },
                        }
                    )
                elif isinstance(payload, RunResult):
                    run_id = payload.command.env.get("UQO_AUDIT_RUN_ID") or payload.command.env.get("UQO_RUN_ID")
                    state.append_event(
                        {
                            "event": "run_result",
                            "data": {
                                "run_id": run_id,
                                "test_type": str(payload.command.env.get("UQO_LAST_TEST_TYPE") or "unknown"),
                                "returncode": int(payload.returncode),
                                "started_at": float(payload.started_at),
                                "finished_at": float(payload.finished_at),
                                "cwd": str(payload.command.cwd),
                            },
                        }
                    )
        except Exception as exc:  # pragma: no cover - defensive fallback
            state.append_event(
                {
                    "event": "summary",
                    "data": {
                        "schema_version": "1",
                        "exit_code": 4,
                        "error": str(exc),
                        "runs": [],
                        "finished_at": time.time(),
                    },
                }
            )
            state.set_done(status="failed", summary=None, error=str(exc))

    @staticmethod
    def _to_engine_spec(spec) -> EngineRunSpec:  # noqa: ANN001
        return EngineRunSpec(
            test_type=TestType(spec.test_type),
            target_repo=Path(spec.target_repo).expanduser().resolve(),
            cli_args=tuple(spec.cli_args),
            timeout_s=spec.timeout_s,
            extra_env=spec.extra_env,
            locust_users=spec.locust_users,
            locust_spawn_rate=spec.locust_spawn_rate,
            locust_run_time=spec.locust_run_time,
            locust_only_summary=spec.locust_only_summary,
        )


def format_sse_message(event_name: str, payload: dict[str, object]) -> str:
    data = json.dumps(payload, separators=(",", ":"), ensure_ascii=True)
    return f"event: {event_name}\ndata: {data}\n\n"
