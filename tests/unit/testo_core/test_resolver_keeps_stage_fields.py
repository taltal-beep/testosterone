"""Resolving a cycle must not drop stage fields it doesn't touch.

Cycle resolution and the ``--workers`` override used to copy ``Stage`` field by
field and silently lost ``tier`` and ``junit_xml``, so a ``command`` stage's
JUnit results were never imported in a real ``testo run``.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from testo_core.config.resolver import resolve_stages_for_plan
from testo_core.config.schema import Plan, Stage
from testo_core.services.cycle_run import apply_workers_override

pytestmark = [pytest.mark.unit, pytest.mark.tier_fast]


def _stage_with_every_field_set() -> Stage:
    """A stage whose every field differs from its default, so a dropped field shows."""
    stage = Stage(
        name="web",
        framework="command",
        target_repo=Path("/repo"),
        args=("npx", "jest"),
        workers=7,
        timeout_s=42.0,
        if_expr=None,
        extra_env=(("CI", "1"),),
        tier="e2e",
        junit_xml=("reports/*.xml",),
    )
    defaults = Stage(name="x", framework="pytest", target_repo=Path("/"))
    unset = [
        f.name
        for f in dataclasses.fields(Stage)
        if f.name != "if_expr" and getattr(stage, f.name) == getattr(defaults, f.name)
    ]
    assert not unset, f"give these fields a non-default value in this test: {unset}"
    return stage


def _fields(stage: Stage) -> dict[str, object]:
    return {f.name: getattr(stage, f.name) for f in dataclasses.fields(Stage)}


def test_resolution_keeps_every_field() -> None:
    stage = _stage_with_every_field_set()

    (resolved,) = resolve_stages_for_plan(
        Plan(name="app", description=None, stages=(stage,)), env={}
    )

    assert _fields(resolved) == _fields(stage)


def test_workers_override_keeps_every_other_field() -> None:
    stage = _stage_with_every_field_set()
    plan = Plan(name="app", description=None, stages=(stage,))

    (overridden,) = apply_workers_override(plan, plan.stages, 2).stages

    assert overridden.workers == 2
    assert _fields(overridden) == {**_fields(stage), "workers": 2}
