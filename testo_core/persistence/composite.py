"""Composite backend — fans out to multiple backends in sequence."""

from __future__ import annotations

import logging
from pathlib import Path

from testo_core.engine.result import PlanResult
from testo_core.persistence.json_backend import JsonBackend

logger = logging.getLogger(__name__)


class _CompositeBackend:
    """Run every registered backend; swallow individual failures."""

    def __init__(self, backends: list[object]) -> None:
        self._backends = backends

    def persist(self, result: PlanResult) -> str | None:
        run_id: str | None = None
        for backend in self._backends:
            try:
                outcome = backend.persist(result)  # type: ignore[union-attr]
            except Exception:
                logger.debug("backend %s failed", type(backend).__name__, exc_info=True)
                continue
            if isinstance(outcome, str) and outcome:
                run_id = outcome
        return run_id


def composite_backend(*, artifacts_root: Path, db: bool = True) -> _CompositeBackend:
    """Build the default persistence stack.

    Always includes :class:`JsonBackend`.  Includes :class:`DbBackend` when
    *db* is ``True`` and the repository layer is importable.
    """

    backends: list[object] = [JsonBackend(artifacts_root)]
    if db:
        try:
            from testo_core.persistence.db_backend import DbBackend
            backends.append(DbBackend(artifacts_root))
        except Exception:
            logger.debug("db backend unavailable, skipping", exc_info=True)
    return _CompositeBackend(backends)
