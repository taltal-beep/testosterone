"""Per-framework command builders consumed by :mod:`testo_core.engine.executor`.

Each adapter implements the :class:`FrameworkAdapter` protocol with a tiny,
side-effect-free :meth:`build_argv` plus a :meth:`results_subdir` hint that
the orchestrator uses to lay out per-stage Allure result trees.
"""

from testo_core.frameworks.base import FrameworkAdapter, get_adapter
from testo_core.frameworks.behave_adapter import BehaveAdapter
from testo_core.frameworks.behavex_adapter import BehaveXAdapter
from testo_core.frameworks.pytest_adapter import PytestAdapter

__all__ = [
    "BehaveAdapter",
    "BehaveXAdapter",
    "FrameworkAdapter",
    "PytestAdapter",
    "get_adapter",
]
