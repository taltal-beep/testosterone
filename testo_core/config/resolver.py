"""Plan/stage resolution: env interpolation, plan selection, ``if`` evaluation.

The loader produces an immutable :class:`TestosteroneConfig`.  The resolver
applies the runtime concerns (env substitution, conditional stage inclusion)
just before the orchestrator executes the plan.  Keeping the two phases
separate makes ``testo plans show`` deterministic regardless of the host
environment.
"""

from __future__ import annotations

import dataclasses
import os
from collections.abc import Mapping

from testo_core.config import if_expr
from testo_core.config.errors import UNSPECIFIED_PLAN, PlanNotFoundError
from testo_core.config.schema import Plan, Stage, TestosteroneConfig

_ENV_PATTERN = if_expr.ENV_PATTERN


def resolve_plan(config: TestosteroneConfig, *, plan_name: str | None) -> Plan:
    """Pick the right cycle from the config.

    When ``plan_name`` is ``None`` and exactly one plan is defined, that one
    is returned.  Otherwise an explicit name is required.
    """
    if plan_name is None:
        if len(config.cycles) == 1:
            return next(iter(config.cycles.values()))
        raise PlanNotFoundError(UNSPECIFIED_PLAN, tuple(config.cycles.keys()))
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
        resolved_extra_env = tuple((k, _interpolate(v, env=env_map)) for k, v in stage.extra_env)
        # ``replace`` keeps every other Stage field (tier, junit_xml, ...) intact.
        out.append(
            dataclasses.replace(
                stage,
                args=resolved_args,
                extra_env=resolved_extra_env,
                if_expr=None,  # already evaluated
            )
        )
    return tuple(out)


def _interpolate(value: str, *, env: Mapping[str, str]) -> str:
    """Replace every ``${env:NAME[:-DEFAULT]}`` token with its value."""
    return if_expr.interpolate(value, env=env)


def _eval_if(expr: str | None, *, env: Mapping[str, str]) -> bool:
    """Evaluate a stage's ``if:`` (grammar in :mod:`testo_core.config.if_expr`)."""
    return if_expr.evaluate(expr, env=env)
