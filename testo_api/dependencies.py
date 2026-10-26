from __future__ import annotations

from testo_api.cycle_execution_manager import CycleExecutionManager
from testo_core.services.ai.integration_settings import (
    FileBackedAiSettingsStore,
    InMemoryAiSettingsStore,
    default_ai_settings_path,
)
from testo_core.services.ask_tests import AskTestsService
from testo_core.services.failure_analysis_service import FailureAnalysisService
from testo_core.services.project_review import ProjectReviewService

_CYCLE_MANAGER = CycleExecutionManager()
_AI_SETTINGS_PATH = default_ai_settings_path()
_AI_SETTINGS_STORE: InMemoryAiSettingsStore = (
    FileBackedAiSettingsStore(_AI_SETTINGS_PATH)
    if _AI_SETTINGS_PATH is not None
    else InMemoryAiSettingsStore()
)
_FAILURE_ANALYSIS_SERVICE = FailureAnalysisService(settings_store=_AI_SETTINGS_STORE)


def get_cycle_execution_manager() -> CycleExecutionManager:
    return _CYCLE_MANAGER


def get_ai_settings_store() -> InMemoryAiSettingsStore:
    return _AI_SETTINGS_STORE


def get_failure_analysis_service() -> FailureAnalysisService:
    return _FAILURE_ANALYSIS_SERVICE


_PROJECT_REVIEW_SERVICE = ProjectReviewService(settings_store=_AI_SETTINGS_STORE)


def get_project_review_service() -> ProjectReviewService:
    return _PROJECT_REVIEW_SERVICE


_ASK_TESTS_SERVICE = AskTestsService(settings_store=_AI_SETTINGS_STORE)


def get_ask_tests_service() -> AskTestsService:
    return _ASK_TESTS_SERVICE
