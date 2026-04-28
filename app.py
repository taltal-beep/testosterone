from __future__ import annotations

import os
import queue
import threading
import time
from pathlib import Path
from typing import Optional

# Load `.env` before other imports read ``os.environ`` (integrations, secrets).
_APP_ROOT = Path(__file__).resolve().parent
try:
    from dotenv import load_dotenv

    load_dotenv(_APP_ROOT / ".env")
except Exception:
    pass

import streamlit as st

from engine.command_builders import RunConfig, TestType, coerce_path
from engine.runners import (
    UQO_AUDIT_HEALTH,
    UQO_AUDIT_PHASE,
    UQO_DONE_MARKER,
    LogEvent,
    RunResult,
    default_artifacts_root,
    run_streaming,
    validate_target_repo,
)
from engine.sandbox_api import (
    MOCK_BASE_URL,
    is_managed_process_alive,
    sample_target_repo,
    start_sandbox_if_needed,
    stop_sandbox_if_managed,
)
from engine.integrations import (
    auto_push_metrics_if_enabled,
    integration_status_from_env,
    push_to_influxdb,
    push_to_prometheus,
    test_influxdb_connection,
    test_prometheus_pushgateway,
)
from engine.metrics import list_run_history, write_metrics_json
from engine.metrics_extractor import to_run_metrics
from engine.run_history import (
    RunStatus,
    cleanup_orphaned_runs,
    create_run,
    get_run,
    list_run_sessions,
    record_completed_run,
    snapshot_files_for_download,
    update_run_status,
)
from engine.paths import STATIC_BEHAVE_INDEX
from engine.report_generator import STATIC_ALLURE_HTML, STATIC_ALLURE_INDEX
from engine.services import AuditService, MetricsService, ReportService, RunLogLine, iter_drained_queue_items


def _section_label(text: str) -> None:
    st.markdown(
        f'<p style="font-size:0.7rem;font-weight:600;letter-spacing:0.08em;color:rgba(248,249,251,0.45);margin:0 0 0.5rem 0;">{text}</p>',
        unsafe_allow_html=True,
    )


def init_state() -> None:
    """
    Initialize all ``st.session_state`` keys before any widgets mount.

    Widget-bound keys (e.g. toggles) use ``if key not in session_state`` so defaults are
    set exactly once; the rest use ``setdefault``.
    """
    if "auto_push_influx" not in st.session_state:
        st.session_state["auto_push_influx"] = False
    if "auto_push_prometheus" not in st.session_state:
        st.session_state["auto_push_prometheus"] = False
    if "run_completed" not in st.session_state:
        st.session_state.run_completed = False
    if "last_test_type" not in st.session_state:
        st.session_state.last_test_type = None

    st.session_state.setdefault("running", False)
    st.session_state.setdefault("log_lines", [])
    st.session_state.setdefault("log_max_lines", 2000)
    st.session_state.setdefault("events_q", None)  # type: ignore[assignment]
    st.session_state.setdefault("worker", None)  # type: ignore[assignment]
    st.session_state.setdefault("last_result", None)  # type: ignore[assignment]
    st.session_state.setdefault("sandbox_mode", False)
    st.session_state.setdefault("report_server", None)  # type: ignore[assignment]
    st.session_state.setdefault("last_run_id", None)  # type: ignore[assignment]
    st.session_state.setdefault("target_repo", str(Path(".").resolve()))
    st.session_state.setdefault("is_audit_mode", False)
    st.session_state.setdefault("audit_phase_display", "")
    st.session_state.setdefault("audit_health_pct", None)
    st.session_state.setdefault("audit_partial_success", False)
    st.session_state.setdefault("influx_url", os.getenv("INFLUXDB_URL", ""))
    st.session_state.setdefault("influx_org", os.getenv("INFLUXDB_ORG", ""))
    st.session_state.setdefault("influx_bucket", os.getenv("INFLUXDB_BUCKET", ""))
    st.session_state.setdefault("influx_token", os.getenv("INFLUXDB_TOKEN", ""))
    st.session_state.setdefault("prometheus_pushgateway_url", os.getenv("PROMETHEUS_PUSHGATEWAY_URL", ""))
    st.session_state.setdefault("influx_test_ok", None)
    st.session_state.setdefault("prometheus_test_ok", None)


def _append_line(line: str) -> None:
    st.session_state.log_lines.append(line)
    max_lines = int(st.session_state.get("log_max_lines", 2000))
    if len(st.session_state.log_lines) > max_lines:
        st.session_state.log_lines = st.session_state.log_lines[-max_lines:]


