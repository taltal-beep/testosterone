from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import threading
import time
from collections import deque
from collections.abc import AsyncIterator, Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal
from uuid import UUID, uuid4

from testo_core.config.errors import ConfigDiscoveryError
from testo_core.config.loader import discover_and_load
from testo_core.config.resolver import resolve_plan
from testo_core.config.schema import Defaults, Plan, TestosteroneConfig
from testo_core.config.triggers import TriggerResult
from testo_core.services.cycle_run import (
    ADHOC_PLAN_NAME,
    CycleRunOptions,
    CycleRunService,
    single_stage_plan,
)

CycleExecutionStatus = Literal["queued", "running", "completed", "failed"]

logger = logging.getLogger(__name__)

# The registry only exists so clients can follow a run while it is live; the durable
# record of every run is the run history DB. Running executions are always kept;
# finished ones are kept up to this many (oldest evicted first, minimum 1 so a run's
# final status can always be read), so memory stays bounded however many runs happen.
MAX_FINISHED_EXECUTIONS_ENV = "TESTO_MAX_FINISHED_EXECUTIONS"
DEFAULT_MAX_FINISHED_EXECUTIONS = 200


def _max_finished_from_env() -> int:
    raw = os.environ.get(MAX_FINISHED_EXECUTIONS_ENV)
    if raw is None or not raw.strip():
        return DEFAULT_MAX_FINISHED_EXECUTIONS
    try:
        return max(1, int(raw))
    except ValueError:
        logger.warning(
            "%s=%r is not an integer; using %d",
            MAX_FINISHED_EXECUTIONS_ENV,
            raw,
            DEFAULT_MAX_FINISHED_EXECUTIONS,
        )
        return DEFAULT_MAX_FINISHED_EXECUTIONS


