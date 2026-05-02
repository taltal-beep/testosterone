from __future__ import annotations

import contextlib
import os
import queue
import shlex
import shutil
import subprocess
import sys
import threading
import time
import uuid
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Generator, Mapping, Optional, Sequence

try:
    import docker
except Exception:  # pragma: no cover - optional dependency/import-time daemon failures
    docker = None

from .command_builders import BuiltCommand, RunConfig, TestType, build_command
from .paths import default_artifacts_root
from .metrics_extractor import write_manual_locust_results_json
from .report_generator import (
    collect_behavex_native_report,
    compute_system_health_pct,
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


def _run_scoped_allure_results_dir(base_dir: Path, run_id: str) -> Path:
    """
    Keep concurrent non-audit runs from sharing the same framework results directory.

    The UI passes a framework-scoped parent such as ``artifacts/allure-results/pytest``;
    each subprocess writes into its own child so another session cannot archive, delete,
    or mix this run's Allure files while it is still executing.
    """
    return base_dir.expanduser().resolve() / str(run_id)


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


DOCKER_IMAGE = "python:3.11-slim"
DOCKER_NETWORK = "uqo-net"
DOCKER_MOUNT_POINT = "/app"
ORCHESTRATOR_MOUNT_POINT = "/uqo"


def _default_container_timeout_s() -> float:
    v = (os.getenv("UQO_CONTAINER_TIMEOUT_S") or "").strip()
    if not v:
        return 600.0
    try:
        return float(v)
    except ValueError:
        return 600.0


def _host_repo_root() -> Path:
    # Repo root is the parent of `uqo_core/`.
    return Path(__file__).resolve().parents[1]


def _to_container_path(host_path: Path, *, target_root: Path | None = None) -> str:
    """
    Convert a mounted host path into its container path.

    The target repo is mounted at /app. The orchestrator repo is mounted at /uqo
    when the target repo lives outside it, and at /app for in-repo runs.
    """
    root = _host_repo_root().expanduser().resolve()
    target = target_root.expanduser().resolve() if target_root is not None else root
    mappings: list[tuple[Path, str]] = [(target, DOCKER_MOUNT_POINT)]
    if target != root:
        mappings.append((root, ORCHESTRATOR_MOUNT_POINT))
    else:
        mappings.append((root, DOCKER_MOUNT_POINT))

    resolved = host_path.expanduser().resolve()
    for host_base, container_base in mappings:
        try:
            rel = resolved.relative_to(host_base)
        except ValueError:
            continue
        return str(Path(container_base) / rel).replace("\\", "/")
    return DOCKER_MOUNT_POINT


def _rewrite_container_arg(arg: str, *, target_root: Path) -> str:
    """Rewrite host-absolute path arguments to their mounted container paths."""
    if "," in arg:
        parts = arg.split(",")
        rewritten = [_rewrite_container_arg(part, target_root=target_root) for part in parts]
        return ",".join(rewritten)
    if "=" in arg:
        prefix, value = arg.split("=", 1)
        if value.startswith(os.sep):
            return f"{prefix}={_to_container_path(Path(value), target_root=target_root)}"
    if arg.startswith(os.sep):
        return _to_container_path(Path(arg), target_root=target_root)
    return arg


def _docker_volumes_for(target_root: Path) -> dict[str, dict[str, str]]:
    """Build Docker bind mounts for the target repo plus orchestrator support files."""
    root = _host_repo_root().expanduser().resolve()
    target = target_root.expanduser().resolve()
    volumes: dict[str, dict[str, str]] = {
        str(target): {"bind": DOCKER_MOUNT_POINT, "mode": "rw"},
    }
    if target != root:
        volumes[str(root)] = {"bind": ORCHESTRATOR_MOUNT_POINT, "mode": "rw"}
    return volumes


def _orchestrator_container_root(*, target_root: Path) -> str:
    root = _host_repo_root().expanduser().resolve()
    target = target_root.expanduser().resolve()
    return DOCKER_MOUNT_POINT if target == root else ORCHESTRATOR_MOUNT_POINT


def _container_display_mounts(target_root: Path) -> str:
    parts = [f"{host} -> {cfg['bind']}" for host, cfg in _docker_volumes_for(target_root).items()]
    return ", ".join(parts)


def _docker_client():
    if docker is None:
        return None
    try:
        return docker.from_env()
    except Exception:
        return None


def _docker_env_from_cmd_env(env: Mapping[str, str]) -> dict[str, str]:
    """
    Keep env minimal: propagate the SUT URL, run ids, and common S3/MinIO credentials.
    """
    allow_prefixes = ("UQO_", "AWS_", "S3_", "MINIO_")
    allow_exact = {"SUT_URL"}
    out: dict[str, str] = {}
    for k, v in env.items():
        if k in allow_exact or k.startswith(allow_prefixes):
            out[str(k)] = str(v)
    return out


def _run_in_ephemeral_container_streaming(
    *,
    run_id: str,
    cmd: BuiltCommand,
    cfg_timeout_s: float | None,
    cfg_heartbeat_s: float,
    emit: "callable[[str, str], None]",
    log_path: Path,
) -> tuple[int, float, float]:
    """
    Run `cmd` in a one-off Docker container and stream logs into `emit` and `log_path`.
    Returns (returncode, started_at, finished_at).
    """
    started_at = time.time()
    target_root = cmd.cwd.expanduser().resolve()

    # When Docker is unavailable (common in local pytest / CI), fall back to a direct
    # local subprocess runner while preserving the same streaming contract.
    docker_client = _docker_client()
    if docker_client is None:
        os.makedirs(str(log_path.parent), exist_ok=True)

        argv = list(cmd.argv)
        _resolve_subprocess_argv(argv)

        emit("meta", "[runner] docker unavailable; falling back to local subprocess\n")
        emit("meta", f"$ (cwd={cmd.cwd}) {' '.join(argv)}\n")

        q: queue.Queue[LogEvent | None] = queue.Queue()
        proc: subprocess.Popen[str] | None = None

        try:
            with open(log_path, "a", encoding="utf-8") as lf:
                proc = subprocess.Popen(
                    argv,
                    cwd=str(cmd.cwd),
                    env=dict(cmd.env),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                )

                def reader_thread() -> None:
                    try:
                        assert proc is not None
                        out = proc.stdout
                        if out is None:
                            q.put(LogEvent(ts=time.time(), stream="meta", line="[subprocess] no stdout pipe\n"))
                            return
                        for line in out:
                            lf.write(line)
                            lf.flush()
                            q.put(LogEvent(ts=time.time(), stream="stdout", line=line))
                    except Exception as exc:
                        q.put(LogEvent(ts=time.time(), stream="meta", line=f"[subprocess stream error] {exc}\n"))
                    finally:
                        q.put(None)

                t_out = threading.Thread(target=reader_thread, daemon=True)
                t_out.start()

                last_output_ts = time.time()
                returncode: int | None = None

                while True:
                    try:
                        item = q.get(timeout=0.1)
                        if item is None:
                            pass
                        else:
                            last_output_ts = time.time()
                            emit(item.stream, item.line)
                    except queue.Empty:
                        pass

                    now = time.time()
                    if float(cfg_heartbeat_s) > 0 and (now - last_output_ts) >= float(cfg_heartbeat_s):
                        last_output_ts = now
                        emit("meta", "[still running...]\n")

                    if cfg_timeout_s is not None and (now - started_at) >= float(cfg_timeout_s):
                        emit("meta", f"[timeout after {cfg_timeout_s}s] terminating subprocess...\n")
                        with contextlib.suppress(Exception):
                            assert proc is not None
                            proc.kill()
                        returncode = 124
                        break

                    assert proc is not None
                    polled = proc.poll()
                    if polled is not None:
                        returncode = int(polled)
                        break

                t_out.join(timeout=2.0)
                if returncode is None and proc is not None:
                    with contextlib.suppress(Exception):
                        returncode = int(proc.wait(timeout=1.0))
                if returncode is None:
                    returncode = 1

                finished_at = time.time()
                return int(returncode), started_at, finished_at
        except FileNotFoundError as exc:
            finished_at = time.time()
            emit("meta", f"[subprocess error] {exc}\n")
            return 127, started_at, finished_at
        except Exception as exc:
            finished_at = time.time()
            emit("meta", f"[subprocess error] {exc}\n")
            return 1, started_at, finished_at
        finally:
            if proc is not None:
                with contextlib.suppress(Exception):
                    proc.kill()
                with contextlib.suppress(Exception):
                    proc.wait(timeout=0.5)

    container_repo_root = _orchestrator_container_root(target_root=target_root)
    container_cwd = _to_container_path(cmd.cwd, target_root=target_root)

    # Rewrite orchestrator-defined paths that are host-absolute into /app-relative paths.
    env_for_container = dict(cmd.env)
    shared_dir = env_for_container.get("UQO_SHARED_ALLURE_RESULTS_DIR")
    if shared_dir:
        env_for_container["UQO_SHARED_ALLURE_RESULTS_DIR"] = _to_container_path(Path(shared_dir), target_root=target_root)
    container_argv = [_rewrite_container_arg(str(a), target_root=target_root) for a in cmd.argv]

    # Ensure the container can import orchestrator/drop-in code when plugins need it.
    pp_parts = [str(Path(container_repo_root) / "drop_in_hooks"), str(container_repo_root)]
    existing_pp = env_for_container.get("PYTHONPATH")
    if existing_pp:
        pp_parts.append(existing_pp)
    env_for_container["PYTHONPATH"] = os.pathsep.join([p for p in pp_parts if p])
    env_for_container["PYTHONUNBUFFERED"] = "1"

    # Install deps then execute the plugin command.
    plugin_cmd = shlex.join(list(container_argv))
    bash_cmd = f"pip install --no-cache-dir -r {shlex.quote(str(Path(container_repo_root) / 'requirements.txt'))} && cd {shlex.quote(container_cwd)} && {plugin_cmd}"

    os.makedirs(str(log_path.parent), exist_ok=True)

    container = None
    returncode: int | None = None
    try:
        emit("meta", f"[docker] image={DOCKER_IMAGE} network={DOCKER_NETWORK}\n")
        emit("meta", f"[docker] mounts {_container_display_mounts(target_root)}\n")
        emit("meta", f"[docker] $ (cwd={container_cwd}) bash -lc {bash_cmd}\n")

        container = docker_client.containers.run(
            DOCKER_IMAGE,
            command=["bash", "-lc", bash_cmd],
            detach=True,
            network=DOCKER_NETWORK,
            working_dir=container_repo_root,
            volumes=_docker_volumes_for(target_root),
            environment=_docker_env_from_cmd_env(env_for_container),
            name=f"uqo-run-{run_id[:12]}",
            auto_remove=False,
        )

        q: queue.Queue[LogEvent | None] = queue.Queue()

        def reader_thread() -> None:
            try:
                with open(log_path, "a", encoding="utf-8") as lf:
                    for chunk in container.logs(stream=True, follow=True):
                        try:
                            s = chunk.decode("utf-8", errors="replace")
                        except Exception:
                            s = str(chunk)
                        # Preserve newlines so the UI matches the log file.
                        for line in s.splitlines(True):
                            lf.write(line)
                            lf.flush()
                            q.put(LogEvent(ts=time.time(), stream="stdout", line=line))
            except Exception as exc:
                q.put(LogEvent(ts=time.time(), stream="meta", line=f"[docker log stream error] {exc}\n"))
            finally:
                q.put(None)

        t_out = threading.Thread(target=reader_thread, daemon=True)
        t_out.start()

        last_output_ts = time.time()
        while True:
            try:
                item = q.get(timeout=0.1)
                if item is None:
                    # Log thread ended; container might still be exiting.
                    pass
                else:
                    last_output_ts = time.time()
                    emit(item.stream, item.line)
            except queue.Empty:
                pass

            now = time.time()
            if float(cfg_heartbeat_s) > 0 and (now - last_output_ts) >= float(cfg_heartbeat_s):
                last_output_ts = now
                emit("meta", "[still running...]\n")

            if cfg_timeout_s is not None and (now - started_at) >= float(cfg_timeout_s):
                emit("meta", f"[timeout after {cfg_timeout_s}s] terminating container...\n")
                with contextlib.suppress(Exception):
                    container.kill()
                returncode = 124
                break

            with contextlib.suppress(Exception):
                container.reload()
            if getattr(container, "status", "") == "exited":
                try:
                    w = container.wait()
                    returncode = int(w.get("StatusCode", 1))
                except Exception:
                    returncode = 1
                break

        t_out.join(timeout=2.0)
        if returncode is None:
            try:
                w = container.wait()
                returncode = int(w.get("StatusCode", 1))
            except Exception:
                returncode = 1

        finished_at = time.time()
        return int(returncode), started_at, finished_at
    finally:
        if container is not None:
            with contextlib.suppress(Exception):
                container.remove(force=True)

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
        # SOLID firewall: callers provide a framework-scoped parent; isolate this run
        # underneath it so concurrent sessions never mutate each other's output.
        shared_allure_dir = _run_scoped_allure_results_dir(cfg.shared_allure_results_dir, run_id)
        if shared_allure_dir.exists():
            prepared = prepare_allure_results_dir(shared_allure_dir, mode="archive", run_id=run_id)
            shared_allure_dir = prepared.shared_dir
        else:
            shared_allure_dir.mkdir(parents=True, exist_ok=True)
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

    # Safety net: enforce a default timeout (prevents runaway containers).
    if cfg.timeout_s is None:
        cfg = replace(cfg, timeout_s=_default_container_timeout_s())

    cmd = build_command(cfg, parent_env=parent_env or os.environ)

    orchestrator_root = Path(__file__).resolve().parents[1]
    drop_in_root = orchestrator_root / "drop_in_hooks"

    pythonpath_parts = [str(orchestrator_root), str(drop_in_root)]
    existing_pp = cmd.env.get("PYTHONPATH")
    if existing_pp:
        pythonpath_parts.append(existing_pp)
    cmd.env["PYTHONPATH"] = os.pathsep.join(pythonpath_parts)

    # Plugins may optionally request a site-packages prefix (BehaveX runs often need this
    # when launched from Streamlit workers where sys.path differs from the target venv).
    site_packages = cmd.env.pop("_UQO_BEHAVEX_SITE_PACKAGES", None)
    if site_packages:
        cmd.env["PYTHONPATH"] = os.pathsep.join([site_packages, cmd.env.get("PYTHONPATH", "")]).strip(os.pathsep)

    cmd.env["PYTHONUNBUFFERED"] = "1"

    q: queue.Queue[LogEvent | None] = queue.Queue()

    def emit(stream: str, line: str) -> None:
        q.put(LogEvent(ts=time.time(), stream=stream, line=line))

    emit("meta", f"$ UQO_RUN_ID={run_id}\n")
    emit("meta", f"$ (cwd={cmd.cwd}) {' '.join(cmd.argv)}\n")

    os.makedirs(str(cfg.shared_allure_results_dir), exist_ok=True)
    local_run_log = (_host_repo_root() / "logs" / f"{run_id}.log").resolve()

    def emit_from_container(stream: str, line: str) -> None:
        q.put(LogEvent(ts=time.time(), stream=stream, line=line))

    rc, started_at, finished_at = _run_in_ephemeral_container_streaming(
        run_id=run_id,
        cmd=cmd,
        cfg_timeout_s=cfg.timeout_s,
        cfg_heartbeat_s=cfg.heartbeat_s,
        emit=emit_from_container,
        log_path=local_run_log,
    )

    # Drain any remaining queued output.
    drain_deadline = time.time() + 2.0
    while time.time() < drain_deadline:
        try:
            item = q.get_nowait()
            if item is not None:
                yield item
        except queue.Empty:
            break

    yield LogEvent(ts=finished_at, stream="meta", line=f"\n[exit code {int(rc)}]\n")
    if emit_done_marker:
        yield LogEvent(
            ts=time.time(),
            stream="meta",
            line=f"{UQO_DONE_MARKER} returncode={int(rc)}\n",
        )

    # Framework-specific lifecycle fixes that must occur immediately after the run exits,
    # before any report generation/sync that relies on the shared Allure results directory.
    if run_framework_hooks and cfg.test_type.value == "behavex":
        try:
            moved = _collect_behavex_allure_json_into_shared_dir(
                target_repo=cmd.cwd,
                artifacts_root=artifacts_root,
                shared_allure_results_dir=shared_allure_dir,
            )
            if moved:
                yield LogEvent(
                    ts=time.time(),
                    stream="meta",
                    line=f"[behavex allure json] copied {moved} *.json into {shared_allure_dir}\n",
                )
        except Exception:
            pass

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
            # Locust's --html output is written into the isolated shared results directory.
            # Mirror it into artifacts_root so existing static sync code can publish it.
            _mirror_locust_html_into_artifacts_root(
                shared_allure_results_dir=shared_allure_dir,
                artifacts_root=artifacts_root,
            )
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
    native_behave_args: Sequence[str] = (),
    run_native_behave: bool = False,
    locust_args: Sequence[str] = (),
    locust_users: int = 10,
    locust_spawn_rate: int = 2,
    locust_run_time: str = "1m",
    locust_only_summary: bool = True,
) -> Generator[LogEvent, None, RunResult]:
    """
    Run Pytest → BehaveX → Native Behave (optional) → Locust into isolated
    ``allure-results/{pytest,behavex,behave_native,locust}/`` directories (no overwrite).
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
    enable_native_behave = bool(run_native_behave)

    if enable_native_behave:
        # Native Behave is executed via its own CLI (not BehaveX).
        phases.insert(2, (TestType.BEHAVE_NATIVE, "behave_native", "Behave (native)"))

    phase_returncodes: list[int] = []
    last_cmd: BuiltCommand | None = None
    rr: RunResult | None = None

    for idx, (tt, key, title) in enumerate(phases, start=1):
        yield LogEvent(
            ts=time.time(),
            stream="meta",
            line=f"{UQO_AUDIT_PHASE} [{idx}/{len(phases)}] {key} — {title}\n",
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
            behave_native_args=tuple(native_behave_args),
            locust_args=tuple(locust_args),
            locust_headless=True,
            locust_users=int(locust_users),
            locust_spawn_rate=int(locust_spawn_rate),
            locust_run_time=str(locust_run_time),
            locust_only_summary=bool(locust_only_summary),
            run_id=f"{audit_run_id}-{key}",
            last_test_type=key,
            extra_env=extra,
            timeout_s=_default_container_timeout_s(),
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

    # Native mirrors (no unified Allure report generation)
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

    # Generate per-framework Allure HTML (strict isolation).
    frameworks: list[str] = ["pytest", "behavex"]
    if enable_native_behave:
        frameworks.append("behave_native")

    for fw in frameworks:
        out_dir = default_report_paths(artifacts_root=artifacts_root).report_dir / fw
        ok_gen, msg_gen, _ = generate_allure_html(
            results_dir=(shared_allure / fw),
            report_dir=out_dir,
            input_dirs=[shared_allure / fw],
        )
        if ok_gen:
            yield LogEvent(ts=time.time(), stream="meta", line=f"[AUDIT] Allure HTML ({fw}): {msg_gen}\n")
        else:
            yield LogEvent(ts=time.time(), stream="meta", line=f"[AUDIT] Allure generate failed ({fw}): {msg_gen}\n")

    # Health score is a metric computed from results JSON across isolated dirs.
    health_pct = compute_system_health_pct(shared_allure)

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


def run_native_behave(
    *,
    target_repo: Path,
    artifacts_root: Path | None = None,
    parent_env: Optional[Mapping[str, str]] = None,
    behave_args: Sequence[str] = (),
    extra_env: Mapping[str, str] | None = None,
    run_id: str | None = None,
) -> Generator[LogEvent, None, RunResult]:
    """
    Run standard Behave (not BehaveX) with Allure formatter.

    Command shape:
      behave -f allure_behave.formatter:AllureFormatter -o artifacts/allure-results/behave_native ...
    """
    started = time.time()
    artifacts_root = (artifacts_root or Path("artifacts")).expanduser().resolve()
    out_dir = (artifacts_root / "allure-results" / "behave_native").resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    repo_root = target_repo.expanduser().resolve()
    features_dir = repo_root / "features"
    if not features_dir.is_dir():
        finished = time.time()
        yield LogEvent(
            ts=time.time(),
            stream="meta",
            line=f"[behave_native] skipping: missing features/ under {repo_root}\n",
        )
        cmd = BuiltCommand(argv=["behave"], cwd=repo_root, env=dict(parent_env or os.environ))
        return RunResult(returncode=0, started_at=started, finished_at=finished, command=cmd)

    argv: list[str] = [
        "behave",
        "-f",
        "allure_behave.formatter:AllureFormatter",
        "-o",
        str(out_dir),
        *list(behave_args),
    ]
    _resolve_subprocess_argv(argv)

    env = dict(parent_env or os.environ)
    if extra_env:
        env.update({str(k): str(v) for k, v in extra_env.items()})
    if run_id:
        env["UQO_RUN_ID"] = str(run_id)
    env["UQO_LAST_TEST_TYPE"] = "behave_native"
    env["UQO_SHARED_ALLURE_RESULTS_DIR"] = str(out_dir)

    cmd = BuiltCommand(argv=list(argv), cwd=repo_root, env=env)

    yield LogEvent(ts=time.time(), stream="meta", line=f"[behave_native] running: {' '.join(argv)}\n")

    run_id_eff = str(run_id or uuid.uuid4())
    local_run_log = (_host_repo_root() / "logs" / f"{run_id_eff}.log").resolve()

    q: queue.Queue[LogEvent | None] = queue.Queue()

    def _emit(stream: str, line: str) -> None:
        q.put(LogEvent(ts=time.time(), stream=stream, line=line))

    rc, started_at, finished_at = _run_in_ephemeral_container_streaming(
        run_id=run_id_eff,
        cmd=cmd,
        cfg_timeout_s=60.0,
        cfg_heartbeat_s=10.0,
        emit=_emit,
        log_path=local_run_log,
    )

    drain_deadline = time.time() + 2.0
    while time.time() < drain_deadline:
        try:
            item = q.get_nowait()
            if item is not None:
                yield item
        except queue.Empty:
            break

    return RunResult(returncode=int(rc), started_at=started_at, finished_at=finished_at, command=cmd)


def _collect_behavex_allure_json_into_shared_dir(
    *,
    target_repo: Path,
    artifacts_root: Path,
    shared_allure_results_dir: Path,
) -> int:
    """
    BehaveX may write Allure JSON into its own output folder tree instead of the orchestrator's
    isolated ``shared_allure_results_dir``. Copy any emitted ``*.json`` files from known BehaveX
    internal locations into the shared dir so Allure generation never sees an empty folder.
    """
    target_repo = target_repo.expanduser().resolve()
    artifacts_root = artifacts_root.expanduser().resolve()
    shared_allure_results_dir = shared_allure_results_dir.expanduser().resolve()
    shared_allure_results_dir.mkdir(parents=True, exist_ok=True)

    candidates: list[Path] = []

    # Primary orchestrator BehaveX output folder (set by command builder: artifacts/behave_reports)
    candidates.append(artifacts_root / "behave_reports" / "behave" / "allure")
    candidates.append(artifacts_root / "behave_reports" / "allure")

    # Legacy BehaveX output folder(s)
    candidates.append(artifacts_root / "behavex-output" / "behave" / "allure")
    candidates.append(artifacts_root / "behavex-output" / "allure")

    # Repo-relative defaults some BehaveX versions/plugins use
    candidates.append(target_repo / "behavex_output" / "behave" / "allure")
    candidates.append(target_repo / "output" / "behave" / "allure")
    candidates.append(target_repo / "output" / "allure")

    copied = 0
    seen: set[str] = set()
    for src_dir in candidates:
        if not src_dir.is_dir():
            continue
        try:
            for p in src_dir.rglob("*.json"):
                if not p.is_file():
                    continue
                # Avoid double-copying identical file names from multiple candidate roots.
                if p.name in seen:
                    continue
                dest = shared_allure_results_dir / p.name
                if dest.exists():
                    continue
                try:
                    shutil.copy2(p, dest)
                    seen.add(p.name)
                    copied += 1
                except OSError:
                    continue
        except OSError:
            continue

    return copied


def _mirror_locust_html_into_artifacts_root(*, shared_allure_results_dir: Path, artifacts_root: Path) -> Path | None:
    """
    Locust writes native HTML via ``--html``. We keep it inside the isolated shared results dir,
    but also mirror it into ``artifacts_root/locust_report.html`` so the static sync code can publish it.
    """
    shared_allure_results_dir = shared_allure_results_dir.expanduser().resolve()
    artifacts_root = artifacts_root.expanduser().resolve()
    src = shared_allure_results_dir / "locust_report.html"
    if not src.is_file():
        return None
    artifacts_root.mkdir(parents=True, exist_ok=True)
    dst = (artifacts_root / "locust_report.html").resolve()
    try:
        shutil.copy2(src, dst)
    except OSError:
        return None
    return dst


