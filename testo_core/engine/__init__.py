"""Subprocess orchestrator: pure execution engine with no terminal dependencies.

``testo_core.engine`` consumes :class:`testo_core.config.schema.Plan` objects
and produces :class:`PlanResult` (via the :func:`run_plan` entry-point).  It
must never import from ``testo_core.cli`` or ``testo_core.reporting``.
"""

from testo_core.engine.events import (
    EngineEvent,
    PlanFinished,
    PlanStarted,
    StageFinished,
    StageOutputChunk,
    StageStarted,
)
from testo_core.engine.exit_codes import EngineExitCode, classify_exit_code
from testo_core.engine.result import PlanResult, StageResult

__all__ = [
    "EngineEvent",
    "EngineExitCode",
    "PlanFinished",
    "PlanResult",
    "PlanStarted",
    "StageFinished",
    "StageOutputChunk",
    "StageResult",
    "StageStarted",
    "classify_exit_code",
]
