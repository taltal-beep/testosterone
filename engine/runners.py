from __future__ import annotations

import contextlib
import os
import queue
import shutil
import subprocess
import sys
import threading
import time
import uuid
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Generator, Mapping, Optional, Sequence

from .command_builders import BuiltCommand, RunConfig, TestType, build_command
from .paths import default_artifacts_root
from .metrics_extractor import write_manual_locust_results_json
from .report_generator import (
    collect_behavex_native_report,
    default_report_paths,
    generate_allure_html,
    publish_locust_html_to_static,
    sync_all_reports_to_static,
)
from .result_management import prepare_allure_results_dir

# Emitted immediately before returning ``RunResult`` so the UI can stop polling
# even if the ``RunResult`` object is delayed or dropped.
UQO_DONE_MARKER = "[UQO_DONE]"
UQO_AUDIT_PHASE = "[UQO_AUDIT_PHASE]"
UQO_AUDIT_HEALTH = "[UQO_AUDIT_HEALTH]"


def _resolve_subprocess_argv(argv: list[str]) -> None:
    """Ensure the spawned executable is findable when PATH is incomplete (e.g. Streamlit worker)."""
    if not argv:
        return
    base_cmd = argv[0]
    # Leave explicit relative/absolute paths to the OS / subprocess cwd resolution.
    if os.path.dirname(base_cmd):
        return
    resolved_cmd = shutil.which(base_cmd)
    if resolved_cmd:
        argv[0] = resolved_cmd
    else:
        argv[:] = [sys.executable, "-m", base_cmd] + argv[1:]


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
    audit_mode: bool = False
    audit_partial_success: bool = False
    audit_phase_returncodes: tuple[int, ...] = ()
    audit_health_pct: float | None = None


