"""Manage the Phase 3.5 sandbox Mock API (uvicorn) lifecycle."""

from __future__ import annotations

import atexit
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

MOCK_HOST = "0.0.0.0"
MOCK_PORT = 8000
MOCK_BASE_URL = f"http://127.0.0.1:{MOCK_PORT}"

_PROC: Optional[subprocess.Popen[bytes]] = None


def orchestrator_root() -> Path:
    return Path(__file__).resolve().parents[1]


def sample_target_repo() -> Path:
    return orchestrator_root() / "sample_target_repo"


def is_mock_api_responding(*, timeout_s: float = 1.0) -> bool:
    try:
        import requests

        r = requests.get(f"{MOCK_BASE_URL}/", timeout=timeout_s)
        return r.status_code == 200
    except Exception:
        return False


def _terminate_process(proc: subprocess.Popen[bytes]) -> None:
    if proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=8)
    except subprocess.TimeoutExpired:
        proc.kill()
        try:
            proc.wait(timeout=5)
        except Exception:
            pass


def stop_sandbox_if_managed() -> None:
    global _PROC
    if _PROC is None:
        return
    _terminate_process(_PROC)
    _PROC = None


def is_managed_process_alive() -> bool:
    global _PROC
    if _PROC is None:
        return False
    return _PROC.poll() is None


def start_sandbox_if_needed() -> tuple[bool, str]:
    """
    Start uvicorn for mock_api if nothing is listening on MOCK_PORT.
    Returns (started_or_already_running, message).
    """
    global _PROC

    if is_mock_api_responding():
        return True, f"Mock API already running at {MOCK_BASE_URL}"

    cwd = sample_target_repo()
    if not (cwd / "mock_api.py").exists():
        return False, f"Missing {cwd / 'mock_api.py'}"

    # If port is in use but not responding like our API, avoid clobbering unknown processes.
    if _port_in_use(MOCK_PORT) and not is_mock_api_responding(timeout_s=0.5):
        return False, f"Port {MOCK_PORT} is in use but did not respond like the Mock API."

    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "mock_api:app",
        "--host",
        MOCK_HOST,
        "--port",
        str(MOCK_PORT),
    ]
    env = os.environ.copy()
    env.setdefault("PYTHONUNBUFFERED", "1")

    _PROC = subprocess.Popen(
        cmd,
        cwd=str(cwd.resolve()),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
    )

    deadline = time.time() + 15.0
    while time.time() < deadline:
        if _PROC.poll() is not None:
            err = ""
            if _PROC.stderr:
                try:
                    err = _PROC.stderr.read().decode("utf-8", errors="replace")[:2000]
                except Exception:
                    err = "(could not read stderr)"
            return False, f"Mock API exited early (code {_PROC.returncode}). {err}"

        if is_mock_api_responding():
            return True, f"Started Mock API at {MOCK_BASE_URL}"

        time.sleep(0.2)

    stop_sandbox_if_managed()
    return False, "Timed out waiting for Mock API to become ready."


def _port_in_use(port: int) -> bool:
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.25)
        return s.connect_ex(("127.0.0.1", port)) == 0


def _atexit_cleanup() -> None:
    stop_sandbox_if_managed()


atexit.register(_atexit_cleanup)
