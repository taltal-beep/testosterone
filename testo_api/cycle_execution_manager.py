from __future__ import annotations

import json
import os
import sys
import threading
import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal
from uuid import UUID, uuid4

from testo_core.config.loader import discover_and_load
from testo_core.config.resolver import resolve_plan
from testo_core.config.schema import Plan
from testo_core.services.cycle_run import CycleRunOptions, CycleRunService
from testo_core.triggers import TriggerResult

CycleExecutionStatus = Literal["queued", "running", "completed", "failed"]


@dataclass
class CycleExecutionState:
    execution_id: str
    cycle: str
    created_at: float
    status: CycleExecutionStatus = "queued"
    artifacts_root: Path | None = None
    plan_result_path: Path | None = None
    events_path: Path | None = None
    events_start_offset_bytes: int = 0
    done: bool = False
    error: str | None = None
    lock: threading.Lock = field(default_factory=threading.Lock)

    def mark_done(self, *, status: CycleExecutionStatus, error: str | None = None) -> None:
        with self.lock:
            self.status = status
            self.error = error
            self.done = True


class _NullRenderer:
    wants_streaming = False

    def handle(self, _event) -> None:  # noqa: ANN001
        return


class _NdjsonCycleListener:
    """Writes the trigger verdict into the cycle's events.ndjson so the SSE stream carries it."""

    def __init__(self, events_path: Path, *, ci: bool) -> None:
        self._events_path = events_path
        self._ci = ci

    def trigger_evaluated(self, plan: Plan, result: TriggerResult) -> None:
        if not self._ci:
            return
        _append_ndjson_line(
            self._events_path,
            {
                "event": "cycle_trigger",
                "cycle": plan.name,
                "status": "activated" if result.stimulus else "resting",
                "reason": result.reason,
                "matched": list(result.matched_paths),
                "mode": result.mode,
            },
        )

    def trigger_bypassed(self, plan: Plan) -> None:
        return

    def report_archived(self, report_id: UUID | None, *, background: bool) -> None:
        return


def _append_ndjson_line(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, separators=(",", ":"), ensure_ascii=True))
        fh.write("\n")
        fh.flush()


