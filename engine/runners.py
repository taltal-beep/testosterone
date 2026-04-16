from __future__ import annotations

import os
import queue
import subprocess
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Generator, Mapping, Optional

from .command_builders import BuiltCommand, RunConfig, build_command
from .result_management import prepare_allure_results_dir


@dataclass(frozen=True)
class LogEvent:
    ts: float
    stream: str  # "stdout" | "stderr" | "meta"
    line: str


@dataclass(frozen=True)
class RunResult:
    returncode: int
    started_at: float
    finished_at: float
    command: BuiltCommand


def run_streaming(
    cfg: RunConfig,
    *,
    parent_env: Optional[Mapping[str, str]] = None,
    artifacts_root: Path | None = None,
) -> Generator[LogEvent, None, RunResult]:
    """
    Execute a test runner subprocess and stream logs as LogEvent objects.

    This is designed to be consumed by a UI loop that polls the generator.
    It uses background reader threads + a Queue so the UI doesn't freeze.
    """
    started_at = time.time()

    run_id = str(uuid.uuid4())
    artifacts_root = (artifacts_root or Path("artifacts")).expanduser().resolve()
    shared_allure_dir = (artifacts_root / "allure-results").resolve()
    prepared = prepare_allure_results_dir(shared_allure_dir, mode="archive", run_id=run_id)
    shared_allure_dir = prepared.shared_dir

    merged_extra = dict(cfg.extra_env or {})
    merged_extra.setdefault("UQO_RUN_ID", run_id)

    cfg = RunConfig(
        test_type=cfg.test_type,
        target_repo=cfg.target_repo,
        shared_allure_results_dir=shared_allure_dir,
        pytest_args=cfg.pytest_args,
        behavex_args=cfg.behavex_args,
        locust_args=cfg.locust_args,
        locustfile=cfg.locustfile,
        extra_env=merged_extra,
        run_id=run_id,
    )

    cmd = build_command(cfg, parent_env=parent_env or os.environ)

    # Injection logic (zero-touch)
    orchestrator_root = Path(__file__).resolve().parents[1]
    drop_in_root = orchestrator_root / "drop_in_hooks"

    # Ensure subprocess can import drop-in modules regardless of cwd.
    pythonpath_parts = []
    existing_pp = cmd.env.get("PYTHONPATH")
    pythonpath_parts.append(str(orchestrator_root))
    pythonpath_parts.append(str(drop_in_root))
    if existing_pp:
        pythonpath_parts.append(existing_pp)
    cmd.env["PYTHONPATH"] = os.pathsep.join(pythonpath_parts)

    # Pytest: load plugin module even if target repo doesn't include it.
    if cfg.test_type.value == "pytest":
        existing = cmd.env.get("PYTEST_ADDOPTS", "")
        injection = "-p drop_in_hooks.pytest.conftest"
        if injection not in existing:
            cmd.env["PYTEST_ADDOPTS"] = (existing + " " + injection).strip()

    q: queue.Queue[LogEvent | None] = queue.Queue()

    def emit(stream: str, line: str) -> None:
        q.put(LogEvent(ts=time.time(), stream=stream, line=line))

    emit("meta", f"$ UQO_RUN_ID={run_id}\n")
    emit("meta", f"$ (cwd={cmd.cwd}) {' '.join(cmd.argv)}\n")

    proc = subprocess.Popen(
        cmd.argv,
        cwd=str(cmd.cwd),
        env=cmd.env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,  # line-buffered (best-effort)
        universal_newlines=True,
    )

    def reader_thread(stream_name: str, fh) -> None:
        try:
            for line in iter(fh.readline, ""):
                emit(stream_name, line)
        finally:
            try:
                fh.close()
            except Exception:
                pass

    t_out = threading.Thread(target=reader_thread, args=("stdout", proc.stdout), daemon=True)
    t_err = threading.Thread(target=reader_thread, args=("stderr", proc.stderr), daemon=True)
    t_out.start()
    t_err.start()

    # Loop until process ends and both reader threads drained.
    while True:
        try:
            item = q.get(timeout=0.1)
            if item is not None:
                yield item
        except queue.Empty:
            pass

        rc = proc.poll()
        if rc is not None:
            # Drain remaining lines for a short window.
            drain_deadline = time.time() + 2.0
            while time.time() < drain_deadline:
                try:
                    item = q.get_nowait()
                    if item is not None:
                        yield item
                except queue.Empty:
                    break

            # Ensure threads get a chance to exit.
            t_out.join(timeout=1.0)
            t_err.join(timeout=1.0)
            finished_at = time.time()
            yield LogEvent(ts=finished_at, stream="meta", line=f"\n[exit code {rc}]\n")
            return RunResult(
                returncode=int(rc),
                started_at=started_at,
                finished_at=finished_at,
                command=cmd,
            )


def validate_target_repo(path: Path) -> tuple[bool, str]:
    p = path.expanduser()
    if not p.exists():
        return False, "Path does not exist."
    if not p.is_dir():
        return False, "Path is not a directory."
    return True, "OK"


def default_artifacts_root() -> Path:
    return Path("artifacts")

