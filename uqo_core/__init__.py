"""Unified Quality Orchestration — public API for the ``uqo-core`` distribution."""

from __future__ import annotations

from .command_builders import RunConfig, TestType, build_command, coerce_path
from .db import get_repository, reset_repository_cache
from .db_config import (
    create_db_and_tables,
    get_engine,
    reset_engine_cache,
    resolve_database_url,
)
from .orchestrator import create_plugin_manager
from .repository.models import RunRecord, RunStatus
from .runners import (
    LogEvent,
    RunResult,
    UQO_DONE_MARKER,
    run_audit_streaming,
    run_streaming,
    validate_target_repo,
)
from .specs import BaseRunnerSpec, hookimpl

__all__ = [
    "BaseRunnerSpec",
    "LogEvent",
    "RunConfig",
    "RunRecord",
    "RunResult",
    "RunStatus",
    "TestType",
    "UQO_DONE_MARKER",
    "build_command",
    "coerce_path",
    "create_db_and_tables",
    "create_plugin_manager",
    "get_engine",
    "get_repository",
    "hookimpl",
    "reset_engine_cache",
    "reset_repository_cache",
    "resolve_database_url",
    "run_audit_streaming",
    "run_streaming",
    "validate_target_repo",
]

__version__ = "0.1.0"
