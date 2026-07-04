"""Unit tests for ``run_plan`` lifecycle & state (QA Strategies LC/ST rows).

Complements ``test_orchestrator.py`` (fail-fast rows): full ``events.ndjson``
contract, renderer event sequence, streaming chunk fan-out, persistence
hand-off (``plan_result.json``), and the internal-failure path (EC-04).
The executor is stubbed; real-subprocess coverage lives in
``tests/integration/testo_core/engine/test_subprocess_smoke.py``.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Callable

import pytest

import testo_core.persistence
from testo_core.config.schema import Plan, Stage
from testo_core.engine import orchestrator
from testo_core.engine.events import (
    EngineEvent,
    PlanFinished,
    PlanStarted,
    StageFinished,
    StageOutputChunk,
    StageStarted,
)
from testo_core.engine.exit_codes import EngineExitCode
from testo_core.engine.result import PlanResult, StageResult
from testo_core.persistence.json_backend import JsonBackend
from tests.fixtures.engine import read_artifact_events

pytestmark = [pytest.mark.unit, pytest.mark.tier_fast]


class _RecordingRenderer:
    wants_streaming = False

    def __init__(self) -> None:
        self.events: list[EngineEvent] = []

    def handle(self, event: EngineEvent) -> None:
        self.events.append(event)


class _StreamingRenderer(_RecordingRenderer):
    wants_streaming = True


def _stage(name: str) -> Stage:
    return Stage(name=name, framework="pytest", target_repo=Path("."))


def _plan(*names: str, plan_name: str = "lifecycle-plan") -> Plan:
    return Plan(name=plan_name, description=None, stages=tuple(_stage(n) for n in names))


def _result(stage: Stage, *, returncode: int = 0, timed_out: bool = False, error: str | None = None) -> StageResult:
    now = time.time()
    return StageResult(
        stage_name=stage.name,
        framework=stage.framework,
        returncode=returncode,
        started_at=now,
        finished_at=now,
        duration_s=0.1,
        log_path=Path(f"/tmp/{stage.name}.log"),
        artifacts_dir=Path("."),
        command=("pytest",),
        output_tail="",
        timed_out=timed_out,
        error=error,
    )


def _stub_executor(
    monkeypatch: pytest.MonkeyPatch,
    make_result: Callable[[Stage], StageResult],
) -> None:
    def fake_run_stage(stage: Stage, *, on_chunk=None, **_: object) -> StageResult:
        return make_result(stage)

    monkeypatch.setattr(orchestrator, "run_stage", fake_run_stage)


def test_events_ndjson_full_lifecycle_and_field_contract(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan = _plan("lint", "unit")
    _stub_executor(monkeypatch, _result)

    orchestrator.run_plan(plan, renderer=_RecordingRenderer(), artifacts_root=tmp_path, persist=False)

    events = read_artifact_events(tmp_path, plan.name)
    assert [e["event"] for e in events] == [
        "plan_started",
        "stage_started",
        "stage_finished",
        "stage_started",
        "stage_finished",
        "plan_finished",
    ]

    assert events[0] == {"event": "plan_started", "plan": plan.name, "stage_count": 2}
    assert events[1] == {
        "event": "stage_started",
        "stage": "lint",
        "framework": "pytest",
        "index": 1,
        "count": 2,
    }
    finished = events[2]
    assert finished["returncode"] == 0
    assert finished["timed_out"] is False
    assert finished["error"] is None
    assert finished["internal_failure"] is False
    assert finished["log_path"].endswith("lint.log")
    assert events[-1]["event"] == "plan_finished"
    assert events[-1]["exit_code"] == 0
    assert events[-1]["aggregate_returncode"] == 0


def test_artifact_mirror_includes_error_on_timeout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # ST: the artifact events.ndjson carries `error` even though CIRenderer
    # stdout omits it on stage_finished.
    plan = _plan("hang")
    _stub_executor(
        monkeypatch,
        lambda stage: _result(stage, returncode=124, timed_out=True, error="stage exceeded timeout_s=0.5"),
    )

    result = orchestrator.run_plan(
        plan, renderer=_RecordingRenderer(), artifacts_root=tmp_path, persist=False
    )

    assert result.exit_code is EngineExitCode.INFRA_FAILURE
    finished = [e for e in read_artifact_events(tmp_path, plan.name) if e["event"] == "stage_finished"][0]
    assert finished["timed_out"] is True
    assert finished["returncode"] == 124
    assert finished["error"] == "stage exceeded timeout_s=0.5"


def test_renderer_receives_ordered_engine_events(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan = _plan("lint", "unit")
    _stub_executor(monkeypatch, _result)
    renderer = _RecordingRenderer()

    orchestrator.run_plan(plan, renderer=renderer, artifacts_root=tmp_path, persist=False)

    assert [type(e) for e in renderer.events] == [
        PlanStarted,
        StageStarted,
        StageFinished,
        StageStarted,
        StageFinished,
        PlanFinished,
    ]
    assert isinstance(renderer.events[0], PlanStarted) and renderer.events[0].plan is plan
    stage_started = renderer.events[1]
    assert isinstance(stage_started, StageStarted)
    assert (stage_started.stage_index, stage_started.stage_count) == (1, 2)


def test_streaming_renderer_gets_stage_output_chunks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan = _plan("stream-stage")
    renderer = _StreamingRenderer()

    def fake_run_stage(stage: Stage, *, on_chunk=None, **_: object) -> StageResult:
        assert on_chunk is not None, "streaming renderer must produce a chunk callback"
        on_chunk(b"live-bytes")
        return _result(stage)

    monkeypatch.setattr(orchestrator, "run_stage", fake_run_stage)

    orchestrator.run_plan(plan, renderer=renderer, artifacts_root=tmp_path, persist=False)

    chunks = [e for e in renderer.events if isinstance(e, StageOutputChunk)]
    assert chunks == [StageOutputChunk(stage_name="stream-stage", chunk=b"live-bytes")]


def test_buffered_renderer_gets_no_chunk_callback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan = _plan("buffered-stage")
    seen_callbacks: list[object] = []

    def fake_run_stage(stage: Stage, *, on_chunk=None, **_: object) -> StageResult:
        seen_callbacks.append(on_chunk)
        return _result(stage)

    monkeypatch.setattr(orchestrator, "run_stage", fake_run_stage)

    orchestrator.run_plan(
        plan, renderer=_RecordingRenderer(), artifacts_root=tmp_path, persist=False
    )

    assert seen_callbacks == [None]


def test_internal_failure_yields_exit_code_4(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # EC-04: an exception escaping the executor is converted into a synthetic
    # rc=4 stage result with internal_failure=True, classifying as 4.
    plan = _plan("kaboom")

    def exploding_run_stage(stage: Stage, **_: object) -> StageResult:
        raise RuntimeError("adapter blew up")

    monkeypatch.setattr(orchestrator, "run_stage", exploding_run_stage)
    renderer = _RecordingRenderer()

    result = orchestrator.run_plan(plan, renderer=renderer, artifacts_root=tmp_path, persist=False)

    assert result.exit_code is EngineExitCode.INTERNAL_ERROR
    assert result.stages[0].returncode == 4
    assert result.stages[0].internal_failure is True
    assert "adapter blew up" in (result.stages[0].error or "")

    finished = [e for e in read_artifact_events(tmp_path, plan.name) if e["event"] == "stage_finished"][0]
    assert finished["internal_failure"] is True
    plan_finished = read_artifact_events(tmp_path, plan.name)[-1]
    assert plan_finished["exit_code"] == 4


def test_persist_true_hands_result_to_composite_backend(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan = _plan("persisted")
    _stub_executor(monkeypatch, _result)
    persisted: list[PlanResult] = []

    class _Backend:
        def persist(self, result: PlanResult) -> None:
            persisted.append(result)

    monkeypatch.setattr(
        testo_core.persistence, "composite_backend", lambda *, artifacts_root: _Backend()
    )

    result = orchestrator.run_plan(
        plan, renderer=_RecordingRenderer(), artifacts_root=tmp_path, persist=True
    )

    assert persisted == [result]


def test_persist_false_writes_no_plan_result_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan = _plan("unpersisted")
    _stub_executor(monkeypatch, _result)

    orchestrator.run_plan(plan, renderer=_RecordingRenderer(), artifacts_root=tmp_path, persist=False)

    assert not (tmp_path / plan.name / "plan_result.json").exists()


def test_json_backend_writes_plan_result_schema(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # LC: plan_result.json is the durable summary next to events.ndjson.
    plan = _plan("json-plan", plan_name="json-plan-cycle")
    _stub_executor(monkeypatch, lambda stage: _result(stage, returncode=1))

    result = orchestrator.run_plan(
        plan, renderer=_RecordingRenderer(), artifacts_root=tmp_path, persist=False
    )
    JsonBackend(tmp_path).persist(result)

    payload = json.loads((tmp_path / plan.name / "plan_result.json").read_text(encoding="utf-8"))
    assert payload["plan"] == plan.name
    assert payload["exit_code"] == 1
    assert payload["aggregate_returncode"] == 1
    assert payload["stages"][0]["name"] == "json-plan"
    assert payload["stages"][0]["returncode"] == 1
    assert set(payload["stages"][0]) >= {"framework", "duration_s", "log_path", "timed_out", "error"}
