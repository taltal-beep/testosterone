"""Plan-aware configuration layer for the ``testo`` CLI.

The runtime engine consumes :class:`Plan` objects produced by this package;
it must not parse YAML itself.
"""

from testo_core.config.errors import (
    ConfigError,
    ConfigValidationError,
    PlanNotFoundError,
)
from testo_core.config.loader import discover_and_load, load_config
from testo_core.config.resolver import resolve_plan, resolve_stages_for_plan
from testo_core.config.schema import Defaults, Plan, Stage, TestosteroneConfig

__all__ = [
    "ConfigError",
    "ConfigValidationError",
    "Defaults",
    "Plan",
    "PlanNotFoundError",
    "Stage",
    "TestosteroneConfig",
    "discover_and_load",
    "load_config",
    "resolve_plan",
    "resolve_stages_for_plan",
]
