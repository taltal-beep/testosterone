"""
Service: full-system audit orchestration entrypoints (delegates to ``testo_core.runners``).
"""

from __future__ import annotations

from collections.abc import Generator, Mapping, Sequence
from pathlib import Path

from testo_core.paths import default_artifacts_root
from testo_core.runners import LogEvent, RunResult, run_audit_streaming


class AuditService:
    """Thin façade so presentation code does not import generator internals directly."""

    @staticmethod
    def stream_audit(
        *,
        target_repo: Path,
        artifacts_root: Path | None = None,
        parent_env: Mapping[str, str] | None = None,
        pytest_args: Sequence[str] = (),
        behavex_args: Sequence[str] = (),
        native_behave_args: Sequence[str] = (),
        run_native_behave: bool = False,
    ) -> Generator[LogEvent, None, RunResult]:
        return run_audit_streaming(
            target_repo=target_repo,
            artifacts_root=artifacts_root or default_artifacts_root(),
            parent_env=parent_env,
            pytest_args=pytest_args,
            behavex_args=behavex_args,
            native_behave_args=native_behave_args,
            run_native_behave=run_native_behave,
        )
