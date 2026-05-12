"""Bridge module that wires ``testo run`` to the engine.

This is the only CLI-side module that knows the renderer classes.  Engine
internals only see a :class:`testo_core.cli.ui.renderers.Renderer` protocol
instance.
"""

from __future__ import annotations

from pathlib import Path

from rich.console import Console

from testo_core.cli.ui.renderers import (
    BufferedRenderer,
    CIRenderer,
    Renderer,
    StreamRenderer,
)
from testo_core.config.errors import ConfigDiscoveryError, ConfigError, PlanNotFoundError
from testo_core.config.loader import discover_and_load
from testo_core.config.resolver import resolve_plan, resolve_stages_for_plan
from testo_core.engine.exit_codes import EngineExitCode


def execute_plan_command(
    *,
    console: Console,
    plan_name: str | None,
    config_path: Path | None,
    stream: bool,
    ci: bool,
    persist: bool,
    workers_override: int | None,
) -> int:
    """Load + resolve + execute one plan; return the process exit code."""
    try:
        cfg = discover_and_load(config_path=config_path)
    except (ConfigError, ConfigDiscoveryError) as exc:
        _emit_config_error(console=console, exc=exc, ci=ci)
        return int(EngineExitCode.INVALID_INPUT)

    try:
        plan = resolve_plan(cfg, plan_name=plan_name)
    except PlanNotFoundError as exc:
        _emit_config_error(console=console, exc=exc, ci=ci)
        return int(EngineExitCode.INVALID_INPUT)

    resolved_stages = resolve_stages_for_plan(plan)
    if not resolved_stages:
        _emit_config_error(
            console=console,
            exc=ConfigError(f"plan {plan.name!r} has no stages enabled in this environment."),
            ci=ci,
        )
        return int(EngineExitCode.INVALID_INPUT)

    renderer = _pick_renderer(console=console, stream=stream, ci=ci)

    # Apply runtime overrides without mutating the immutable Plan.
    effective_plan = _apply_workers_override(plan, resolved_stages, workers_override)

    # Deferred engine import: keeps `testo --help` cheap.
    from testo_core.engine.orchestrator import run_plan

    result = run_plan(
        plan=effective_plan,
        renderer=renderer,
        artifacts_root=cfg.defaults.artifacts_root,
        persist=persist,
    )
    return int(result.exit_code)


def _pick_renderer(*, console: Console, stream: bool, ci: bool) -> Renderer:
    if ci:
        return CIRenderer()
    if stream:
        return StreamRenderer(console)
    return BufferedRenderer(console)


def _apply_workers_override(plan, stages, workers_override):  # type: ignore[no-untyped-def]
    """Return a new Plan with the workers override applied to every stage."""
    if workers_override is None:
        # Just swap in the resolved stages.
        from testo_core.config.schema import Plan

        return Plan(name=plan.name, description=plan.description, stages=tuple(stages))

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
    return Plan(name=plan.name, description=plan.description, stages=new_stages)


def _emit_config_error(*, console: Console, exc: Exception, ci: bool) -> None:
    if ci:
        from testo_core.cli.ui.ci_renderer import emit_ndjson

        emit_ndjson({"event": "error", "code": "invalid_input", "message": str(exc)})
    else:
        console.print(f"[fail]error:[/] {exc}")
