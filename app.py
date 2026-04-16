from __future__ import annotations

import queue
import threading
import time
from pathlib import Path
from typing import Optional

import streamlit as st

from engine.command_builders import RunConfig, TestType, coerce_path
from engine.runners import LogEvent, RunResult, default_artifacts_root, run_streaming, validate_target_repo


def _init_state() -> None:
    st.session_state.setdefault("running", False)
    st.session_state.setdefault("log_lines", [])
    st.session_state.setdefault("log_max_lines", 2000)
    st.session_state.setdefault("events_q", None)  # type: ignore[assignment]
    st.session_state.setdefault("worker", None)  # type: ignore[assignment]
    st.session_state.setdefault("last_result", None)  # type: ignore[assignment]


def _append_line(line: str) -> None:
    st.session_state.log_lines.append(line)
    max_lines = int(st.session_state.log_max_lines)
    if len(st.session_state.log_lines) > max_lines:
        st.session_state.log_lines = st.session_state.log_lines[-max_lines:]


def _start_worker(cfg: RunConfig) -> None:
    events_q: queue.Queue[LogEvent | RunResult] = queue.Queue()

    def worker() -> None:
        gen = run_streaming(cfg, artifacts_root=default_artifacts_root())
        try:
            while True:
                ev = next(gen)
                events_q.put(ev)
        except StopIteration as e:
            result = e.value
            if result is not None:
                events_q.put(result)

    t = threading.Thread(target=worker, daemon=True)
    st.session_state.events_q = events_q
    st.session_state.worker = t
    st.session_state.running = True
    st.session_state.last_result = None
    t.start()


def _drain_events() -> None:
    q: Optional[queue.Queue] = st.session_state.events_q
    if not q:
        return

    drained_any = False
    while True:
        try:
            item = q.get_nowait()
        except queue.Empty:
            break

        drained_any = True
        if isinstance(item, RunResult):
            st.session_state.last_result = item
            st.session_state.running = False
            continue

        # LogEvent
        prefix = ""
        if item.stream == "stderr":
            prefix = "[stderr] "
        elif item.stream == "meta":
            prefix = ""
        _append_line(prefix + item.line.rstrip("\n"))

    # If we're still running but got nothing new, keep UI ticking.
    _ = drained_any


st.set_page_config(page_title="Unified Quality Orchestration", layout="wide")
_init_state()

st.title("Unified Quality Orchestration & Reporting Dashboard")
st.caption("Streamlit orchestrator — zero-touch wrapper; runs tools via subprocess in the target repo.")

with st.sidebar:
    st.subheader("Run configuration")

    target_repo_str = st.text_input(
        "Target repository path",
        value=str(st.session_state.get("target_repo", "")),
        placeholder="/abs/path/to/test-repo or ./relative/path",
        disabled=bool(st.session_state.running),
    )
    st.session_state["target_repo"] = target_repo_str

    test_type = st.selectbox(
        "Test type",
        options=[t.value for t in TestType],
        index=0,
        disabled=bool(st.session_state.running),
    )

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
        value=int(st.session_state.log_max_lines),
        step=200,
        key="log_max_lines",
        disabled=bool(st.session_state.running),
    )

    col_a, col_b = st.columns(2)
    with col_a:
        run_clicked = st.button("Run", type="primary", disabled=bool(st.session_state.running))
    with col_b:
        clear_clicked = st.button("Clear console", disabled=bool(st.session_state.running))

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
        # Minimal parsing: split on whitespace. Phase 2 can improve quoting.
        argv_extra = [a for a in extra_args.split() if a.strip()]
        cfg = RunConfig(
            test_type=TestType(test_type),
            target_repo=target_repo,
            shared_allure_results_dir=Path("artifacts/allure-results"),
            pytest_args=argv_extra if test_type == TestType.PYTEST.value else (),
            behavex_args=argv_extra if test_type == TestType.BEHAVEX.value else (),
            locust_args=argv_extra if test_type == TestType.LOCUST.value else (),
        )
        _append_line(f"Starting run: {cfg.test_type.value} in {cfg.target_repo}")
        _start_worker(cfg)

_drain_events()

col1, col2 = st.columns([2, 1], gap="large")

with col1:
    st.subheader("Live output")
    console_text = "\n".join(st.session_state.log_lines)
    st.code(console_text or "(no output yet)", language="text")

with col2:
    st.subheader("Run status")
    st.write(f"**Running:** {bool(st.session_state.running)}")
    st.write(f"**Artifacts:** `{default_artifacts_root()}`")

    if st.session_state.last_result is not None:
        rr: RunResult = st.session_state.last_result
        st.success(f"Finished with exit code {rr.returncode}")
        st.json(
            {
                "returncode": rr.returncode,
                "duration_s": round(rr.finished_at - rr.started_at, 3),
                "cwd": str(rr.command.cwd),
                "argv": rr.command.argv,
                "allure_results_dir": str(rr.command.env.get("UQO_SHARED_ALLURE_RESULTS_DIR", "")),
            }
        )
    elif st.session_state.running:
        st.info("Process is running. Logs will stream below.")

# Keep the UI updating while a background run is active.
if st.session_state.running:
    time.sleep(0.2)
    st.rerun()

