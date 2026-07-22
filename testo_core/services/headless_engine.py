from __future__ import annotations

import time
from collections.abc import Callable, Generator, Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from testo_core.command_builders import RunConfig, TestType
from testo_core.engine.exit_codes import EngineExitCode, classify_exit_code
from testo_core.repository.models import RunStatus
from testo_core.run_history import (
    RunSyncStatus,
    create_run,
    record_completed_run,
    update_run_status,
)
from testo_core.runners import LogEvent, RunResult, run_streaming
from testo_core.services.ci_provenance import CIProvenance
from testo_core.services.multi_run import stream_multi_run

SCHEMA_VERSION = "1"
TriggerSource = Literal["cli", "ui", "ci"]


class HeadlessEngineError(Exception):
    exit_code: EngineExitCode = EngineExitCode.INTERNAL_ERROR

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.details = details or {}


class ConfigValidationError(HeadlessEngineError):
    exit_code = EngineExitCode.INVALID_INPUT


class InfrastructureRuntimeError(HeadlessEngineError):
    exit_code = EngineExitCode.INFRA_FAILURE


@dataclass(frozen=True)
class EngineRunSpec:
    test_type: TestType
    target_repo: Path
    cli_args: tuple[str, ...] = ()
    shared_allure_results_dir: Path | None = None
    artifacts_root: Path | None = None
    timeout_s: float | None = None
    extra_env: dict[str, str] | None = None


@dataclass(frozen=True)
class EngineRequest:
    runs: tuple[EngineRunSpec, ...]
    trigger_source: TriggerSource
    ci_mode: bool = False
    persist: bool = True
    provenance: CIProvenance | None = None


@dataclass(frozen=True)
class EngineEvent:
    kind: Literal["log", "run_result"]
    payload: LogEvent | RunResult


@dataclass(frozen=True)
class EngineRunRecord:
    test_type: str
    run_id: str | None
    returncode: int
    started_at: float
    finished_at: float
    duration_s: float
    cwd: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "test_type": self.test_type,
            "run_id": self.run_id,
            "returncode": self.returncode,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "duration_s": self.duration_s,
            "cwd": self.cwd,
        }


@dataclass(frozen=True)
class EngineSummary:
    schema_version: str
    trigger_source: TriggerSource
    ci_mode: bool
    persist: bool
    exit_code: int
    aggregate_returncode: int
    started_at: float
    finished_at: float
    runs: tuple[EngineRunRecord, ...]
    error: str | None = None
    execution_mode: str = "headless"
    failure_type: str | None = None
    sync: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "trigger_source": self.trigger_source,
            "ci_mode": self.ci_mode,
            "persist": self.persist,
            "exit_code": self.exit_code,
            "aggregate_returncode": self.aggregate_returncode,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "duration_s": max(0.0, self.finished_at - self.started_at),
            "runs": [run.to_dict() for run in self.runs],
            "error": self.error,
            "execution_mode": self.execution_mode,
            "failure_type": self.failure_type,
            "sync": self.sync,
        }


def _split_args_for_spec(spec: EngineRunSpec) -> tuple[Sequence[str], Sequence[str], Sequence[str]]:
    args = tuple(spec.cli_args)
    if spec.test_type == TestType.PYTEST:
        return args, (), ()
    if spec.test_type == TestType.BEHAVEX:
        return (), args, ()
    if spec.test_type == TestType.BEHAVE_NATIVE:
        return (), (), args
    raise ConfigValidationError(f"Unsupported test_type: {spec.test_type}")


def _build_run_config(spec: EngineRunSpec, *, db_run_id: str | None) -> RunConfig:
    pytest_args, behavex_args, behave_native_args = _split_args_for_spec(spec)
    shared_dir = spec.shared_allure_results_dir or Path(f"artifacts/allure-results/{spec.test_type.value}")
    artifacts_root = spec.artifacts_root or Path("artifacts")
    extra_env = dict(spec.extra_env or {})
    extra_env.setdefault("UQO_ARTIFACTS_ROOT", str(Path(artifacts_root).expanduser().resolve()))
    return RunConfig(
        test_type=spec.test_type,
        target_repo=spec.target_repo,
        shared_allure_results_dir=shared_dir,
        artifacts_root=artifacts_root,
        pytest_args=pytest_args,
        behavex_args=behavex_args,
        behave_native_args=behave_native_args,
        last_test_type=spec.test_type.value,
        run_id=db_run_id,
        timeout_s=spec.timeout_s,
        extra_env=extra_env,
    )