def _start_worker(cfg: RunConfig, *, db_run_id: str | None = None) -> None:
    events_q: queue.Queue[LogEvent | RunResult] = queue.Queue()

    def worker() -> None:
        # If the subprocess runner crashes, ensure the DB doesn't get stuck in RUNNING forever.
        try:
            gen = run_streaming(cfg, artifacts_root=default_artifacts_root())
            while True:
                try:
                    ev = next(gen)
                    events_q.put(ev)
                except StopIteration as e:
                    if e.value is not None:
                        events_q.put(e.value)
                    break
        except Exception as exc:
            import traceback

            if db_run_id:
                try:
                    update_run_status(
                        db_run_id,
                        status=RunStatus.FAILED,
                        metadata={"error": str(exc), "traceback": traceback.format_exc()},
                    )
                except Exception:
                    pass

            events_q.put(
                LogEvent(
                    ts=time.time(),
                    stream="meta",
                    line=f"[orchestrator worker error] {exc}\n{traceback.format_exc()}\n",
                )
            )
            events_q.put(LogEvent(ts=time.time(), stream="meta", line=f"{UQO_DONE_MARKER} returncode=-1\n"))

    t = threading.Thread(target=worker, daemon=True)
    st.session_state.events_q = events_q
    st.session_state.worker = t
    st.session_state.running = True
    st.session_state.last_result = None
    st.session_state.run_completed = False
    st.session_state.last_run_id = None
    st.session_state.is_audit_mode = False
    st.session_state.audit_phase_display = ""
    st.session_state.active_db_run_id = db_run_id
    t.start()


def _start_worker_audit(
    *,
    target_repo: Path,
    pytest_args: tuple[str, ...],
    behavex_args: tuple[str, ...],
    native_behave_args: tuple[str, ...],
    run_native_behave: bool,
    locust_args: tuple[str, ...],
    locust_users: int,
    locust_spawn_rate: int,
    locust_run_time: str,
    locust_only_summary: bool,
) -> None:
    events_q: queue.Queue[LogEvent | RunResult] = queue.Queue()

    def worker() -> None:
        try:
            gen = AuditService.stream_audit(
                target_repo=target_repo,
                artifacts_root=default_artifacts_root(),
                parent_env=os.environ,
                pytest_args=pytest_args,
                behavex_args=behavex_args,
                native_behave_args=native_behave_args,
                run_native_behave=run_native_behave,
                locust_args=locust_args,
                locust_users=locust_users,
                locust_spawn_rate=locust_spawn_rate,
                locust_run_time=locust_run_time,
                locust_only_summary=locust_only_summary,
            )
            while True:
                try:
                    ev = next(gen)
                    events_q.put(ev)
                except StopIteration as e:
                    if e.value is not None:
                        events_q.put(e.value)
                    break
        except Exception as exc:
            import traceback

            events_q.put(
                LogEvent(
                    ts=time.time(),
                    stream="meta",
                    line=f"[orchestrator worker error] {exc}\n{traceback.format_exc()}\n",
                )
            )
            events_q.put(LogEvent(ts=time.time(), stream="meta", line=f"{UQO_DONE_MARKER} returncode=-1\n"))

    t = threading.Thread(target=worker, daemon=True)
    st.session_state.events_q = events_q
    st.session_state.worker = t
    st.session_state.running = True
    st.session_state.last_result = None
    st.session_state.run_completed = False
    st.session_state.last_run_id = None
    st.session_state.is_audit_mode = True
    st.session_state.audit_phase_display = ""
    st.session_state.audit_health_pct = None
    t.start()


def _apply_run_result_to_session(item: RunResult) -> None:
    st.session_state.last_result = item
    st.session_state.running = False
    st.session_state.run_completed = True
    env = item.command.env
    st.session_state.last_run_id = env.get("UQO_AUDIT_RUN_ID") or env.get("UQO_RUN_ID")
    st.session_state.active_db_run_id = None
    if item.audit_mode:
        if item.audit_health_pct is not None:
            st.session_state["audit_health_pct"] = item.audit_health_pct
        st.session_state["audit_partial_success"] = item.audit_partial_success
    try:
        record_completed_run(
            rr=item,
            artifacts_root=default_artifacts_root().expanduser().resolve(),
            test_kind=str(st.session_state.get("last_test_type") or "unknown"),
            audit_health_pct=st.session_state.get("audit_health_pct"),
        )
    except Exception:
        pass
    try:
        if st.session_state.get("auto_push_influx") or st.session_state.get("auto_push_prometheus"):
            rid = st.session_state.get("last_run_id")
            logs = auto_push_metrics_if_enabled(
                artifacts_root=default_artifacts_root().expanduser().resolve(),
                run_id=str(rid) if rid else None,
                auto_influx=bool(st.session_state.get("auto_push_influx")),
                auto_prometheus=bool(st.session_state.get("auto_push_prometheus")),
                influx_url=st.session_state.get("influx_url") or None,
                influx_token=st.session_state.get("influx_token") or None,
                influx_org=st.session_state.get("influx_org") or None,
                influx_bucket=st.session_state.get("influx_bucket") or None,
                prometheus_pushgateway_url=st.session_state.get("prometheus_pushgateway_url") or None,
            )
            for _name, ok, msg in logs:
                _append_line(f"[auto-push] {'OK' if ok else 'FAIL'} {_name}: {msg}")
    except Exception as exc:
        _append_line(f"[auto-push] skipped: {exc}")


