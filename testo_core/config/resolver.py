"""Plan/stage resolution: env interpolation, plan selection, ``if`` evaluation.

The loader produces an immutable :class:`TestosteroneConfig`.  The resolver
applies the runtime concerns (env substitution, conditional stage inclusion)
just before the orchestrator executes the plan.  Keeping the two phases
separate makes ``testo plans show`` deterministic regardless of the host
environment.
"""

from __future__ import annotations

import os
import re
from collections.abc import Mapping

from testo_core.config.errors import PlanNotFoundError
from testo_core.config.schema import Plan, Stage, TestosteroneConfig

_ENV_PATTERN = re.compile(r"\$\{env:(?P<name>[A-Za-z_][A-Za-z0-9_]*)(?::-(?P<default>[^}]*))?\}")


def resolve_plan(config: TestosteroneConfig, *, plan_name: str | None) -> Plan:
    """Pick the right cycle from the config.

    When ``plan_name`` is ``None`` and exactly one plan is defined, that one
    is returned.  Otherwise an explicit name is required.
    """
    if plan_name is None:
        if len(config.cycles) == 1:
            return next(iter(config.cycles.values()))
        raise PlanNotFoundError("<unspecified>", tuple(config.cycles.keys()))
    try:
        return config.cycles[plan_name]
    except KeyError as exc:
        raise PlanNotFoundError(plan_name, tuple(config.cycles.keys())) from exc


def resolve_stages_for_plan(
    plan: Plan,
    *,
    env: Mapping[str, str] | None = None,
) -> tuple[Stage, ...]:
    """Return only the stages that survive ``${env:...}`` interpolation and ``if`` filtering."""
    env_map = env if env is not None else os.environ
    out: list[Stage] = []
    for stage in plan.stages:
        if not _eval_if(stage.if_expr, env=env_map):
            continue
        resolved_args = tuple(_interpolate(arg, env=env_map) for arg in stage.args)
        resolved_extra_env = tuple(
            (k, _interpolate(v, env=env_map)) for k, v in stage.extra_env
        )
        out.append(
            Stage(
                name=stage.name,
                framework=stage.framework,
                target_repo=stage.target_repo,
                args=resolved_args,
                workers=stage.workers,
                timeout_s=stage.timeout_s,
                if_expr=None,  # already evaluated
                extra_env=resolved_extra_env,
            )
        )
    return tuple(out)


def _interpolate(value: str, *, env: Mapping[str, str]) -> str:
    """Replace every ``${env:NAME[:-DEFAULT]}`` token with its value."""

    def repl(match: re.Match[str]) -> str:
        name = match.group("name")
        default = match.group("default") or ""
        return env.get(name, default)

    return _ENV_PATTERN.sub(repl, value)


def _eval_if(expr: str | None, *, env: Mapping[str, str]) -> bool:
    """Evaluate a simple ``if`` expression.

    Supported grammar (intentionally tiny — never uses ``eval``):

    * ``${env:VAR}`` is interpolated first.
    * ``LHS == "RHS"`` / ``LHS != "RHS"``  → string compare.
    * Bare interpolated string → truthy when non-empty/non-zero.
    """
    if expr is None or not expr.strip():
        return True

    text = _interpolate(expr, env=env).strip()

    for op in ("==", "!="):
        if op in text:
            lhs, rhs = (part.strip().strip('"').strip("'") for part in text.split(op, 1))
            return (lhs == rhs) if op == "==" else (lhs != rhs)

    falsy = {"", "0", "false", "no", "off"}
    return text.lower() not in falsy
