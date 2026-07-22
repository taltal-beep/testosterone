"""Database persistence backend — upserts a RunRecord via the repository layer."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path

from testo_core.engine.result import PlanResult
from testo_core.reporting.paths import plan_artifacts_dir
from testo_core.repository.models import RunStatus

logger = logging.getLogger(__name__)

# Mirrors testo_core.run_history.ORCHESTRATOR_ROOT — the root that
# snapshot_files_for_download() resolves local (non-S3) snapshot_dir values against.
ORCHESTRATOR_ROOT = Path(__file__).resolve().parents[2]


class DbBackend:
    """Persist a :class:`PlanResult` as a :class:`RunRecord` in the database."""

    def __init__(self, artifacts_root: Path) -> None:
        self._artifacts_root = artifacts_root

    def _local_snapshot_dir(self, plan_name: str) -> str | None:
        """Relative path (from ``ORCHESTRATOR_ROOT``) to this plan's artifacts.

        ``run_history.snapshot_files_for_download`` resolves non-S3
        ``snapshot_dir`` values as ``ORCHESTRATOR_ROOT / snapshot_dir``; only
        return a value when the artifacts actually live under the repo root.
        """
        plan_dir = plan_artifacts_dir(self._artifacts_root, plan_name)
        try:
            return plan_dir.relative_to(ORCHESTRATOR_ROOT).as_posix()
        except ValueError:
            return None

    def persist(self, result: PlanResult) -> str | None:
        try:
            from testo_core.db import get_repository

            repo = get_repository()
            status = RunStatus.COMPLETED if result.exit_code == 0 else RunStatus.FAILED
            record = repo.create_run(
                status=status,
                metadata={
                    "plan": result.plan_name,
                    "test_kind": "cycle",
                    "returncode": int(result.exit_code),
                    "exit_code": int(result.exit_code),
                    "aggregate_returncode": result.aggregate_returncode,
                    "duration_s": result.duration_s,
                    "started_at": result.started_at,
                    "finished_at": result.finished_at,
                    "started_at_iso": datetime.fromtimestamp(result.started_at, tz=UTC).isoformat(),
                    "stage_count": len(result.stages),
                    "stages": [
                        {
                            "name": s.stage_name,
                            "framework": s.framework,
                            "returncode": s.returncode,
                            "duration_s": s.duration_s,
                        }
                        for s in result.stages
                    ],
                    "snapshot_dir": self._local_snapshot_dir(result.plan_name),
                    "source": "engine",
                },
            )
            return str(record.id)
        except Exception:
            logger.debug("db persistence failed for plan %s", result.plan_name, exc_info=True)
            return None
