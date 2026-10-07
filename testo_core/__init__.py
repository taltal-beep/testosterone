"""Testosterone — public API for the ``testo-core`` distribution.

The new narrow surface is :class:`testo_core.config.Plan` /
:class:`testo_core.config.Stage` plus :func:`testo_core.engine.run_plan`.
The database helpers (``get_repository``, ``RunRecord`` …) are exposed via
PEP 562 lazy loading so ``import testo_core`` does NOT pull in SQLAlchemy
until a consumer actually touches them.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as pkg_version
from typing import Any

# Narrow, fast-loading facade for the new CLI-first world.
from testo_core.config import Plan, Stage, TestosteroneConfig  # noqa: F401
from testo_core.engine.exit_codes import EngineExitCode  # noqa: F401

# Database names that used to be re-exported eagerly from this module.  Each
# entry maps the exported attribute to its real module path.  PEP 562
# :func:`__getattr__` resolves them on first access so ``import testo_core``
# stays under ~50 ms even when SQLAlchemy is installed.
_LAZY_EXPORTS: dict[str, str] = {
    "get_repository": "testo_core.repository.db",
    "reset_repository_cache": "testo_core.repository.db",
    "create_db_and_tables": "testo_core.repository.db_config",
    "get_engine": "testo_core.repository.db_config",
    "reset_engine_cache": "testo_core.repository.db_config",
    "resolve_database_url": "testo_core.repository.db_config",
    "RunRecord": "testo_core.repository.models",
    "RunStatus": "testo_core.repository.models",
}


__all__ = [
    "EngineExitCode",
    "Plan",
    "Stage",
    "TestosteroneConfig",
    *_LAZY_EXPORTS.keys(),
]


def __getattr__(name: str) -> Any:
    """PEP 562 lazy attribute resolver for the database names above."""
    module_path = _LAZY_EXPORTS.get(name)
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
