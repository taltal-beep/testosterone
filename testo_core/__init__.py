"""Unified Quality Orchestration — public API for the ``testo-core`` distribution.

The new narrow surface is :class:`testo_core.config.Plan` /
:class:`testo_core.config.Stage` plus :func:`testo_core.engine.run_plan`.
The legacy attributes (``RunConfig``, ``TestType``, ``run_streaming`` …) are
preserved via PEP 562 lazy loading so ``import testo_core`` does NOT pull in
SQLAlchemy / Docker / Streamlit until a consumer actually touches them.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as pkg_version
from typing import Any

# Narrow, fast-loading facade for the new CLI-first world.
from testo_core.config import Plan, Stage, TestosteroneConfig  # noqa: F401
from testo_core.engine.exit_codes import EngineExitCode  # noqa: F401

# Legacy names that used to be re-exported eagerly from this module.  Each
# entry maps the exported attribute to its real module path.  PEP 562
# :func:`__getattr__` resolves them on first access so ``import testo_core``
# stays under ~50 ms even when SQLAlchemy is installed.
_LEGACY_EXPORTS: dict[str, str] = {
    "RunConfig": "testo_core.command_builders",
    "TestType": "testo_core.command_builders",
    "build_command": "testo_core.command_builders",
    "coerce_path": "testo_core.command_builders",
    "get_repository": "testo_core.db",
    "reset_repository_cache": "testo_core.db",
    "create_db_and_tables": "testo_core.db_config",
    "get_engine": "testo_core.db_config",
    "reset_engine_cache": "testo_core.db_config",
    "resolve_database_url": "testo_core.db_config",
    "create_plugin_manager": "testo_core.orchestrator",
    "RunRecord": "testo_core.repository.models",
    "RunStatus": "testo_core.repository.models",
    "LogEvent": "testo_core.runners",
    "RunResult": "testo_core.runners",
    "UQO_DONE_MARKER": "testo_core.runners",
    "run_audit_streaming": "testo_core.runners",
    "run_streaming": "testo_core.runners",
    "validate_target_repo": "testo_core.runners",
    "BaseRunnerSpec": "testo_core.specs",
    "hookimpl": "testo_core.specs",
}


__all__ = [
    "EngineExitCode",
    "Plan",
    "Stage",
    "TestosteroneConfig",
    *_LEGACY_EXPORTS.keys(),
]


def __getattr__(name: str) -> Any:
    """PEP 562 lazy attribute resolver for backwards-compatible legacy names."""
    module_path = _LEGACY_EXPORTS.get(name)
    if module_path is None:
        raise AttributeError(f"module 'testo_core' has no attribute {name!r}")
    import importlib

    module = importlib.import_module(module_path)
    value = getattr(module, name)
    globals()[name] = value  # cache for subsequent accesses
    return value


def __dir__() -> list[str]:
    return sorted(__all__)


try:
    __version__ = pkg_version("testo-core")
except PackageNotFoundError:  # pragma: no cover - source tree import before install
    __version__ = "0.1.0"
