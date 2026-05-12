"""Pure subprocess wrapper used by :mod:`testo_core.engine.orchestrator`.

Responsibilities:

* Resolve the per-stage artifacts layout (``<artifacts>/<plan>/<stage>/``).
* Ask the framework adapter for the argv to launch.
* Spawn the subprocess with stderr merged into stdout for deterministic
  ordering, and tee everything through :class:`LogBuffer`.
* Enforce ``timeout_s`` by sending SIGTERM, then SIGKILL after a short grace.
* Return a :class:`StageResult` describing the outcome.

No Docker, no SSH, no DB.  Future backends (Docker, remote runner) will live
under ``testo_core/engine/backends/`` and adapt to the same return type.
"""

from __future__ import annotations

import os
import shutil
import signal
import subprocess
import sys
import threading
import time
from collections.abc import Mapping
from pathlib import Path
from typing import Callable

from testo_core.config.schema import Stage
from testo_core.engine.log_buffer import LogBuffer, drain_stream_into_buffer, merged_env
from testo_core.engine.result import StageResult
from testo_core.frameworks.base import FrameworkAdapter, get_adapter


_TERMINATE_GRACE_S: float = 5.0
_DEFAULT_TAIL_LINES: int = 200


def run_stage(
    stage: Stage,
    *,
    plan_name: str,
    artifacts_root: Path,
    parent_env: Mapping[str, str] | None = None,
    on_chunk: Callable[[bytes], None] | None = None,
    tail_lines: int = _DEFAULT_TAIL_LINES,
) -> StageResult:
    """Execute one stage and return a :class:`StageResult`."""
    adapter: FrameworkAdapter = get_adapter(stage.framework)
    stage_root = (artifacts_root / plan_name / stage.name).expanduser().resolve()
    results_dir = (stage_root / "allure-results" / adapter.results_subdir()).resolve()
    stage_root.mkdir(parents=True, exist_ok=True)
    if results_dir.exists():
        shutil.rmtree(results_dir)
    results_dir.mkdir(parents=True, exist_ok=True)
    log_path = (stage_root / "run.log").resolve()

    argv = adapter.build_argv(
        target_repo=stage.target_repo,
        results_dir=results_dir,
        stage_args=stage.args,
        workers=stage.workers,
    )

    env = merged_env(parent_env if parent_env is not None else os.environ, stage.extra_env)
    env.setdefault("UQO_LAST_TEST_TYPE", stage.framework)
    env.setdefault("UQO_ARTIFACTS_ROOT", str(artifacts_root.expanduser().resolve()))
    env["UQO_SHARED_ALLURE_RESULTS_DIR"] = str(results_dir)

    started_at = time.time()
    returncode: int
    timed_out = False
    error: str | None = None

    with LogBuffer(log_path=log_path, on_chunk=on_chunk) as buffer:
        try:
            proc = subprocess.Popen(  # noqa: S603 - argv is built by trusted adapters
                argv,
                cwd=str(stage.target_repo.expanduser().resolve()),
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                bufsize=0,
                close_fds=True,
            )
        except FileNotFoundError as exc:
            error = f"executable not found: {exc.filename or argv[0]}"
            finished_at = time.time()
            return _failure_result(
                stage=stage,
                started_at=started_at,
                finished_at=finished_at,
                error=error,
                log_path=log_path,
                results_dir=results_dir,
                argv=argv,
                buffer=buffer,
                tail_lines=tail_lines,
                returncode=127,
            )

        assert proc.stdout is not None  # noqa: S101 — we asked for a pipe
        reader = threading.Thread(
            target=drain_stream_into_buffer,
            args=(proc.stdout, buffer),
            name=f"testo-log-reader-{stage.name}",
            daemon=True,
        )
        reader.start()

        try:
            returncode = proc.wait(timeout=stage.timeout_s)
        except subprocess.TimeoutExpired:
            timed_out = True
            error = f"stage exceeded timeout_s={stage.timeout_s}"
            returncode = _terminate(proc)

        reader.join(timeout=2.0)
        finished_at = time.time()
        output_tail = buffer.tail(max_lines=tail_lines)

    if stage.framework == "behavex":
        try:
            from testo_core.reporting.native_reports import ensure_behavex_report_html

            ensure_behavex_report_html(stage_root)
        except Exception:
            pass

    duration = max(0.0, finished_at - started_at)
    return StageResult(
        stage_name=stage.name,
        framework=stage.framework,
        returncode=int(returncode),
        started_at=started_at,
        finished_at=finished_at,
        duration_s=duration,
        log_path=log_path,
        artifacts_dir=stage_root,
        command=tuple(argv),
        output_tail=output_tail,
        timed_out=timed_out,
        error=error,
    )


def _terminate(proc: subprocess.Popen[bytes]) -> int:
    """Try SIGTERM, then SIGKILL.  Returns the final returncode."""
    try:
        if sys.platform == "win32":
            proc.terminate()
        else:
            proc.send_signal(signal.SIGTERM)
        try:
            return proc.wait(timeout=_TERMINATE_GRACE_S)
        except subprocess.TimeoutExpired:
            proc.kill()
            return proc.wait()
    except (ProcessLookupError, OSError):
        return -1


def _failure_result(
    *,
    stage: Stage,
    started_at: float,
    finished_at: float,
    error: str,
    log_path: Path,
    results_dir: Path,
    argv: list[str],
    buffer: LogBuffer,
    tail_lines: int,
    returncode: int,
) -> StageResult:
    return StageResult(
        stage_name=stage.name,
        framework=stage.framework,
        returncode=int(returncode),
        started_at=started_at,
        finished_at=finished_at,
        duration_s=max(0.0, finished_at - started_at),
        log_path=log_path,
        artifacts_dir=results_dir.parent,
        command=tuple(argv),
        output_tail=buffer.tail(max_lines=tail_lines),
        timed_out=False,
        error=error,
    )
