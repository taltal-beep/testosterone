from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator, Literal
from uuid import uuid4

from testo_core.config.loader import discover_and_load
from testo_core.config.resolver import resolve_plan, resolve_stages_for_plan
from testo_core.config.schema import Plan, Stage
from testo_core.engine.orchestrator import run_plan
from testo_core.triggers import evaluate_cycle_trigger


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


def _append_ndjson_line(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, separators=(",", ":"), ensure_ascii=True))
        fh.write("\n")
        fh.flush()


class CycleExecutionManager:
    """
    Manage plan/cycle executions using the modern engine lifecycle:

    - `discover_and_load` config discovery
    - `resolve_plan` + `resolve_stages_for_plan`
    - optional trigger evaluation (`cycle_trigger` NDJSON event)
    - `orchestrator.run_plan()` emits durable NDJSON into `artifacts/<cycle>/events.ndjson`

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
            resolved_stages = resolve_stages_for_plan(plan)
            if not resolved_stages:
                raise ValueError(f"plan {plan.name!r} has no stages enabled in this environment.")

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

            # Trigger gate (CI schema): emit `cycle_trigger` and potentially short-circuit to success.
            if plan.trigger is not None and not force:
                tr = evaluate_cycle_trigger(plan=plan, cfg=cfg)
                if ci:
                    _append_ndjson_line(
                        events_path,
                        {
                            "event": "cycle_trigger",
                            "cycle": plan.name,
                            "status": "activated" if tr.stimulus else "resting",
                            "reason": tr.reason,
                            "matched": list(tr.matched_paths),
                            "mode": tr.mode,
                        },
                    )
                if not tr.stimulus:
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
                    return

            renderer = _NullRenderer()
            effective_plan = _apply_workers_override(plan=plan, stages=resolved_stages, workers_override=workers_override)
            # `run_plan` persists events.ndjson and plan_result.json under artifacts/<cycle>/.
            result = run_plan(
                plan=effective_plan,
                renderer=renderer,
                artifacts_root=artifacts_root,
                persist=persist,
                fail_fast=fail_fast,
            )

            # Post-run reporters + optional report DB archive (same flow as CLI runner).
            if cfg.reporters or reporter_override:
                from rich.console import Console

                from testo_core.reporting.reporters.orchestrate import run_configured_reporters

                run_configured_reporters(
                    cfg=cfg,
                    artifacts_root=artifacts_root,
                    plan_name=effective_plan.name,
                    reporter_override=reporter_override,
                    console=Console(),
                    ci=ci,
                    generate_only=True,
                )

            if persist and report_db:
                from rich.console import Console

                from testo_core.cli.runner import _maybe_archive_cycle_report  # type: ignore[attr-defined]

                _maybe_archive_cycle_report(
                    cfg=cfg,
                    plan=effective_plan,
                    console=Console(),
                    ci=ci,
                    persist=persist,
                    report_db=report_db,
                    async_report_db=async_report_db,
                    plan_exit_code=int(result.exit_code),
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


def _apply_workers_override(*, plan: Plan, stages: tuple[Stage, ...], workers_override: int | None) -> Plan:
    if workers_override is None:
        return Plan(
            name=plan.name,
            description=plan.description,
            stages=tuple(stages),
            trigger=plan.trigger,
            tags=plan.tags,
        )
    new_stages = tuple(
        Stage(
            name=s.name,
            framework=s.framework,
            target_repo=s.target_repo,
            args=s.args,
            workers=int(workers_override),
            timeout_s=s.timeout_s,
            if_expr=None,
            extra_env=s.extra_env,
        )
        for s in stages
    )
    return Plan(
        name=plan.name,
        description=plan.description,
        stages=new_stages,
        trigger=plan.trigger,
        tags=plan.tags,
    )


def iter_sse_from_ndjson_file(
    *,
    events_path: Path,
    start_offset_bytes: int,
    is_done: "callable[[], bool]",
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

