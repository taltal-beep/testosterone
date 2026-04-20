from __future__ import annotations

import os
import platform
import socket
import traceback
from typing import Any

import pytest


def _safe_allure_import():
    try:
        import allure  # type: ignore
    except Exception:  # pragma: no cover
        return None
    return allure


def _metadata() -> dict[str, str]:
    return {
        "UQO_RUN_ID": os.environ.get("UQO_RUN_ID", ""),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "hostname": socket.gethostname(),
        "cwd": os.getcwd(),
        "UQO_SHARED_ALLURE_RESULTS_DIR": os.environ.get("UQO_SHARED_ALLURE_RESULTS_DIR", ""),
    }


def pytest_configure(config: pytest.Config) -> None:
    """
    Zero-touch metadata injection.

    This module is intended to be loaded explicitly by the orchestrator via:
      PYTEST_ADDOPTS="-p drop_in_hooks.pytest_custom.conftest"
    """
    _ = config
    # Do NOT call allure.dynamic.* here: there is no active test context yet.
    # Global metadata is written in pytest_sessionfinish to environment.properties.


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_logreport(report: pytest.TestReport) -> None:
    """
    Capture failures/skips/errors and attach lightweight diagnostics.
    """
    if report.when != "call":
        return

    allure = _safe_allure_import()
    if allure is None:
        return

    if report.failed or report.outcome == "failed":
        allure.attach(
            f"nodeid={report.nodeid}\nlocation={getattr(report, 'location', '')}\nlongrepr={getattr(report, 'longrepr', '')}",
            name="pytest.failure.details",
            attachment_type=allure.attachment_type.TEXT,
        )
    elif report.skipped:
        allure.attach(
            f"nodeid={report.nodeid}\nskipped={report.longrepr}",
            name="pytest.skip.details",
            attachment_type=allure.attachment_type.TEXT,
        )


@pytest.hookimpl(tryfirst=True)
def pytest_exception_interact(node: Any, call: pytest.CallInfo, report: pytest.TestReport) -> None:
    allure = _safe_allure_import()
    if allure is None:
        return

    exc = call.excinfo
    if exc is None:
        return

    allure.attach(
        "".join(traceback.format_exception(exc.type, exc.value, exc.tb)),
        name="pytest.exception.traceback",
        attachment_type=allure.attachment_type.TEXT,
    )


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """
    Write global metadata for Allure via environment.properties.

    Allure picks up `<allure-results>/environment.properties` as run-level context.
    """
    _ = (session, exitstatus)
    config = session.config

    alluredir = None
    try:
        alluredir = config.getoption("--alluredir")
    except Exception:
        alluredir = None

    if not alluredir:
        alluredir = os.environ.get("UQO_SHARED_ALLURE_RESULTS_DIR", "")

    if not alluredir:
        return

    dir_path = os.path.abspath(os.path.expanduser(str(alluredir)))
    os.makedirs(dir_path, exist_ok=True)
    env_path = os.path.join(dir_path, "environment.properties")

    meta = _metadata()
    with open(env_path, "w", encoding="utf-8") as f:
        for k, v in meta.items():
            if v is None:
                continue
            s = str(v).replace("\n", "\\n")
            f.write(f"{k}={s}\n")