def _apply_run_log_line_to_session(stream: str, line: str) -> None:
    done_sentinel = UQO_DONE_MARKER in line
    if done_sentinel:
        st.session_state.running = False

    prefix = ""
    if stream == "stderr":
        prefix = "[stderr] "
    elif stream == "meta":
        prefix = ""
    if UQO_AUDIT_PHASE in line:
        st.session_state["audit_phase_display"] = line.strip()
    if UQO_AUDIT_HEALTH in line:
        try:
            rest = line.split(UQO_AUDIT_HEALTH, 1)[1].strip()
            st.session_state["audit_health_pct"] = float(rest)
        except (ValueError, IndexError):
            pass
    _append_line(prefix + line.rstrip("\n"))

    if done_sentinel:
        st.session_state.run_completed = True


def _drain_events() -> None:
    q: Optional[queue.Queue[object]] = st.session_state.events_q
    if not q:
        return

    for item in iter_drained_queue_items(q):
        if isinstance(item, RunResult):
            _apply_run_result_to_session(item)
        elif isinstance(item, RunLogLine):
            _apply_run_log_line_to_session(item.stream, item.line)


def _on_sandbox_toggle() -> None:
    if not st.session_state.get("sandbox_mode", False):
        stop_sandbox_if_managed()


def _streamlit_origin() -> str:
    u = getattr(st.context, "url", None)
    if u:
        from urllib.parse import urlparse

        p = urlparse(str(u))
        return f"{p.scheme}://{p.netloc}"
    host = st.get_option("server.address") or "localhost"
    if host in ("0.0.0.0", "::", "[::]"):
        host = "localhost"
    port = int(st.get_option("server.port") or 8501)
    return f"http://{host}:{port}"


def get_base_url() -> str:
    """Streamlit origin (scheme + host + port) for static report URLs."""
    return _streamlit_origin()


def _streamlit_static_url(relative_under_static: str) -> str:
    rel = relative_under_static.lstrip("/")
    return f"{_streamlit_origin()}/app/static/{rel}"


def _static_paths_exist() -> tuple[bool, bool]:
    return ReportService.static_reports_ready()


def _execution_status_title() -> str:
    if st.session_state.get("is_audit_mode"):
        raw = str(st.session_state.get("audit_phase_display") or "")
        if UQO_AUDIT_PHASE in raw:
            raw = raw.split(UQO_AUDIT_PHASE, 1)[-1].strip()
        if raw:
            return f"Full System Audit — {raw}"
        return "Full System Audit — starting…"
    return "Running tests…"


st.set_page_config(page_title="Unified Quality Orchestration", layout="wide")

init_state()

# Startup safety: if the app was force-killed mid-run, don't leave DB entries stuck in RUNNING.
if "uqo_startup_cleanup_done" not in st.session_state:
    try:
        cleanup_orphaned_runs()
    except Exception:
        pass
    st.session_state["uqo_startup_cleanup_done"] = True

_drain_events()

st.title("Unified Quality Orchestration & Reporting Dashboard")
st.caption("Streamlit orchestrator — zero-touch wrapper; runs tools via subprocess in the target repo.")

sandbox_path = str(sample_target_repo().resolve())

tab_exec, tab_analytics, tab_history, tab_integrations = st.tabs(
    ["Execution", "Analytics", "History", "Integrations"]
)

_report_svc = ReportService()
artifacts_root = _report_svc.artifacts_root
paths = _report_svc.report_paths()

