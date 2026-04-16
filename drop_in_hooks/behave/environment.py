from __future__ import annotations

import os
import platform
import socket
from pathlib import Path


def _safe_allure_import():
    try:
        import allure  # type: ignore
    except Exception:  # pragma: no cover
        return None
    return allure


def _force_shared_allure_dir() -> Path | None:
    raw = os.environ.get("UQO_SHARED_ALLURE_RESULTS_DIR", "").strip()
    if not raw:
        return None

    p = Path(raw).expanduser().resolve()
    p.mkdir(parents=True, exist_ok=True)

    # Best-effort: set common env vars used by Allure formatters / integrations.
    os.environ["ALLURE_RESULTS_DIRECTORY"] = str(p)
    os.environ["ALLURE_OUTPUT_FOLDER"] = str(p)
    os.environ["ALLURE_DIR"] = str(p)

    return p


def before_scenario(context, scenario):  # noqa: ARG001
    results_dir = _force_shared_allure_dir()

    allure = _safe_allure_import()
    if allure is None:
        return

    if results_dir is not None:
        allure.dynamic.parameter("UQO_SHARED_ALLURE_RESULTS_DIR", str(results_dir))

    allure.dynamic.parameter("UQO_RUN_ID", os.environ.get("UQO_RUN_ID", ""))
    allure.dynamic.parameter("python", platform.python_version())
    allure.dynamic.parameter("platform", platform.platform())
    allure.dynamic.parameter("hostname", socket.gethostname())
    allure.dynamic.parameter("cwd", os.getcwd())


def after_scenario(context, scenario):  # noqa: ARG001
    # Placeholder for future: scenario-level attachments / diagnostics.
    return
