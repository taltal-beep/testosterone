"""``testo`` CLI package.

The new Typer-based CLI lives in :mod:`testo_core.cli.app`; the legacy
argparse-based entry-point (kept for backwards compatibility) lives in
:mod:`testo_core.cli.legacy`.

To keep ``testo --help`` fast we expose the legacy attributes via PEP 562
lazy loading.  Existing tests that do ``from testo_core import cli`` and
then ``cli.main`` / ``cli.HeadlessEngineService`` continue to work, but the
import is deferred until first access.
"""

from __future__ import annotations

from typing import Any

# Names re-exported from the legacy module for backwards compatibility.
# Order matches the historical ``testo_core.cli`` module surface.
_LEGACY_ATTRS = frozenset(
    {
        "SUMMARY_SCHEMA_KEYS",
        "NDJSON_EVENT_TYPES",
        "_event_to_ndjson",
        "main",
        "load_run_specs_from_yaml",
        "HeadlessEngineService",
        "ConfigValidationError",
        "InfrastructureRuntimeError",
        "EngineExitCode",
        "EngineRequest",
        "SCHEMA_VERSION",
        "detect_ci_provenance",
        "resolve_ghost_mode",
        "HeadlessEngineError",
        "os",
    }
)


def __getattr__(name: str) -> Any:
    if name in _LEGACY_ATTRS:
        from testo_core.cli import legacy

        value = getattr(legacy, name)
        globals()[name] = value
        return value
    raise AttributeError(f"module 'testo_core.cli' has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(_LEGACY_ATTRS)
