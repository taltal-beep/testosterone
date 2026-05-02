## Test layout (enterprise scaling)

This repo historically used a flat `tests/` layout. We now split tests by intent:

- `tests/unit/`: pure function + branch-matrix tests (heavy mocking)
- `tests/integration/`: component interaction / state persistence (FastAPI TestClient or managed sandbox)
- `tests/e2e/`: sequential user journeys (Allure-stepped)
- `tests/contracts/`: schema/contract enforcement (Pydantic)

### Migration map (old → new)

#### Sandbox API
- `tests/test_sandbox_api_unit.py` → `tests/unit/uqo_core/test_sandbox_api_unit.py`
- `tests/test_sandbox_api_more.py` → `tests/unit/uqo_core/test_sandbox_api_more.py`
- `tests/test_sandbox_api_terminate.py` → `tests/unit/uqo_core/test_sandbox_api_terminate.py`

#### Engine core (unit)
- `tests/test_paths.py` → `tests/unit/uqo_core/test_paths.py`
- `tests/test_paths_behave_native.py` → `tests/unit/uqo_core/test_paths_behave_native.py`
- `tests/test_command_builders_extended.py` → `tests/unit/uqo_core/test_command_builders_extended.py`
- `tests/test_integrations_unit.py` → `tests/unit/uqo_core/test_integrations_unit.py`
- `tests/test_integrations_more.py` → `tests/unit/uqo_core/test_integrations_more.py`
- `tests/test_report_generator.py` → `tests/unit/uqo_core/test_report_generator.py`
- `tests/test_report_generator_helpers.py` → `tests/unit/uqo_core/test_report_generator_helpers.py`
- `tests/test_report_generator_http.py` → `tests/unit/uqo_core/test_report_generator_http.py`
- `tests/test_report_generator_locust.py` → `tests/unit/uqo_core/test_report_generator_locust.py`
- `tests/test_report_generator_static_sync.py` → `tests/unit/uqo_core/test_report_generator_static_sync.py`
- `tests/test_report_service_more.py` → `tests/unit/uqo_core/test_report_service_more.py`
- `tests/test_run_history_unit.py` → `tests/unit/uqo_core/test_run_history_unit.py`
- `tests/test_run_history_snapshot.py` → `tests/unit/uqo_core/test_run_history_snapshot.py`
- `tests/test_result_management.py` → `tests/unit/uqo_core/test_result_management.py`
- `tests/test_event_drain.py` → `tests/unit/uqo_core/test_event_drain.py`
- `tests/test_services.py` → `tests/unit/uqo_core/test_services.py`
- `tests/test_runners_unit.py` → `tests/unit/uqo_core/test_runners_unit.py`
- `tests/test_runners_audit_mock.py` → `tests/unit/uqo_core/test_runners_audit_mock.py`
- `tests/test_runners.py` → `tests/unit/uqo_core/test_runners.py`
- `tests/test_metrics.py` → `tests/unit/uqo_core/test_metrics.py`
- `tests/test_metrics_advanced.py` → `tests/unit/uqo_core/test_metrics_advanced.py`
- `tests/test_metrics_extractor_unit.py` → `tests/unit/uqo_core/test_metrics_extractor_unit.py`
- `tests/test_metrics_extractor_more.py` → `tests/unit/uqo_core/test_metrics_extractor_more.py`
- `tests/test_defaults_and_placeholders.py` → `tests/unit/test_defaults_and_placeholders.py`
- `tests/test_isolation_integrity.py` → `tests/unit/test_isolation_integrity.py`

#### New test families (added)
- Contract tests for `sample_target_repo/mock_api.py` → `tests/contracts/`
- Stateful flow tests for sandbox API → `tests/integration/sandbox_api/`
- Sequential user journeys → `tests/e2e/sandbox_api/`