with tab_exec:
    left_cfg, right_run = st.columns([1, 2], gap="large")

    with left_cfg:
        st.subheader("Run configuration")

        with st.container(border=True):
            _section_label("SANDBOX")
            st.checkbox(
                "Load sandbox mode",
                key="sandbox_mode",
                on_change=_on_sandbox_toggle,
                disabled=bool(st.session_state.running),
            )
            if st.session_state.sandbox_mode:
                st.session_state["target_repo"] = sandbox_path
                ok_api, api_msg = start_sandbox_if_needed()
                if not ok_api:
                    st.error(api_msg)
                else:
                    st.caption(api_msg)
                st.caption(f"Mock API base: `{MOCK_BASE_URL}`")
                col_stop, _ = st.columns([1, 1])
                with col_stop:
                    if st.button("Stop Sandbox API", disabled=bool(st.session_state.running), key="stop_sandbox_btn"):
                        stop_sandbox_if_managed()
                        st.toast("Sandbox API stopped.")
                        st.rerun()
                if is_managed_process_alive():
                    st.caption("Orchestrator is managing the uvicorn process for this session.")

        target_repo_str = st.text_input(
            "Target repository path",
            value=st.session_state.get("target_repo", "") if not st.session_state.sandbox_mode else sandbox_path,
            placeholder="/abs/path/to/test-repo or ./relative/path",
            disabled=bool(st.session_state.running) or bool(st.session_state.sandbox_mode),
        )
        if st.session_state.sandbox_mode:
            target_repo_str = sandbox_path
            st.session_state["target_repo"] = sandbox_path
        else:
            st.session_state["target_repo"] = target_repo_str

        test_type = st.selectbox(
            "Test type",
            options=[t.value for t in TestType],
            index=0,
            disabled=bool(st.session_state.running),
        )

        locust_users = 10
        locust_spawn_rate = 2
        locust_run_time = "1m"
        locust_only_summary = True
        if test_type == TestType.LOCUST.value:
            st.markdown("**Locust (headless)**")
            locust_users = int(
                st.slider(
                    "Users (-u)", min_value=1, max_value=500, value=int(st.session_state.get("locust_users", 10))
                )
            )
            locust_spawn_rate = int(
                st.slider(
                    "Spawn rate (-r)",
                    min_value=1,
                    max_value=500,
                    value=int(st.session_state.get("locust_spawn_rate", 2)),
                )
            )
            locust_run_time = st.text_input(
                "Run time (-t)",
                value=str(st.session_state.get("locust_run_time", "1m")),
                help="Examples: 10s, 1m, 5m",
            )
            locust_only_summary = bool(
                st.checkbox(
                    "Only summary",
                    value=bool(st.session_state.get("locust_only_summary", True)),
                    help="Keeps logs cleaner in headless mode.",
                )
            )
            st.session_state["locust_users"] = locust_users
            st.session_state["locust_spawn_rate"] = locust_spawn_rate
            st.session_state["locust_run_time"] = locust_run_time
            st.session_state["locust_only_summary"] = locust_only_summary

        extra_args = st.text_input(
            "Extra CLI args (space-separated)",
            value=str(st.session_state.get("extra_args", "")),
            placeholder="e.g. -m smoke -q",
            disabled=bool(st.session_state.running),
        )
        st.session_state["extra_args"] = extra_args

        st.number_input(
            "Console buffer (lines)",
            min_value=200,
            max_value=20000,
            step=200,
            key="log_max_lines",
            disabled=bool(st.session_state.running),
        )

        col_a, col_b, col_c = st.columns(3)
        with col_a:
            run_clicked = st.button("Run", type="secondary", disabled=bool(st.session_state.running))
        with col_b:
            audit_clicked = st.button(
                "Run full system audit",
                type="secondary",
                disabled=bool(st.session_state.running),
            )
        with col_c:
            clear_clicked = st.button("Clear console", type="secondary", disabled=bool(st.session_state.running))

        if clear_clicked:
            st.session_state.log_lines = []

        target_repo = coerce_path(target_repo_str) if target_repo_str else Path(".")
        ok, msg = validate_target_repo(target_repo)
        if not ok:
            st.warning(f"Target repo: {msg}")

        if run_clicked:
            if not ok:
                st.error(f"Cannot run: {msg}")
            else:
                argv_extra = [a for a in extra_args.split() if a.strip()]
                # Create a DB row BEFORE execution so History shows it immediately.
                try:
                    db_run_uuid = create_run(status=RunStatus.RUNNING, metadata={"test_kind": str(test_type)})
                    db_run_id = str(db_run_uuid)
                except Exception:
                    db_run_id = None
                timeout_s = float(os.getenv("UQO_CONTAINER_TIMEOUT_S", "600"))
                cfg = RunConfig(
                    test_type=TestType(test_type),
                    target_repo=target_repo,
                    shared_allure_results_dir=Path(f"artifacts/allure-results/{test_type}"),
                    artifacts_root=Path("artifacts"),
                    pytest_args=argv_extra if test_type == TestType.PYTEST.value else (),
                    behavex_args=argv_extra if test_type == TestType.BEHAVEX.value else (),
                    behave_native_args=argv_extra if test_type == TestType.BEHAVE_NATIVE.value else (),
                    locust_args=argv_extra if test_type == TestType.LOCUST.value else (),
                    locust_headless=True,
                    locust_users=int(locust_users),
                    locust_spawn_rate=int(locust_spawn_rate),
                    locust_run_time=str(locust_run_time),
                    locust_only_summary=bool(locust_only_summary),
                    last_test_type=test_type,
                    run_id=db_run_id,
                    timeout_s=timeout_s,
                )
                st.session_state["last_test_type"] = test_type
                st.session_state["is_audit_mode"] = False
                _append_line(f"Starting run: {cfg.test_type.value} in {cfg.target_repo}")
                _start_worker(cfg, db_run_id=db_run_id)

        if audit_clicked:
            if not ok:
                st.error(f"Cannot run audit: {msg}")
            else:
                argv_extra = [a for a in extra_args.split() if a.strip()]
                st.session_state["last_test_type"] = "audit"
                st.session_state["is_audit_mode"] = True
                st.session_state["audit_phase_display"] = ""
                st.session_state["audit_health_pct"] = None
                st.session_state["audit_partial_success"] = False
                _append_line(f"Starting Full System Audit in {target_repo}")
                _start_worker_audit(
                    target_repo=target_repo,
                    pytest_args=tuple(argv_extra),
                    behavex_args=tuple(argv_extra),
                    native_behave_args=tuple(argv_extra),
                    run_native_behave=True,
                    locust_args=tuple(argv_extra),
                    locust_users=int(st.session_state.get("locust_users", locust_users)),
                    locust_spawn_rate=int(st.session_state.get("locust_spawn_rate", locust_spawn_rate)),
                    locust_run_time=str(st.session_state.get("locust_run_time", locust_run_time)),
                    locust_only_summary=bool(st.session_state.get("locust_only_summary", locust_only_summary)),
                )

    with right_run:
        col_out, col_stat = st.columns([2, 1], gap="large")

        with col_out:
            st.subheader("Live output")
            console_text = "\n".join(st.session_state.log_lines)
            if st.session_state.running:
                with st.status(_execution_status_title(), expanded=True):
                    st.caption(
                        "When the subprocess exits, the orchestrator runs **report sync** "
                        "(copying HTML into `./static/`). Expect a short pause before the run is marked complete."
                        if not st.session_state.get("is_audit_mode")
                        else "Audit runs Pytest, BehaveX, Native Behave (optional), then Locust. Each framework writes to its own Allure results folder."
                    )
                    st.code(console_text or "(starting…)", language="text")
            else:
                st.code(console_text or "(no output yet)", language="text")

        with col_stat:
            st.subheader("Run status")
            st.write(f"**Running:** {bool(st.session_state.running)}")
            st.write(f"**Artifacts:** `{default_artifacts_root()}`")
            active_db = st.session_state.get("active_db_run_id")
            if st.session_state.running and active_db:
                st.info(f"DB status: RUNNING (run id `{str(active_db)[:8]}…`)")

            if st.session_state.last_result is not None:
                rr: RunResult = st.session_state.last_result
                if rr.audit_mode and rr.audit_partial_success:
                    st.warning(
                        f"Audit finished with exit code {rr.returncode} (partial success: phases {rr.audit_phase_returncodes})"
                    )
                else:
                    st.success(f"Finished with exit code {rr.returncode}")
                payload = {
                    "returncode": rr.returncode,
                    "duration_s": round(rr.finished_at - rr.started_at, 3),
                    "cwd": str(rr.command.cwd),
                    "argv": rr.command.argv,
                    "allure_results_dir": str(rr.command.env.get("UQO_SHARED_ALLURE_RESULTS_DIR", "")),
                }
                if rr.audit_mode:
                    payload["audit"] = {
                        "phases_returncode": list(rr.audit_phase_returncodes),
                        "partial_success": rr.audit_partial_success,
                        "health_pct": rr.audit_health_pct,
                    }
                st.json(payload)
            elif st.session_state.running:
                st.info("Process is running. Logs update live above.")

