from __future__ import annotations

import time
import uuid
from pathlib import Path

from uqo_core.command_builders import BuiltCommand, TestType
from uqo_core.run_history import RunSyncStatus, SyncOperationStatus
from uqo_core.runners import LogEvent, RunResult
from uqo_core.services.ci_provenance import CIProvenance
from uqo_core.services.headless_engine import (
    EngineExitCode,
    EngineRequest,
    EngineRunSpec,
    HeadlessEngineService,
)


def _drain_summary(gen):  # noqa: ANN001
    try:
        while True:
            next(gen)
    except StopIteration as stop:
        return stop.value


def _fake_streaming_success(cfg, **kwargs):  # noqa: ANN001
    del kwargs
    yield LogEvent(ts=time.time(), stream="stdout", line="ok\n")
    cmd = BuiltCommand(
        argv=["pytest", "-q"],
        cwd=cfg.target_repo,
        env={
            "UQO_RUN_ID": str(cfg.run_id or "rid-1"),
            "UQO_LAST_TEST_TYPE": cfg.test_type.value,
            "UQO_ARTIFACTS_ROOT": str((cfg.artifacts_root or Path("artifacts")).resolve()),
        },
    )
    return RunResult(
        returncode=0,
        started_at=time.time() - 1,
        finished_at=time.time(),
        command=cmd,
    )


def test_engine_persists_metadata_context(monkeypatch, tmp_path: Path) -> None:  # noqa: ANN001
    captured_start_md: list[dict] = []
    captured_complete_md: list[dict] = []

    def fake_create_run(*, status, metadata):  # noqa: ANN001
        del status
        captured_start_md.append(dict(metadata))
        return uuid.uuid4()

    def fake_record_completed_run(*, rr, artifacts_root, test_kind, metadata_context, audit_health_pct=None, db_path=None):  # noqa: ANN001
        del rr, artifacts_root, test_kind, audit_health_pct, db_path
        captured_complete_md.append(dict(metadata_context or {}))
        return RunSyncStatus(
            run_id="rid-1",
            db_finalize=SyncOperationStatus(status="success", attempts=1),
            artifact_upload=SyncOperationStatus(status="success", attempts=1),
        )

    monkeypatch.setattr("uqo_core.services.headless_engine.create_run", fake_create_run)
    monkeypatch.setattr("uqo_core.services.headless_engine.record_completed_run", fake_record_completed_run)

    target = tmp_path / "repo"
    target.mkdir()
    spec = EngineRunSpec(test_type=TestType.PYTEST, target_repo=target, cli_args=("-q",))
    request = EngineRequest(
        runs=(spec,),
        trigger_source="ci",
        ci_mode=True,
        persist=True,
        provenance=CIProvenance(ci_provider="github", ci_pipeline_id="1001"),
    )
    engine = HeadlessEngineService(run_streaming_fn=_fake_streaming_success)

    summary = _drain_summary(engine.stream(request))

    assert summary is not None
    assert summary.exit_code == int(EngineExitCode.SUCCESS)
    assert captured_start_md[0]["trigger_source"] == "ci"
    assert captured_start_md[0]["ci_mode"] is True
    assert captured_start_md[0]["execution_mode"] == "ghost"
    assert captured_complete_md[0]["schema_version"] == "1"
    assert captured_start_md[0]["ci_provider"] == "github"
    assert captured_complete_md[0]["ci_pipeline_id"] == "1001"
    assert summary.sync is not None
    assert summary.sync["status"] == "success"


def test_engine_maps_runtime_failure_to_infra_exit_code(tmp_path: Path) -> None:
    def fake_streaming_fail(cfg, **kwargs):  # noqa: ANN001
        del cfg, kwargs
        raise RuntimeError("docker unavailable")
        yield  # pragma: no cover

    target = tmp_path / "repo"
    target.mkdir()
    request = EngineRequest(
        runs=(EngineRunSpec(test_type=TestType.PYTEST, target_repo=target),),
        trigger_source="cli",
        persist=False,
    )
    engine = HeadlessEngineService(run_streaming_fn=fake_streaming_fail)

    summary = _drain_summary(engine.stream(request))

    assert summary.exit_code == int(EngineExitCode.INFRA_FAILURE)
    assert summary.error is not None


