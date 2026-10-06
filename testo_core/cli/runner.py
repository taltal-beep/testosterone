"""Bridge module that wires ``testo run`` to :class:`~testo_core.services.cycle_run.CycleRunService`.

This is the only CLI-side module that knows the renderer classes.  The
service and the engine only see a :class:`testo_core.cli.ui.renderers.Renderer`
protocol instance and a listener for trigger/archive messages.
"""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

from rich.console import Console
from rich.panel import Panel

from testo_core.cli.ui.renderers import (
    BufferedRenderer,
    CIRenderer,
    Renderer,
    StreamRenderer,
)
from testo_core.config.errors import ConfigDiscoveryError, ConfigError, PlanNotFoundError
from testo_core.config.loader import discover_and_load
from testo_core.config.resolver import resolve_plan
from testo_core.config.schema import Plan, TestosteroneConfig
from testo_core.engine.exit_codes import EngineExitCode
from testo_core.triggers import TriggerResult


def execute_plan_command(
    *,
    console: Console,
    plan_name: str | None,
    config_path: Path | None,
    stream: bool,
    ci: bool,
    persist: bool,
    workers_override: int | None,
    force: bool = False,
    report_db: bool = True,
    async_report_db: bool = False,
) -> int:
    """Load + resolve + execute one plan (or every cycle when ``plan_name == 'all'``)."""
    try:
        cfg = discover_and_load(config_path=config_path)
    except (ConfigError, ConfigDiscoveryError) as exc:
        _emit_config_error(console=console, exc=exc, ci=ci)
        return int(EngineExitCode.INVALID_INPUT)

    if plan_name == "all":
        if not cfg.cycles:
            _emit_config_error(
                console=console,
                exc=ConfigError("no cycles defined in configuration."),
                ci=ci,
            )
            return int(EngineExitCode.INVALID_INPUT)
        worst = 0
        for name in sorted(cfg.cycles.keys()):
            ec = _execute_one_cycle(
                cfg=cfg,
                plan=cfg.cycles[name],
                console=console,
                stream=stream,
                ci=ci,
                persist=persist,
                workers_override=workers_override,
                force=force,
                report_db=report_db,
                async_report_db=async_report_db,
            )
            worst = max(worst, ec)
        return worst

    try:
        plan = resolve_plan(cfg, plan_name=plan_name)
    except PlanNotFoundError as exc:
        _emit_config_error(console=console, exc=exc, ci=ci)
        return int(EngineExitCode.INVALID_INPUT)

    return _execute_one_cycle(
        cfg=cfg,
        plan=plan,
        console=console,
        stream=stream,
        ci=ci,
        persist=persist,
        workers_override=workers_override,
        force=force,
        report_db=report_db,
        async_report_db=async_report_db,
    )


def _execute_one_cycle(
    *,
    cfg: TestosteroneConfig,
    plan: Plan,
    console: Console,
    stream: bool,
    ci: bool,
    persist: bool,
    workers_override: int | None,
    force: bool,
    report_db: bool = True,
    async_report_db: bool = False,
) -> int:
    from testo_core.services.cycle_run import CycleRunOptions, CycleRunService, NoStagesEnabledError

    service = CycleRunService(
        listener=_ConsoleCycleListener(console=console, ci=ci), console=console
    )
    try:
        outcome = service.run(
            cfg=cfg,
            plan=plan,
            renderer=_pick_renderer(console=console, stream=stream, ci=ci),
            options=CycleRunOptions(
                persist=persist,
                force=force,
                workers_override=workers_override,
                report_db=report_db,
                async_report_db=async_report_db,
                ci=ci,
            ),
        )
    except NoStagesEnabledError as exc:
        _emit_config_error(console=console, exc=exc, ci=ci)
        return int(EngineExitCode.INVALID_INPUT)
    return outcome.exit_code


class _ConsoleCycleListener:
    """Renders the service's trigger and archive moments as Rich panels or NDJSON."""

    def __init__(self, *, console: Console, ci: bool) -> None:
        self._console = console
        self._ci = ci

    def trigger_evaluated(self, plan: Plan, result: TriggerResult) -> None:
        _emit_cycle_trigger_event(ci=self._ci, plan=plan, tr=result)
        if result.stimulus:
            _emit_cycle_activating(console=self._console, ci=self._ci, plan=plan, tr=result)
        else:
            _emit_cycle_resting(console=self._console, ci=self._ci, plan=plan)

    def trigger_bypassed(self, plan: Plan) -> None:
        if not self._ci:
            self._console.print("[muted]Trigger bypassed (--force).[/]")

    def report_archived(self, report_id: UUID | None, *, background: bool) -> None:
        if self._ci:
            return
        if background:
            self._console.print(
                "[dim]Report database archive started in background "
                "(may not complete if the process exits immediately).[/]"
            )
        elif report_id is not None:
            self._console.print(f"[muted]Archived cycle report[/] [bold]{report_id}[/]")


def _emit_cycle_trigger_event(*, ci: bool, plan: Plan, tr: TriggerResult) -> None:
    if not ci:
        return
    from testo_core.cli.ui.ci_renderer import emit_ndjson

    emit_ndjson(
        {
            "event": "cycle_trigger",
            "cycle": plan.name,
            "status": "activated" if tr.stimulus else "resting",
            "reason": tr.reason,
            "matched": list(tr.matched_paths),
            "mode": tr.mode,
        }
    )


def _emit_cycle_resting(*, console: Console, ci: bool, plan: Plan) -> None:
    if ci:
        return
    msg = f"Cycle {plan.name} skipped: No stimulus detected in targeted muscle groups."
    console.print(Panel(msg, title="Resting", border_style="dim"))


def _emit_cycle_activating(*, console: Console, ci: bool, plan: Plan, tr: TriggerResult) -> None:
    if ci:
        return
    hint = tr.matched_paths[0] if tr.matched_paths else ""
    if not hint and plan.trigger is not None and plan.trigger.paths:
        hint = plan.trigger.paths[0]
    body = f"[ok]Stimulus detected[/] in [bold]{hint}[/]. [bold]Activating Cycle:[/] {plan.name}."
    console.print(Panel(body, title="Trigger", border_style="green"))


def _pick_renderer(*, console: Console, stream: bool, ci: bool) -> Renderer:
    if ci:
        return CIRenderer()
    if stream:
        return StreamRenderer(console)
    return BufferedRenderer(console)


def _emit_config_error(*, console: Console, exc: Exception, ci: bool) -> None:
    if ci:
        from testo_core.cli.ui.ci_renderer import emit_ndjson

        emit_ndjson({"event": "error", "code": "invalid_input", "message": str(exc)})
    else:
        console.print(f"[fail]error:[/] {exc}")