class HeadlessEngineService:
    def __init__(
        self,
        *,
        run_streaming_fn: Callable[..., Iterable[LogEvent]] = run_streaming,
        stream_multi_run_fn: Callable[..., Iterable[LogEvent | RunResult]] = stream_multi_run,
    ) -> None:
        self._run_streaming_fn = run_streaming_fn
        self._stream_multi_run_fn = stream_multi_run_fn

    def stream(self, request: EngineRequest) -> Generator[EngineEvent, None, EngineSummary]:
        if not request.runs:
            raise ConfigValidationError("At least one run is required.")

        started_at = time.time()
        db_run_ids: list[str | None] = []
        run_configs: list[RunConfig] = []
        infra_error: Exception | None = None
        results: list[RunResult] = []
        sync_results: list[RunSyncStatus] = []

        metadata_context = {
            "trigger_source": request.trigger_source,
            "ci_mode": bool(request.ci_mode),
            "execution_mode": "ghost" if bool(request.ci_mode) else "headless",
            "schema_version": SCHEMA_VERSION,
        }
        if request.provenance is not None:
            metadata_context.update(request.provenance.to_metadata())

        for spec in request.runs:
            db_run_id: str | None = None
            if request.persist:
                try:
                    db_run_uuid = create_run(
                        status=RunStatus.RUNNING,
                        metadata={
                            "test_kind": spec.test_type.value,
                            **metadata_context,
                        },
                    )
                    db_run_id = str(db_run_uuid)
                except Exception as exc:
                    raise InfrastructureRuntimeError("Failed to persist run start.", details={"reason": str(exc)}) from exc
            db_run_ids.append(db_run_id)
            run_configs.append(_build_run_config(spec, db_run_id=db_run_id))

        try:
            if len(run_configs) == 1:
                gen = iter(
                    self._run_streaming_fn(
                        run_configs[0],
                        artifacts_root=Path(run_configs[0].artifacts_root or Path("artifacts")),
                    )
                )
                while True:
                    try:
                        item = next(gen)
                        yield EngineEvent(kind="log", payload=item)
                    except StopIteration as stop:
                        if stop.value is not None:
                            results.append(stop.value)
                            yield EngineEvent(kind="run_result", payload=stop.value)
                        break
            else:
                for item in self._stream_multi_run_fn(
                    run_configs,
                    artifacts_root=Path(run_configs[0].artifacts_root or Path("artifacts")),
                    db_run_ids=db_run_ids,
                    run_streaming_fn=self._run_streaming_fn,
                    update_run_status_fn=update_run_status,
                    failed_status=RunStatus.FAILED,
                ):
                    if isinstance(item, RunResult):
                        results.append(item)
                        yield EngineEvent(kind="run_result", payload=item)
                    else:
                        yield EngineEvent(kind="log", payload=item)
        except Exception as exc:
            infra_error = exc
            for db_run_id in db_run_ids:
                if request.persist and db_run_id:
                    try:
                        update_run_status(
                            db_run_id,
                            status=RunStatus.FAILED,
                            metadata={
                                "error": str(exc),
                                **metadata_context,
                            },
                        )
                    except Exception:
                        pass

        run_records: list[EngineRunRecord] = []
        for idx, rr in enumerate(results):
            run_id = rr.command.env.get("UQO_AUDIT_RUN_ID") or rr.command.env.get("UQO_RUN_ID")
            run_records.append(
                EngineRunRecord(
                    test_type=str(rr.command.env.get("UQO_LAST_TEST_TYPE") or request.runs[idx].test_type.value),
                    run_id=run_id,
                    returncode=int(rr.returncode),
                    started_at=float(rr.started_at),
                    finished_at=float(rr.finished_at),
                    duration_s=max(0.0, float(rr.finished_at - rr.started_at)),
                    cwd=str(rr.command.cwd),
                )
            )
            if request.persist:
                try:
                    sync_result = record_completed_run(
                        rr=rr,
                        artifacts_root=Path(rr.command.env.get("UQO_ARTIFACTS_ROOT") or run_configs[idx].artifacts_root or "artifacts"),
                        test_kind=str(rr.command.env.get("UQO_LAST_TEST_TYPE") or request.runs[idx].test_type.value),
                        metadata_context=metadata_context,
                    )
                    if sync_result is not None:
                        sync_results.append(sync_result)
                except Exception as exc:
                    infra_error = infra_error or exc

        finished_at = time.time()
        returncodes = [int(r.returncode) for r in results]
        has_test_failure = any(rc != 0 for rc in returncodes)
        has_sync_failure = any(
            sr.db_finalize.status != "success" or sr.artifact_upload.status == "failed"
            for sr in sync_results
        )
        exit_code = classify_exit_code(returncodes, infra_error=infra_error)
        if infra_error is None and has_sync_failure:
            exit_code = EngineExitCode.INFRA_FAILURE
        aggregate_returncode = 0 if returncodes and all(rc == 0 for rc in returncodes) else 1
        if not returncodes and infra_error is not None:
            aggregate_returncode = 1

        failure_type: str | None = None
        if infra_error is not None:
            failure_type = "infra_failure"
        elif has_test_failure:
            failure_type = "test_failure"
        elif has_sync_failure:
            failure_type = "sync_failure"

        sync_status = "not_requested"
        if request.persist:
            if not sync_results:
                sync_status = "skipped"
            elif has_sync_failure:
                sync_status = "partial_failure"
            else:
                sync_status = "success"

        summary = EngineSummary(
            schema_version=SCHEMA_VERSION,
            trigger_source=request.trigger_source,
            ci_mode=bool(request.ci_mode),
            persist=bool(request.persist),
            exit_code=int(exit_code),
            aggregate_returncode=int(aggregate_returncode),
            started_at=started_at,
            finished_at=finished_at,
            runs=tuple(run_records),
            error=str(infra_error) if infra_error else None,
            execution_mode="ghost" if bool(request.ci_mode) else "headless",
            failure_type=failure_type,
            sync={
                "status": sync_status,
                "runs": [sr.to_dict() for sr in sync_results],
            },
        )
        return summary