def test_engine_maps_nonzero_run_to_domain_exit_code(tmp_path: Path) -> None:
    def fake_streaming_domain_fail(cfg, **kwargs):  # noqa: ANN001
        del kwargs
        yield LogEvent(ts=time.time(), stream="stdout", line="tests failed\n")
        cmd = BuiltCommand(
            argv=["pytest", "-q"],
            cwd=cfg.target_repo,
            env={"UQO_RUN_ID": "rid-fail", "UQO_LAST_TEST_TYPE": cfg.test_type.value},
        )
        return RunResult(
            returncode=5,
            started_at=time.time() - 1.0,
            finished_at=time.time(),
            command=cmd,
        )

    target = tmp_path / "repo"
    target.mkdir()
    request = EngineRequest(
        runs=(EngineRunSpec(test_type=TestType.PYTEST, target_repo=target),),
        trigger_source="cli",
        persist=False,
    )
    engine = HeadlessEngineService(run_streaming_fn=fake_streaming_domain_fail)
    summary = _drain_summary(engine.stream(request))

    assert summary.exit_code == int(EngineExitCode.DOMAIN_FAILURE)
    assert summary.aggregate_returncode == 1


def test_engine_maps_empty_results_to_internal_error(tmp_path: Path) -> None:
    def fake_streaming_no_result(cfg, **kwargs):  # noqa: ANN001
        del cfg, kwargs
        yield LogEvent(ts=time.time(), stream="stdout", line="no terminal result\n")
        return None

    target = tmp_path / "repo"
    target.mkdir()
    request = EngineRequest(
        runs=(EngineRunSpec(test_type=TestType.PYTEST, target_repo=target),),
        trigger_source="cli",
        persist=False,
    )
    engine = HeadlessEngineService(run_streaming_fn=fake_streaming_no_result)
    summary = _drain_summary(engine.stream(request))

    assert summary.exit_code == int(EngineExitCode.INTERNAL_ERROR)
    assert summary.aggregate_returncode == 1


def test_engine_sync_failure_maps_successful_tests_to_infra_exit(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    def fake_sync_fail(*, rr, artifacts_root, test_kind, metadata_context, audit_health_pct=None, db_path=None):  # noqa: ANN001
        del rr, artifacts_root, test_kind, metadata_context, audit_health_pct, db_path
        return RunSyncStatus(
            run_id="rid-sync",
            db_finalize=SyncOperationStatus(status="success", attempts=1),
            artifact_upload=SyncOperationStatus(status="failed", attempts=3, error="minio timeout"),
        )

    monkeypatch.setattr("uqo_core.services.headless_engine.record_completed_run", fake_sync_fail)
    target = tmp_path / "repo"
    target.mkdir()
    request = EngineRequest(
        runs=(EngineRunSpec(test_type=TestType.PYTEST, target_repo=target),),
        trigger_source="ci",
        ci_mode=True,
        persist=True,
    )
    engine = HeadlessEngineService(run_streaming_fn=_fake_streaming_success)
    summary = _drain_summary(engine.stream(request))

    assert summary.exit_code == int(EngineExitCode.INFRA_FAILURE)
    assert summary.failure_type == "sync_failure"
    assert summary.sync is not None
    assert summary.sync["status"] == "partial_failure"


def test_engine_finalizes_each_persisted_run_exactly_once(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    completed_run_ids: list[str] = []

    def fake_record_completed_run(*, rr, artifacts_root, test_kind, metadata_context, audit_health_pct=None, db_path=None):  # noqa: ANN001
        del artifacts_root, test_kind, metadata_context, audit_health_pct, db_path
        completed_run_ids.append(str(rr.command.env.get("UQO_RUN_ID") or ""))
        return RunSyncStatus(
            run_id=str(rr.command.env.get("UQO_RUN_ID") or "unknown"),
            db_finalize=SyncOperationStatus(status="success", attempts=1),
            artifact_upload=SyncOperationStatus(status="success", attempts=1),
        )

    monkeypatch.setattr("uqo_core.services.headless_engine.record_completed_run", fake_record_completed_run)
    target = tmp_path / "repo"
    target.mkdir()
    request = EngineRequest(
        runs=(
            EngineRunSpec(test_type=TestType.PYTEST, target_repo=target),
            EngineRunSpec(test_type=TestType.PYTEST, target_repo=target),
        ),
        trigger_source="ui",
        persist=True,
    )
    engine = HeadlessEngineService(run_streaming_fn=_fake_streaming_success)
    summary = _drain_summary(engine.stream(request))

    assert summary is not None
    assert len(summary.runs) == 2
    assert len(completed_run_ids) == 2
    assert all(run_id for run_id in completed_run_ids)
