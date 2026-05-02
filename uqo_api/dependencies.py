from __future__ import annotations

from uqo_api.execution_manager import ExecutionManager

_MANAGER = ExecutionManager()


def get_execution_manager() -> ExecutionManager:
    return _MANAGER
