from __future__ import annotations

from uqo_api.execution_manager import ExecutionManager
from uqo_core.services.ai.integration_settings import InMemoryAiSettingsStore
from uqo_core.services.failure_analysis_service import FailureAnalysisService

_MANAGER = ExecutionManager()
_AI_SETTINGS_STORE = InMemoryAiSettingsStore()
_FAILURE_ANALYSIS_SERVICE = FailureAnalysisService(settings_store=_AI_SETTINGS_STORE)


def get_execution_manager() -> ExecutionManager:
    return _MANAGER


def get_ai_settings_store() -> InMemoryAiSettingsStore:
    return _AI_SETTINGS_STORE


def get_failure_analysis_service() -> FailureAnalysisService:
    return _FAILURE_ANALYSIS_SERVICE