# Resolves (config, plan) on the worker thread, so config errors surface as a failed execution.
PlanLoader = Callable[[], tuple[TestosteroneConfig, Plan]]


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
    # Where this execution's events end in the (per-cycle, shared) events file; set on finish.
    events_end_offset_bytes: int | None = None
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

    - `discover_and_load` config discovery + `resolve_plan` (a named cycle), or
      `single_stage_plan` (an ad-hoc run of one framework, see `create_adhoc_execution`)
    - `CycleRunService.run()`, the same use case as `testo run`: trigger gate
      (`cycle_trigger` NDJSON event), `orchestrator.run_plan()` writing durable NDJSON
      into `artifacts/<cycle>/events.ndjson`, reporters and the report archive

    Streaming is done by tailing `events.ndjson` from a recorded byte offset.

    The registry is bounded: every running execution is kept, plus the last
    `max_finished` finished ones (default from `TESTO_MAX_FINISHED_EXECUTIONS`).
    Older finished executions are evicted and their status/events endpoints answer
    404; their results stay in the run history (`/api/v1/runs`).
    """

    def __init__(self, *, max_finished: int | None = None) -> None:
        self._states: dict[str, CycleExecutionState] = {}
        self._states_lock = threading.Lock()
        self._active_by_cycle: dict[str, str] = {}
        configured = _max_finished_from_env() if max_finished is None else max_finished
        self.max_finished = max(1, configured)
        # Finished execution ids, oldest first: the eviction order.
        self._finished: deque[str] = deque()

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
        def load_plan() -> tuple[TestosteroneConfig, Plan]:
            cfg = discover_and_load(config_path=config_path)
            return cfg, resolve_plan(cfg, plan_name=cycle)

        return self._start(
            cycle=str(cycle),
            load_plan=load_plan,
            artifacts_root_override=artifacts_root_override,
            persist=persist,
            force=force,
            fail_fast=fail_fast,
            reporter_override=reporter_override,
            report_db=report_db,
            async_report_db=async_report_db,
            workers_override=workers_override,
            stream=stream,
            ci=ci,
        )

    def create_adhoc_execution(
        self,
        *,
        framework: str,
        target_repo: Path,
        args: Sequence[str] = (),
        timeout_s: float | None = None,
        extra_env: Mapping[str, str] | None = None,
        config_path: Path | None = None,
        artifacts_root_override: Path | None = None,
        persist: bool = True,
        report_db: bool = True,
    ) -> CycleExecutionState:
        """Run one framework directly, as a one-stage ``adhoc`` cycle.

        Validates the stage up front (``ConfigValidationError``). Defaults and
        reporters come from the discovered config when there is one.
        """
        plan = single_stage_plan(
            framework=framework,
            target_repo=target_repo,
            args=args,
            timeout_s=timeout_s,
            extra_env=extra_env,
        )

        def load_plan() -> tuple[TestosteroneConfig, Plan]:
            try:
                cfg = discover_and_load(config_path=config_path)
            except ConfigDiscoveryError:
                if config_path is not None:
                    raise
                cfg = TestosteroneConfig(version=1, defaults=Defaults())
            return cfg, plan

        return self._start(
            cycle=ADHOC_PLAN_NAME,
            load_plan=load_plan,
            artifacts_root_override=artifacts_root_override,
            persist=persist,
            force=False,
            fail_fast=False,
            reporter_override=None,
            report_db=report_db,
            async_report_db=False,
            workers_override=None,
            stream=True,
            ci=True,
        )

    def _start(
        self,
        *,
        cycle: str,
        load_plan: PlanLoader,
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
    ) -> CycleExecutionState:
        execution_id = str(uuid4())
        state = CycleExecutionState(execution_id=execution_id, cycle=cycle, created_at=time.time())

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
                load_plan,
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

    def _run_execution(
        self,
        state: CycleExecutionState,
        load_plan: PlanLoader,
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
        status: CycleExecutionStatus = "failed"
        error: str | None = "execution interrupted"
        try:
            with state.lock:
                state.status = "running"

            cfg, plan = load_plan()
            artifacts_root = (
                (artifacts_root_override or cfg.defaults.artifacts_root).expanduser().resolve()
            )
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

            status, error = "completed", None
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
            error = err
        finally:
            # Record where this run's events end before freeing the cycle: the next run
            # appends to the same file, and streams of this run must stop here.
            if state.events_path is not None:
                try:
                    end = state.events_path.stat().st_size
                except OSError:
                    end = state.events_start_offset_bytes
                with state.lock:
                    state.events_end_offset_bytes = end
            # Free the cycle and update the registry before reporting `done`, so a client
            # that sees the run finish can start the cycle again right away.
            with self._states_lock:
                if self._active_by_cycle.get(state.cycle) == state.execution_id:
                    self._active_by_cycle.pop(state.cycle, None)
                self._finished.append(state.execution_id)
                while len(self._finished) > self.max_finished:
                    self._states.pop(self._finished.popleft(), None)
            state.mark_done(status=status, error=error)


def _sse_message(payload: dict[str, object]) -> str:
    event_name = str(payload.get("event") or "unknown")
    data = json.dumps(payload, separators=(",", ":"), ensure_ascii=True)
    return f"event: {event_name}\ndata: {data}\n\n"


def _read_ndjson(path: Path, offset: int, end: int | None) -> tuple[list[dict[str, object]], int]:
    """Parse the NDJSON objects after byte ``offset``; return them and the new offset.

    While the run is live (``end is None``) a trailing line without its newline is
    still being written, so it is left for the next read. Once the run is done, read
    exactly up to ``end`` (the file is shared by later runs of the same cycle).
    """
    try:
        with path.open("rb") as fh:
            fh.seek(offset)
            chunk = fh.read() if end is None else fh.read(max(0, end - offset))
    except OSError:  # not created yet
        return [], offset if end is None else end
    consumed = chunk.rfind(b"\n") + 1 if end is None else len(chunk)
    payloads: list[dict[str, object]] = []
    for raw in chunk[:consumed].splitlines():
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            payloads.append(payload)
    return payloads, offset + consumed if end is None else end


async def iter_sse_from_ndjson_file(
    *,
    events_path: Path,
    start_offset_bytes: int,
    end_offset: Callable[[], int | None],
    min_poll_s: float = 0.1,
    max_poll_s: float = 2.0,
    keepalive_s: float = 15.0,
) -> AsyncIterator[str]:
    """
    Tail an NDJSON file and emit each JSON object as an SSE message.

    The `data:` payload is the full NDJSON object (including top-level `event`),
    aligned to `docs/CLI Commands/Troubleshooting and Error Codes.md`.

    `end_offset()` is None while the execution runs and, once it is done, the byte
    offset where its events end; the stream drains up to there and closes.

    Per viewer this is one coroutine and a file offset. It sleeps on the event loop
    (a sync generator would hold a threadpool thread per viewer) and the poll interval
    backs off from `min_poll_s` to `max_poll_s` while nothing new is written. When
    the client disconnects, Starlette cancels the response task, which ends the
    stream at its next `await`.
    """
    offset = max(0, int(start_offset_bytes))
    interval = min_poll_s
    last_sent = time.monotonic()
    while True:
        # Sample the end before reading: it is recorded after the worker's last event,
        # so this read is guaranteed to include that event.
        end = end_offset()
        # Off the event loop: a late viewer may have a large backlog to read.
        payloads, offset = await asyncio.to_thread(_read_ndjson, events_path, offset, end)
        for payload in payloads:
            yield _sse_message(payload)
        if end is not None:
            return

        now = time.monotonic()
        if payloads:
            interval = min_poll_s
            last_sent = now
        else:
            interval = min(interval * 2, max_poll_s)
            if now - last_sent >= keepalive_s:
                # Comment line: keeps proxies from timing out an idle stream.
                yield ": keep-alive\n\n"
                last_sent = now
        await asyncio.sleep(interval)


async def iter_execution_sse(
    manager: CycleExecutionManager,
    execution_id: str,
    *,
    min_poll_s: float = 0.1,
    max_poll_s: float = 2.0,
) -> AsyncIterator[str]:
    """SSE stream for one execution: wait until its events file is known, then tail it."""
    # The worker thread learns the events path only after loading the config.
    interval = min_poll_s
    while True:
        state = manager.get(execution_id)
        if state is None:  # evicted: it finished long ago and its result is in run history
            return
        with state.lock:
            events_path, start_offset = state.events_path, state.events_start_offset_bytes
            done, error = state.done, state.error
        if events_path is not None:
            break
        if done:
            # Failed before it had an events file (e.g. a config error): say why.
            message = error or "execution finished without events"
            yield _sse_message({"event": "error", "code": "internal_error", "message": message})
            return
        await asyncio.sleep(interval)
        interval = min(interval * 2, max_poll_s)

    def end_offset() -> int | None:
        current = manager.get(execution_id)
        if current is None:  # evicted mid-stream: nothing more of this run to send
            return 0
        with current.lock:
            return (current.events_end_offset_bytes or 0) if current.done else None

    async for message in iter_sse_from_ndjson_file(
        events_path=events_path,
        start_offset_bytes=start_offset,
        end_offset=end_offset,
        min_poll_s=min_poll_s,
        max_poll_s=max_poll_s,
    ):
        yield message