with tab_analytics:
    st.subheader("Analytics")
    st.caption("After a run completes, native HTML is mirrored under `./static/` for Streamlit static serving.")

    has_allure, has_locust = _static_paths_exist()
    last_tt = st.session_state.get("last_test_type")
    has_behave = STATIC_BEHAVE_INDEX.is_file()

    if st.session_state.get("run_completed") and st.session_state.get("is_audit_mode"):
        hp = st.session_state.get("audit_health_pct")
        if hp is not None:
            st.metric("Overall system health score", f"{float(hp):.1f}%")
        if st.session_state.get("audit_partial_success"):
            st.warning("Partial success: at least one audit phase failed; see Execution logs for phase exit codes.")

    if st.session_state.get("run_completed"):
        st.success("Last run finished (see Execution tab for exit code).")

    st.markdown('<div style="height:8px"></div>', unsafe_allow_html=True)

    with st.container(border=True):
        _section_label("TEST DASHBOARDS")
        d1, d2 = st.columns(2)
        with d1:
            if has_behave and last_tt in (TestType.BEHAVEX.value, "audit"):
                label = "BehaveX (deep dive)" if last_tt == "audit" else "Open BehaveX report"
                st.link_button(
                    label,
                    f"{get_base_url()}/app/static/behave/index.html",
                    type="secondary",
                )
            else:
                st.caption("BehaveX report not available for the last run.")
        with d2:
            if has_locust and last_tt in (TestType.LOCUST.value, "audit"):
                label = "Locust (deep dive)" if last_tt == "audit" else "Open Locust report"
                st.link_button(
                    label,
                    _streamlit_static_url("locust_report.html"),
                    type="secondary",
                )
            else:
                st.caption("Locust report not available for the last run.")

    st.markdown('<div style="height:12px"></div>', unsafe_allow_html=True)

    with st.container(border=True):
        _section_label("REPORTING DASHBOARD")
        st.markdown(
            '<p style="font-size:0.78rem;color:rgba(248,249,251,0.5);margin:0 0 0.75rem 0;">'
            "Requires the <strong>Allure CLI</strong> on your PATH (e.g. <code>brew install allure</code> on macOS)."
            "</p>",
            unsafe_allow_html=True,
        )
        cache_buster = int(time.time())
        top1, top2 = st.columns([1, 1])
        with top1:
            gen_all = st.button(
                "Generate framework reports",
                type="secondary",
                disabled=bool(st.session_state.running),
            )
        with top2:
            st.caption("Reports are generated per framework (no unified merge).")

        if gen_all:
            with st.spinner("Generating Allure reports..."):
                out = _report_svc.generate_framework_reports()
            ok_any = any(v[0] for v in out.values())
            if ok_any:
                st.success("Allure reports generated.")
            else:
                st.error("Allure generation failed. Check logs for details.")

        st.markdown('<div style="height:8px"></div>', unsafe_allow_html=True)
        grid = ReportService.available_allure_reports()
        if grid:
            cols = st.columns(min(4, max(1, len(grid))))
            for i, fw in enumerate(grid):
                with cols[i % len(cols)]:
                    st.link_button(
                        f"View {fw}",
                        _streamlit_static_url(f"allure_reports/{fw}/index.html?t={cache_buster}"),
                        type="secondary",
                    )

    st.markdown('<div style="height:12px"></div>', unsafe_allow_html=True)

    with st.container(border=True):
        _section_label("EXPORTS & METRICS")
        with st.expander("Export data", expanded=False):
            ex1, ex2 = st.columns(2)
            with ex1:
                zip_clicked = st.button(
                    "Build ZIP",
                    type="secondary",
                    disabled=bool(st.session_state.running),
                    key="analytics_zip_btn",
                )
            with ex2:
                metrics_clicked = st.button(
                    "Generate metrics.json",
                    type="secondary",
                    disabled=bool(st.session_state.running),
                    key="analytics_metrics_btn",
                )

            if zip_clicked:
                try:
                    zip_path = _report_svc.make_report_zip(base_name="allure-report")
                    st.session_state["report_zip_path"] = str(zip_path)
                    st.success(f"ZIP created: {zip_path.name}")
                except Exception as exc:
                    st.error(f"ZIP creation failed: {exc}")

            zip_path_str = st.session_state.get("report_zip_path")
            if zip_path_str:
                zp = Path(zip_path_str)
                if zp.exists():
                    st.download_button(
                        "Download ZIP file",
                        data=zp.read_bytes(),
                        file_name=zp.name,
                        mime="application/zip",
                        type="secondary",
                        key="analytics_dl_zip_btn",
                    )

            if metrics_clicked:
                try:
                    m = MetricsService.parse_allure_results_dir(paths.results_dir)
                    out = write_metrics_json(m, out_path=artifacts_root / "metrics.json")
                    st.success(f"Wrote {out}")
                except Exception as exc:
                    st.error(f"Metrics generation failed: {exc}")