class CycleExecutionManager:
    """
    Manage plan/cycle executions using the modern engine lifecycle:

    - `discover_and_load` config discovery + `resolve_plan`
    - `CycleRunService.run()`, the same use case as `testo run`: trigger gate
      (`cycle_trigger` NDJSON event), `orchestrator.run_plan()` writing durable NDJSON
      into `artifacts/<cycle>/events.ndjson`, reporters and the report archive

    Streaming is done by tailing `events.ndjson` from a recorded byte offset.
    """

    def __init__(self) -> None:
        self._states: dict[str, CycleExecutionState] = {}
        self._states_lock = threading.Lock()
        self._active_by_cycle: dict[str, str] = {}

    def create_execution(
        self,
        *,
        cycle: str,
        config_path: Path | None,
        artifacts_root_override: Path | None = None,
        persist: bool = True,
        force: bool = False,
        fail_fast: bool = False,
        reporter_override: list[str] | None = None,
        report_db: bool = True,
        async_report_db: bool = False,
        workers_override: int | None = None,
        stream: bool = False,
        ci: bool = True,
    ) -> CycleExecutionState:
        execution_id = str(uuid4())
        state = CycleExecutionState(execution_id=execution_id, cycle=str(cycle), created_at=time.time())

        with self._states_lock:
            existing = self._active_by_cycle.get(str(cycle))
            if existing is not None:
                raise RuntimeError(f"cycle {cycle!r} already running (execution_id={existing})")
            self._states[execution_id] = state
            self._active_by_cycle[str(cycle)] = execution_id

        threading.Thread(
            target=self._run_execution,
            args=(
                state,
                config_path,
                artifacts_root_override,
                persist,
                force,
                fail_fast,
                reporter_override,
                report_db,
                async_report_db,
                workers_override,
                stream,
                ci,
            ),
            daemon=True,
        ).start()
        return state

    def get(self, execution_id: str) -> CycleExecutionState | None:
        with self._states_lock:
            return self._states.get(execution_id)

    def resolve_events_path(self, execution_id: str) -> tuple[Path, int, bool]:
        state = self.get(execution_id)
        if state is None:
            raise KeyError(execution_id)
        with state.lock:
            if state.events_path is None:
                raise RuntimeError("events file not initialized yet")
            return state.events_path, int(state.events_start_offset_bytes), bool(state.done)

    def _run_execution(
        self,
        state: CycleExecutionState,
        config_path: Path | None,
        artifacts_root_override: Path | None,
        persist: bool,
        force: bool,
        fail_fast: bool,
        reporter_override: list[str] | None,
        report_db: bool,
        async_report_db: bool,
        workers_override: int | None,
        stream: bool,
        ci: bool,
    ) -> None:
        try:
            with state.lock:
                state.status = "running"

            cfg = discover_and_load(config_path=config_path)
            plan = resolve_plan(cfg, plan_name=state.cycle)
            artifacts_root = (artifacts_root_override or cfg.defaults.artifacts_root).expanduser().resolve()
            plan_artifacts = (artifacts_root / plan.name).resolve()
            events_path = plan_artifacts / "events.ndjson"
            plan_result_path = plan_artifacts / "plan_result.json"

            plan_artifacts.mkdir(parents=True, exist_ok=True)
            start_offset = 0
            try:
                start_offset = int(events_path.stat().st_size) if events_path.exists() else 0
            except OSError:
                start_offset = 0

            with state.lock:
                state.artifacts_root = artifacts_root
                state.events_path = events_path
                state.plan_result_path = plan_result_path
                state.events_start_offset_bytes = start_offset

            # Stage subprocesses resolve tools (pytest/behave/...) via PATH. The API server
            # may be launched without an activated venv, so prepend this interpreter's bin
            # dir to guarantee stages run against the same environment as the engine.
            parent_env = dict(os.environ)
            # Note: do not resolve() — in a venv, sys.executable is a symlink into the
            # base interpreter; resolving it would point PATH at the wrong bin dir.
            exe_bin = str(Path(sys.executable).parent)
            path_entries = parent_env.get("PATH", "").split(os.pathsep)
            if exe_bin not in path_entries:
                parent_env["PATH"] = os.pathsep.join([exe_bin, *path_entries])

            # Same use case as `testo run`; `run_plan` persists events.ndjson and
            # plan_result.json under artifacts/<cycle>/, which the SSE route tails.
            outcome = CycleRunService(listener=_NdjsonCycleListener(events_path, ci=ci)).run(
                cfg=cfg,
                plan=plan,
                renderer=_NullRenderer(),
                options=CycleRunOptions(
                    persist=persist,
                    force=force,
                    fail_fast=fail_fast,
                    workers_override=workers_override,
                    reporter_override=reporter_override,
                    report_db=report_db,
                    async_report_db=async_report_db,
                    artifacts_root=artifacts_root,
                    parent_env=parent_env,
                    ci=ci,
                ),
            )
            if outcome.skipped:
                # Contract: treat resting as success (exit_code 0). Emit a minimal `plan_finished`
                # so UIs relying on a terminal event can close the stream.
                _append_ndjson_line(
                    events_path,
                    {
                        "event": "plan_finished",
                        "plan": plan.name,
                        "aggregate_returncode": 0,
                        "exit_code": 0,
                        "duration_s": 0.0,
                        "stages": [],
                        "error": None,
                    },
                )

            state.mark_done(status="completed", error=None)
        except Exception as exc:  # pragma: no cover (defensive: surfaces in API)
            # Keep error exposure minimal (redaction happens upstream in API error formatting where needed).
            err = str(exc)
            try:
                if state.events_path is not None:
                    _append_ndjson_line(
                        state.events_path,
                        {"event": "error", "code": "internal_error", "message": err},
                    )
            except Exception:
                pass
            state.mark_done(status="failed", error=err)
        finally:
            with self._states_lock:
                if self._active_by_cycle.get(state.cycle) == state.execution_id:
                    self._active_by_cycle.pop(state.cycle, None)


def iter_sse_from_ndjson_file(
    *,
    events_path: Path,
    start_offset_bytes: int,
    is_done: callable[[], bool],
    poll_interval_s: float = 0.2,
) -> Iterator[str]:
    """
    Tail an NDJSON file and emit each JSON object as an SSE message.

    The `data:` payload is the full NDJSON object (including top-level `event`),
    aligned to `docs/CLI Commands/Troubleshooting and Error Codes.md`.
    """
    offset = max(0, int(start_offset_bytes))
    while True:
        try:
            if events_path.exists():
                with events_path.open("r", encoding="utf-8", errors="replace") as fh:
                    fh.seek(offset)
                    while True:
                        line = fh.readline()
                        if not line:
                            offset = fh.tell()
                            break
                        raw = line.strip()
                        if not raw:
                            continue
                        try:
                            payload = json.loads(raw)
                        except json.JSONDecodeError:
                            continue
                        event_name = str(payload.get("event") or "unknown")
                        data = json.dumps(payload, separators=(",", ":"), ensure_ascii=True)
                        yield f"event: {event_name}\ndata: {data}\n\n"
        except OSError:
            pass

        if is_done():
            # Best-effort: allow a short final read window for late flushes.
            time.sleep(float(poll_interval_s))
            if is_done():
                return
        yield ": keep-alive\n\n"
        time.sleep(float(poll_interval_s))

