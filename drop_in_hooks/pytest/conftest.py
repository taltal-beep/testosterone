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


def pytest_configure(_config: pytest.Config) -> None:
    """
    Zero-touch metadata injection.

    This module is intended to be loaded explicitly by the orchestrator via:
      PYTEST_ADDOPTS="-p drop_in_hooks.pytest.conftest"
    """
    allure = _safe_allure_import()
    if allure is None:
        return

    for k, v in _metadata().items():
        if v:
            allure.dynamic.parameter(k, v)


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