with tab_history:
    st.subheader("Run history")
    st.caption(
        "Runs are grouped by session. Expand a row to open the reports captured for that run."
    )

    if st.button("Refresh history", type="secondary", key="history_refresh_btn"):
        st.rerun()

    try:
        sessions = list_run_sessions(limit=30)
    except Exception:
        sessions = []

    if not sessions:
        st.info("No run history yet. Complete a run to record metadata and snapshots.")
    else:
        for s in sessions:
            ts = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(float(s.created_at)))
            status_str = str(getattr(s, "status", "") or "")
            summary = f"status={status_str}" if status_str else f"rc={int(s.returncode)}"
            if s.total_tests is not None and s.passed is not None:
                extra = []
                extra.append(f"{int(s.passed)}/{int(s.total_tests)} passed")
                if getattr(s, "failed", None) is not None:
                    extra.append(f"{int(getattr(s, 'failed'))} failed")
                if getattr(s, "skipped", None) is not None:
                    extra.append(f"{int(getattr(s, 'skipped'))} skipped")
                if getattr(s, "broken", None) is not None:
                    extra.append(f"{int(getattr(s, 'broken'))} broken")
                summary += " · " + " · ".join(extra)
            if s.health_pct is not None:
                summary += f" · health={float(s.health_pct):.1f}%"

            title = f"{ts} · {s.run_id[:8]}… · {summary}"
            with st.expander(title):
                cache_buster = int(time.time())

                # Allure Server link (per run_id project) when available.
                if (s.status == RunStatus.COMPLETED) or (str(getattr(s, "status", "")) == str(RunStatus.COMPLETED)):
                    allure_base = (os.getenv("ALLURE_SERVER_URL") or "http://localhost:5050").rstrip("/")
                    st.link_button(
                        "Open Allure Server report",
                        f"{allure_base}/allure-docker-service/projects/{s.run_id}/reports/latest/index.html",
                        type="secondary",
                    )

                # Only show buttons for reports that exist for this session.
                order = [
                    ("pytest", "View Pytest"),
                    ("behave_native", "View Behave"),
                    ("locust", "View Locust"),
                    ("behavex", "View BehaveX"),
                ]
                present = [(k, label) for (k, label) in order if k in s.links_under_static]
                if present:
                    cols = st.columns(len(present))
                    for i, (k, label) in enumerate(present):
                        with cols[i]:
                            raw_link = s.links_under_static[k]
                            if raw_link.startswith("http://") or raw_link.startswith("https://"):
                                sep = "&" if "?" in raw_link else "?"
                                hist_btn_url = f"{raw_link}{sep}t={cache_buster}"
                            else:
                                hist_btn_url = _streamlit_static_url(f"{raw_link}?t={cache_buster}")
                            st.link_button(
                                label,
                                hist_btn_url,
                                type="primary",
                            )

                rr = get_run(run_id=s.run_id)
                if rr is not None:
                    st.markdown("**Test summary**")
                    cols = st.columns(4)
                    cols[0].metric("Passed", int(rr.passed) if rr.passed is not None else 0)
                    cols[1].metric("Failed", int(rr.failed) if getattr(rr, "failed", None) is not None else 0)
                    cols[2].metric("Skipped", int(rr.skipped) if getattr(rr, "skipped", None) is not None else 0)
                    cols[3].metric("Broken", int(rr.broken) if getattr(rr, "broken", None) is not None else 0)

                files = snapshot_files_for_download(record=rr) if rr else []
                with st.expander("Download Artifacts", expanded=False):
                    if files:
                        for i, (label, payload) in enumerate(files):
                            st.download_button(
                                label,
                                data=payload,
                                file_name=f"{s.run_id[:8]}_{label.replace('/', '_')}",
                                key=f"hist_row_dl_{s.run_id}_{i}",
                                type="secondary",
                            )
                    else:
                        st.caption("No captured artifacts for this run.")

    st.divider()
    st.subheader("Allure folder history (archives)")
    archive_root = artifacts_root / "allure-results-archive"
    history = MetricsService.list_run_history(archive_root=archive_root, current_results_dir=paths.results_dir)
    if history:
        rows = []
        for m in history:
            rate = (m.passed / m.total_tests) if m.total_tests else 0.0
            rows.append(
                {
                    "timestamp": m.timestamp,
                    "run_id": m.run_id or "",
                    "total": m.total_tests,
                    "passed": m.passed,
                    "failed": m.failed,
                    "broken": m.broken,
                    "skipped": m.skipped,
                    "pass_rate": round(rate * 100.0, 2),
                    "duration_ms": m.duration_ms,
                }
            )
        st.dataframe(rows, width="stretch", height=420)
    else:
        st.info("No Allure results found yet.")

