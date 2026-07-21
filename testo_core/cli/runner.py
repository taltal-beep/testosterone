"""Bridge module that wires ``testo run`` to the engine.

This is the only CLI-side module that knows the renderer classes.  Engine
internals only see a :class:`testo_core.cli.ui.renderers.Renderer` protocol
instance.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

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
from testo_core.config.resolver import resolve_plan, resolve_stages_for_plan
from testo_core.config.schema import Plan, TestosteroneConfig
from testo_core.engine.exit_codes import EngineExitCode
from testo_core.triggers import TriggerResult, evaluate_cycle_trigger, persist_trigger_snapshot


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
    resolved_stages = resolve_stages_for_plan(plan)
    if not resolved_stages:
        _emit_config_error(
            console=console,
            exc=ConfigError(f"plan {plan.name!r} has no stages enabled in this environment."),
            ci=ci,
        )
        return int(EngineExitCode.INVALID_INPUT)

    tr_result: TriggerResult | None = None
    if plan.trigger is not None and not force:
        tr_result = evaluate_cycle_trigger(plan=plan, cfg=cfg)
        _emit_cycle_trigger_event(ci=ci, plan=plan, tr=tr_result)
        if not tr_result.stimulus:
            _emit_cycle_resting(console=console, ci=ci, plan=plan)
            return int(EngineExitCode.SUCCESS)
        _emit_cycle_activating(console=console, ci=ci, plan=plan, tr=tr_result)
    elif plan.trigger is not None and force and not ci:
        console.print("[muted]Trigger bypassed (--force).[/]")

    renderer = _pick_renderer(console=console, stream=stream, ci=ci)
    effective_plan = _apply_workers_override(plan, resolved_stages, workers_override)

    from testo_core.engine.orchestrator import run_plan

    result = run_plan(
        plan=effective_plan,
        renderer=renderer,
        artifacts_root=cfg.defaults.artifacts_root,
        persist=persist,
    )
    exit_int = int(result.exit_code)
    run_id = result.extra.get("run_id")
    _maybe_run_configured_reporters(
        cfg=cfg,
        plan=effective_plan,
        artifacts_root=cfg.defaults.artifacts_root,
        run_id=run_id if isinstance(run_id, str) else None,
        console=console,
        ci=ci,
    )
    _maybe_archive_cycle_report(
        cfg=cfg,
        plan=effective_plan,
        console=console,
        ci=ci,
        persist=persist,
        report_db=report_db,
        async_report_db=async_report_db,
        plan_exit_code=exit_int,
    )
    if (
        tr_result is not None
        and tr_result.persist_snapshot_after_run
        and exit_int == 0
        and cfg.source_path is not None
        and plan.trigger is not None
    ):
        persist_trigger_snapshot(
            cfg=cfg,
            plan_name=plan.name,
            anchor=cfg.source_path.parent.expanduser().resolve(),
            patterns=plan.trigger.paths,
        )
    return exit_int


def _maybe_archive_cycle_report(
    *,
    cfg: TestosteroneConfig,
    plan: Plan,
    console: Console,
    ci: bool,
    persist: bool,
    report_db: bool,
    async_report_db: bool,
    plan_exit_code: int,
) -> None:
    if not persist or not report_db:
        return

    from testo_core.services.report_archive import try_persist_cycle_report

    artifacts_root = cfg.defaults.artifacts_root
    if async_report_db:
        import threading

        def _job() -> None:
            try_persist_cycle_report(
                artifacts_root=artifacts_root,
                plan_name=plan.name,
                exit_code_override=plan_exit_code,
            )

        threading.Thread(target=_job, daemon=True, name="testo-report-archive").start()
        if not ci:
            console.print(
                "[dim]Report database archive started in background "
                "(may not complete if the process exits immediately).[/]"
            )
        return

    rid = try_persist_cycle_report(
        artifacts_root=artifacts_root,
        plan_name=plan.name,
        exit_code_override=plan_exit_code,
    )
    if rid is not None and not ci:
        console.print(f"[muted]Archived cycle report[/] [bold]{rid}[/]")


def _maybe_run_configured_reporters(
    *,
    cfg: TestosteroneConfig,
    plan: Plan,
    artifacts_root: Path,
    run_id: str | None,
    console: Console,
    ci: bool,
    reporter_override: Sequence[str] | None = None,
) -> None:
    """Run configured HTML reporters (Allure/Extent/ReportPortal/TestBeats) after a cycle.

    Best-effort: the reporters subsystem may not be present in every build
    (see :mod:`testo_core.reporting.reporters`); skip instead of failing the
    run. When *run_id* is known (persistence succeeded), Allure's HTML is
    written directly under ``STATIC_HISTORY_ROOT/<run_id>/allure_report/`` so
    the Run Detail page's ``GET /api/v1/runs/{run_id}/reports`` can find it.
    """
    config_reporters = getattr(cfg, "reporters", ()) or ()
    if not config_reporters and not reporter_override:
        return

    try:
        from testo_core.reporting.reporters.orchestrate import run_configured_reporters
    except ImportError:
        return

    out_dir = None
    if run_id:
        from testo_core.run_history import STATIC_HISTORY_ROOT

        out_dir = STATIC_HISTORY_ROOT / run_id / "allure_report"

    run_configured_reporters(
        cfg=cfg,
        artifacts_root=artifacts_root,
        plan_name=plan.name,
        reporter_override=reporter_override,
        run_id=run_id,
        console=console,
        ci=ci,
        generate_only=True,
        out_dir=out_dir,
    )


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


def _apply_workers_override(plan, stages, workers_override):  # type: ignore[no-untyped-def]
    """Return a new Plan with the workers override applied to every stage."""
    if workers_override is None:
        from testo_core.config.schema import Plan

        return Plan(
            name=plan.name,
            description=plan.description,
            stages=tuple(stages),
            trigger=plan.trigger,
        )

    from testo_core.config.schema import Plan, Stage

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
    )


def _emit_config_error(*, console: Console, exc: Exception, ci: bool) -> None:
    if ci:
        from testo_core.cli.ui.ci_renderer import emit_ndjson

        emit_ndjson({"event": "error", "code": "invalid_input", "message": str(exc)})
    else:
        console.print(f"[fail]error:[/] {exc}")
