"""
Service: full-system audit orchestration entrypoints (delegates to ``engine.runners``).
"""

from __future__ import annotations

from collections.abc import Generator, Mapping, Sequence
from pathlib import Path
from typing import Optional

from engine.paths import default_artifacts_root
from engine.runners import LogEvent, RunResult, run_audit_streaming


class AuditService:
    """Thin façade so presentation code does not import generator internals directly."""

    @staticmethod
    def stream_audit(
        *,
        target_repo: Path,
        artifacts_root: Path | None = None,
        parent_env: Optional[Mapping[str, str]] = None,
        pytest_args: Sequence[str] = (),
        behavex_args: Sequence[str] = (),
        locust_args: Sequence[str] = (),
        locust_users: int = 10,
        locust_spawn_rate: int = 2,
        locust_run_time: str = "1m",
        locust_only_summary: bool = True,
    ) -> Generator[LogEvent, None, RunResult]:
        return run_audit_streaming(
            target_repo=target_repo,
            artifacts_root=artifacts_root or default_artifacts_root(),
            parent_env=parent_env,
            pytest_args=pytest_args,
            behavex_args=behavex_args,
            locust_args=locust_args,
            locust_users=locust_users,
            locust_spawn_rate=locust_spawn_rate,
            locust_run_time=locust_run_time,
            locust_only_summary=locust_only_summary,
        )