with tab_integrations:
    st.subheader("Enterprise integrations")
    st.caption(
        f"Secrets can be set in `{_APP_ROOT / '.env'}` (see `.env.example`). "
        "Values below override the environment for this session when non-empty."
    )

    try:
        cfg_ok = integration_status_from_env()
    except Exception:
        cfg_ok = {"influx_configured": False, "prometheus_configured": False}

    influx_ready = bool(cfg_ok.get("influx_configured")) or (
        bool(str(st.session_state.get("influx_url") or "").strip())
        and bool(str(st.session_state.get("influx_token") or "").strip())
        and bool(str(st.session_state.get("influx_org") or "").strip())
        and bool(str(st.session_state.get("influx_bucket") or "").strip())
    )
    prom_ready = bool(cfg_ok.get("prometheus_configured")) or bool(
        str(st.session_state.get("prometheus_pushgateway_url") or "").strip()
    )

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**InfluxDB**")
        if influx_ready:
            st.caption("Config: credentials available (.env and/or form).")
        else:
            st.caption("Config: set `INFLUXDB_*` in `.env` or fill the form.")
        if st.session_state.get("influx_test_ok") is True:
            st.caption("Last test: connected.")
        elif st.session_state.get("influx_test_ok") is False:
            st.caption("Last test: disconnected.")
        else:
            st.caption("Last test: not run yet.")
        st.toggle(
            "Enable InfluxDB sync (auto after each run)",
            key="auto_push_influx",
        )

        st.text_input("InfluxDB URL", key="influx_url")
        st.text_input("Org", key="influx_org")
        st.text_input("Bucket", key="influx_bucket")
        st.text_input("Token", type="password", key="influx_token")

        b1, b2 = st.columns(2)
        with b1:
            if st.button("Test InfluxDB connection", disabled=bool(st.session_state.running), key="test_influx_btn"):
                try:
                    ok_t, msg_t = test_influxdb_connection(
                        url=st.session_state.get("influx_url") or None,
                        token=st.session_state.get("influx_token") or None,
                        org=st.session_state.get("influx_org") or None,
                    )
                    st.session_state["influx_test_ok"] = ok_t
                    if ok_t:
                        st.toast(msg_t)
                    else:
                        st.toast(msg_t)
                except Exception as exc:
                    st.session_state["influx_test_ok"] = False
                    st.toast(f"InfluxDB test failed: {exc}")
        with b2:
            if st.button("Push metrics now (InfluxDB)", disabled=bool(st.session_state.running), key="push_influx_btn"):
                try:
                    em = MetricsService.extract_best(report_dir=paths.report_dir, results_dir=paths.results_dir)
                    if em is None:
                        st.error("No Allure data to push. Run tests or generate the Allure report first.")
                    else:
                        rm = to_run_metrics(
                            em, run_id=MetricsService.parse_allure_results_dir(paths.results_dir).run_id
                        )
                        ok_push, msg_push = push_to_influxdb(
                            rm,
                            url=st.session_state.get("influx_url") or None,
                            token=st.session_state.get("influx_token") or None,
                            org=st.session_state.get("influx_org") or None,
                            bucket=st.session_state.get("influx_bucket") or None,
                        )
                        if ok_push:
                            st.success(msg_push)
                        else:
                            st.error(msg_push)
                except Exception as exc:
                    st.error(f"Push failed: {exc}")

    with c2:
        st.markdown("**Prometheus (Pushgateway)**")
        if prom_ready:
            st.caption("Config: Pushgateway URL set (.env and/or form).")
        else:
            st.caption("Config: set `PROMETHEUS_PUSHGATEWAY_URL` in `.env` or below.")
        if st.session_state.get("prometheus_test_ok") is True:
            st.caption("Last test: connected.")
        elif st.session_state.get("prometheus_test_ok") is False:
            st.caption("Last test: disconnected.")
        else:
            st.caption("Last test: not run yet.")
        st.toggle(
            "Enable Prometheus push (auto after each run)",
            key="auto_push_prometheus",
        )

        st.text_input(
            "Pushgateway URL",
            help="Example: http://localhost:9091",
            key="prometheus_pushgateway_url",
        )

        b3, b4 = st.columns(2)
        with b3:
            if st.button("Test Pushgateway", disabled=bool(st.session_state.running), key="test_prom_btn"):
                try:
                    ok_t, msg_t = test_prometheus_pushgateway(
                        pushgateway_url=st.session_state.get("prometheus_pushgateway_url") or None
                    )
                    st.session_state["prometheus_test_ok"] = ok_t
                    if ok_t:
                        st.toast(msg_t)
                    else:
                        st.toast(msg_t)
                except Exception as exc:
                    st.session_state["prometheus_test_ok"] = False
                    st.toast(f"Prometheus test failed: {exc}")
        with b4:
            if st.button("Push metrics now (Prometheus)", disabled=bool(st.session_state.running), key="push_prom_btn"):
                try:
                    em = MetricsService.extract_best(report_dir=paths.report_dir, results_dir=paths.results_dir)
                    if em is None:
                        st.error("No Allure data to push. Run tests or generate the Allure report first.")
                    else:
                        rm = to_run_metrics(
                            em, run_id=MetricsService.parse_allure_results_dir(paths.results_dir).run_id
                        )
                        ok_push, msg_push = push_to_prometheus(
                            rm,
                            pushgateway_url=st.session_state.get("prometheus_pushgateway_url") or None,
                        )
                        if ok_push:
                            st.success(msg_push)
                        else:
                            st.error(msg_push)
                except Exception as exc:
                    st.error(f"Push failed: {exc}")

    with st.expander("Environment checklist"):
        missing = []
        if not os.getenv("INFLUXDB_TOKEN") and not st.session_state.get("influx_token"):
            missing.append("INFLUXDB_TOKEN (or enter Token in the form above)")
        if not os.getenv("INFLUXDB_URL") and not st.session_state.get("influx_url"):
            missing.append("INFLUXDB_URL")
        if not os.getenv("PROMETHEUS_PUSHGATEWAY_URL") and not st.session_state.get("prometheus_pushgateway_url"):
            missing.append("PROMETHEUS_PUSHGATEWAY_URL (optional)")
        if missing:
            st.warning("Optional gaps for full automation: " + "; ".join(missing))
        else:
            st.success("Core keys appear present for this session.")

if st.session_state.running:
    time.sleep(0.2)
    st.rerun()