def run_streaming(
    cfg: RunConfig,
    *,
    parent_env: Optional[Mapping[str, str]] = None,
    artifacts_root: Path | None = None,
    prepare_allure: bool = True,
    emit_done_marker: bool = True,
    sync_static: bool = True,
    run_framework_hooks: bool = True,
) -> Generator[LogEvent, None, RunResult]:
    """
    Run a test subprocess and yield log lines in real time.

    Uses ``subprocess.Popen`` with line-buffered text mode, merges stderr into stdout
    (single stream) so interleaved output is readable, and reads via a background thread
    into a queue so the generator can still apply heartbeat/timeout logic without
    blocking the Streamlit main thread (when consumed from a worker thread).

    For multi-phase audit runs, set ``prepare_allure=False`` (shared dir pre-cleared),
    ``emit_done_marker=False``, ``sync_static=False``, and ``run_framework_hooks=False``;
    the audit orchestrator emits ``[UQO_DONE]`` once after the final sync.
    """
    started_at = time.time()

    run_id = str(cfg.run_id) if cfg.run_id is not None else str(uuid.uuid4())
    artifacts_root = (artifacts_root or Path("artifacts")).expanduser().resolve()
    if prepare_allure:
        shared_allure_dir = (artifacts_root / "allure-results").resolve()
        prepared = prepare_allure_results_dir(shared_allure_dir, mode="archive", run_id=run_id)
        shared_allure_dir = prepared.shared_dir
    else:
        shared_allure_dir = cfg.shared_allure_results_dir.expanduser().resolve()
        shared_allure_dir.mkdir(parents=True, exist_ok=True)

    merged_extra = dict(cfg.extra_env or {})
    merged_extra.setdefault("UQO_RUN_ID", run_id)

    cfg = replace(
        cfg,
        shared_allure_results_dir=shared_allure_dir,
        artifacts_root=artifacts_root,
        extra_env=merged_extra,
        run_id=run_id,
    )

    cmd = build_command(cfg, parent_env=parent_env or os.environ)

    orchestrator_root = Path(__file__).resolve().parents[1]
    drop_in_root = orchestrator_root / "drop_in_hooks"

    pythonpath_parts = [str(orchestrator_root), str(drop_in_root)]
    existing_pp = cmd.env.get("PYTHONPATH")
    if existing_pp:
        pythonpath_parts.append(existing_pp)
    cmd.env["PYTHONPATH"] = os.pathsep.join(pythonpath_parts)

    if cfg.test_type.value == "behavex":
        site_packages = _current_site_packages()
        if site_packages:
            cmd.env["PYTHONPATH"] = os.pathsep.join([site_packages, cmd.env.get("PYTHONPATH", "")]).strip(os.pathsep)

    if cfg.test_type.value == "pytest":
        existing = cmd.env.get("PYTEST_ADDOPTS", "")
        injection = "-p drop_in_hooks.pytest_custom.conftest"
        if injection not in existing:
            cmd.env["PYTEST_ADDOPTS"] = (existing + " " + injection).strip()
        opts = cmd.env.get("PYTEST_ADDOPTS", "")
        padded = f" {opts} "
        extra = []
        if " -s " not in padded and "--capture=no" not in opts:
            extra.append("-s")
        if "--color=yes" not in opts and "--color=no" not in opts:
            extra.append("--color=yes")
        if extra:
            cmd.env["PYTEST_ADDOPTS"] = (opts + " " + " ".join(extra)).strip()

    cmd.env["PYTHONUNBUFFERED"] = "1"

    q: queue.Queue[LogEvent | None] = queue.Queue()

    def emit(stream: str, line: str) -> None:
        q.put(LogEvent(ts=time.time(), stream=stream, line=line))

    emit("meta", f"$ UQO_RUN_ID={run_id}\n")
    _resolve_subprocess_argv(cmd.argv)
    emit("meta", f"$ (cwd={cmd.cwd}) {' '.join(cmd.argv)}\n")

    proc = subprocess.Popen(
        cmd.argv,
        cwd=str(cmd.cwd),
        env=cmd.env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    def reader_thread() -> None:
        fh = proc.stdout
        if fh is None:
            return
        try:
            for line in iter(fh.readline, ""):
                emit("stdout", line)
        finally:
            with contextlib.suppress(Exception):
                fh.close()

    t_out = threading.Thread(target=reader_thread, daemon=True)
    t_out.start()

    last_output_ts = time.time()

    while True:
        try:
            item = q.get(timeout=0.1)
            if item is not None:
                last_output_ts = time.time()
                yield item
        except queue.Empty:
            pass

        now = time.time()
        if float(cfg.heartbeat_s) > 0 and (now - last_output_ts) >= float(cfg.heartbeat_s):
            last_output_ts = now
            yield LogEvent(ts=now, stream="meta", line="[still running...]\n")

        if cfg.timeout_s is not None and (now - started_at) >= float(cfg.timeout_s):
            yield LogEvent(ts=now, stream="meta", line=f"[timeout after {cfg.timeout_s}s] terminating...\n")
            with contextlib.suppress(Exception):
                proc.terminate()
            try:
                proc.wait(timeout=5.0)
            except Exception:
                with contextlib.suppress(Exception):
                    proc.kill()
            with contextlib.suppress(Exception):
                proc.wait(timeout=30.0)
            rc = proc.poll()
            finished_at = time.time()
            yield LogEvent(ts=finished_at, stream="meta", line=f"\n[exit code {rc if rc is not None else 124}]\n")
            if emit_done_marker:
                yield LogEvent(
                    ts=time.time(),
                    stream="meta",
                    line=f"{UQO_DONE_MARKER} returncode={int(rc if rc is not None else 124)}\n",
                )
            if sync_static:
                yield LogEvent(
                    ts=time.time(),
                    stream="meta",
                    line="[report sync] copying artifacts into ./static/ …\n",
                )
                sync_all_reports_to_static(artifacts_root=artifacts_root, run_id=run_id)
            return RunResult(
                returncode=int(rc if rc is not None else 124),
                started_at=started_at,
                finished_at=finished_at,
                command=cmd,
            )

        rc = proc.poll()
        if rc is not None:
            drain_deadline = time.time() + 2.0
            while time.time() < drain_deadline:
                try:
                    item = q.get_nowait()
                    if item is not None:
                        yield item
                except queue.Empty:
                    break

            t_out.join(timeout=2.0)
            with contextlib.suppress(Exception):
                proc.wait(timeout=30.0)

            finished_at = time.time()
            yield LogEvent(ts=finished_at, stream="meta", line=f"\n[exit code {rc}]\n")
            if emit_done_marker:
                yield LogEvent(
                    ts=time.time(),
                    stream="meta",
                    line=f"{UQO_DONE_MARKER} returncode={int(rc)}\n",
                )

            if run_framework_hooks and cfg.test_type.value == "behavex":
                try:
                    dest = collect_behavex_native_report(
                        target_repo=cmd.cwd,
                        run_id=run_id,
                        artifacts_root=artifacts_root,
                    )
                    if dest:
                        yield LogEvent(ts=time.time(), stream="meta", line=f"[behavex native report] {dest}\n")
                except Exception:
                    pass

            if run_framework_hooks and cfg.test_type.value == "locust":
                try:
                    lp = publish_locust_html_to_static(artifacts_root=artifacts_root)
                    if lp:
                        yield LogEvent(ts=time.time(), stream="meta", line=f"[locust html mirror] {lp}\n")
                except Exception:
                    pass

            if sync_static:
                try:
                    yield LogEvent(
                        ts=time.time(),
                        stream="meta",
                        line="[report sync] copying artifacts into ./static/ …\n",
                    )
                    synced = sync_all_reports_to_static(artifacts_root=artifacts_root, run_id=run_id)
                    if any(synced.values()):
                        yield LogEvent(
                            ts=time.time(),
                            stream="meta",
                            line=f"[static sync] { {k: str(v) for k, v in synced.items() if v} }\n",
                        )
                except Exception:
                    pass

            return RunResult(
                returncode=int(rc),
                started_at=started_at,
                finished_at=finished_at,
                command=cmd,
            )


def run_audit_streaming(
    *,
    target_repo: Path,
    artifacts_root: Path | None = None,
    parent_env: Optional[Mapping[str, str]] = None,
    pytest_args: Sequence[str] = (),
    behavex_args: Sequence[str] = (),
    locust_args: Sequence[str] = (),
    locust_users: int = 10,
    locust_spawn_rate: int = 2,
    locust_run_time: str = "1m",
    locust_only_summary: bool = True,
) -> Generator[LogEvent, None, RunResult]:
    """
    Run Pytest → BehaveX → Locust into ``allure-results/{pytest,behave,locust}/`` (no overwrite),
    then build one master Allure HTML report from the parent ``allure-results/`` tree.
    Clears ``artifacts/allure-results/`` exactly once at audit start (no per-phase wipes).
    Emits a single ``[UQO_DONE]`` at the end.
    """
    audit_started = time.time()
    artifacts_root = (artifacts_root or Path("artifacts")).expanduser().resolve()
    shared_allure = (artifacts_root / "allure-results").resolve()
    audit_run_id = str(uuid.uuid4())

    if shared_allure.exists():
        shutil.rmtree(shared_allure, ignore_errors=True)
    shared_allure.mkdir(parents=True, exist_ok=True)
    yield LogEvent(
        ts=time.time(),
        stream="meta",
        line=f"[AUDIT] cleared unified allure-results root at {shared_allure}\n",
    )

    phases: list[tuple[TestType, str, str]] = [
        (TestType.PYTEST, "pytest", "API Tests"),
        (TestType.BEHAVEX, "behavex", "BDD Scenarios"),
        (TestType.LOCUST, "locust", "Load Tests"),
    ]

    phase_returncodes: list[int] = []
    last_cmd: BuiltCommand | None = None
    rr: RunResult | None = None

    for idx, (tt, key, title) in enumerate(phases, start=1):
        yield LogEvent(
            ts=time.time(),
            stream="meta",
            line=f"{UQO_AUDIT_PHASE} [{idx}/3] {key} — {title}\n",
        )
        extra = {"UQO_AUDIT_MODE": "1", "UQO_AUDIT_RUN_ID": audit_run_id}
        phase_allure = shared_allure / key
        cfg = RunConfig(
            test_type=tt,
            target_repo=target_repo,
            shared_allure_results_dir=phase_allure,
            artifacts_root=artifacts_root,
            pytest_args=tuple(pytest_args),
            behavex_args=tuple(behavex_args),
            locust_args=tuple(locust_args),
            locust_headless=True,
            locust_users=int(locust_users),
            locust_spawn_rate=int(locust_spawn_rate),
            locust_run_time=str(locust_run_time),
            locust_only_summary=bool(locust_only_summary),
            run_id=f"{audit_run_id}-{key}",
            last_test_type=key,
            extra_env=extra,
        )
        gen = run_streaming(
            cfg,
            parent_env=parent_env,
            artifacts_root=artifacts_root,
            prepare_allure=False,
            emit_done_marker=False,
            sync_static=False,
            run_framework_hooks=False,
        )
        try:
            while True:
                yield next(gen)
        except StopIteration as e:
            rr = e.value
            if rr is None:
                raise RuntimeError("audit phase returned no RunResult")
            phase_returncodes.append(int(rr.returncode))
            last_cmd = rr.command

        if key == "locust":
            try:
                write_manual_locust_results_json(
                    shared_allure / "locust",
                    audit_run_id=audit_run_id,
                    phase_returncodes=list(phase_returncodes),
                )
            except Exception:
                pass

        if rr is not None and rr.returncode != 0:
            yield LogEvent(
                ts=time.time(),
                stream="meta",
                line=f"[AUDIT] phase {key} exited {rr.returncode}; continuing with next phase…\n",
            )

    if last_cmd is None:
        raise RuntimeError("audit produced no phases")

    # Native mirrors + master Allure (unified results dir)
    try:
        collect_behavex_native_report(
            target_repo=target_repo,
            run_id=audit_run_id,
            artifacts_root=artifacts_root,
        )
    except Exception:
        pass
    try:
        publish_locust_html_to_static(artifacts_root=artifacts_root)
    except Exception:
        pass

    paths = default_report_paths(artifacts_root=artifacts_root)
    ok_gen, msg_gen, health_pct = generate_allure_html(
        results_dir=shared_allure,
        report_dir=paths.report_dir,
    )
    if ok_gen:
        yield LogEvent(ts=time.time(), stream="meta", line=f"[AUDIT] master Allure HTML: {msg_gen}\n")
    else:
        yield LogEvent(ts=time.time(), stream="meta", line=f"[AUDIT] Allure generate failed: {msg_gen}\n")

    if health_pct is not None:
        yield LogEvent(
            ts=time.time(),
            stream="meta",
            line=f"{UQO_AUDIT_HEALTH} {health_pct:.4f}\n",
        )

    yield LogEvent(ts=time.time(), stream="meta", line="[report sync] copying artifacts into ./static/ …\n")
    try:
        synced = sync_all_reports_to_static(artifacts_root=artifacts_root, run_id=audit_run_id)
        if any(synced.values()):
            yield LogEvent(
                ts=time.time(),
                stream="meta",
                line=f"[static sync] { {k: str(v) for k, v in synced.items() if v} }\n",
            )
    except Exception:
        pass

    all_zero = all(rc == 0 for rc in phase_returncodes)
    any_zero = any(rc == 0 for rc in phase_returncodes)
    any_nonzero = any(rc != 0 for rc in phase_returncodes)
    partial = bool(any_nonzero and any_zero)
    agg_rc = 0 if all_zero else 1

    yield LogEvent(
        ts=time.time(),
        stream="meta",
        line=f"{UQO_DONE_MARKER} returncode={agg_rc} audit_phases={phase_returncodes}\n",
    )

    audit_finished = time.time()
    return RunResult(
        returncode=agg_rc,
        started_at=audit_started,
        finished_at=audit_finished,
        command=last_cmd,
        audit_mode=True,
        audit_partial_success=partial,
        audit_phase_returncodes=tuple(phase_returncodes),
        audit_health_pct=health_pct,
    )


def _current_site_packages() -> str | None:
    try:
        import site

        for p in site.getsitepackages():
            if p and Path(p).name == "site-packages":
                return str(Path(p).resolve())
    except Exception:
        pass

    for p in sys.path:
        if not p:
            continue
        if "site-packages" in p:
            return str(Path(p).resolve())
    return None


def validate_target_repo(path: Path) -> tuple[bool, str]:
    p = path.expanduser()
    if not p.exists():
        return False, "Path does not exist."
    if not p.is_dir():
        return False, "Path is not a directory."
    return True, "OK"


def run_behave_native_streaming(
    *,
    target_repo: Path,
    artifacts_root: Path | None = None,
    parent_env: Optional[Mapping[str, str]] = None,
    behave_args: Sequence[str] = (),
) -> Generator[LogEvent, None, RunResult]:
    """
    Placeholder: run standard Behave (not BehaveX) with Allure formatter.

    Intended output directory:
      ``artifacts/allure-results/behave_native/``

    Example command shape (when implemented):
      behave -f allure_behave.formatter:AllureFormatter -o <allure_results_dir> ...
    """
    _ = behave_args
    started = time.time()
    artifacts_root = (artifacts_root or Path("artifacts")).expanduser().resolve()
    out_dir = (artifacts_root / "allure-results" / "behave_native").resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    yield LogEvent(
        ts=time.time(),
        stream="meta",
        line=f"[behave_native] not implemented yet; reserved results dir: {out_dir}\n",
    )
    finished = time.time()
    cmd = BuiltCommand(argv=["behave"], cwd=target_repo.expanduser().resolve(), env=dict(parent_env or os.environ))
    return RunResult(returncode=2, started_at=started, finished_at=finished, command=cmd)


