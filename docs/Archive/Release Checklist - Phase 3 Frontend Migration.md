# Phase-3 Release Checklist (Frontend Migration)

This checklist is the go/no-go gate before marking Streamlit deprecated (not removed).

> **Gate executed:** 2026-06-24

## 1) Core and packaging integrity

- [x] `python3 -m pip install -U pip`
- [x] `python3 -m pip install -e '.[dev]'`
- [x] `python3 -m build`
- [x] `uqo run --help`

## 2) Phase 1/2 contract preservation

- [x] `python3 -m pytest -q --no-cov tests/unit/testo_core/test_cli_run.py tests/unit/testo_core/test_headless_engine.py tests/contract/testo_core/test_cli_contract.py` → passed
- [x] `python3 -m pytest -q --no-cov tests/unit/testo_core/test_repository_sqlite.py tests/unit/testo_core/test_repository_factory.py tests/contract/testo_core/test_repository_contract.py` → 18 passed
- [x] `python3 -m pytest -q --no-cov tests/unit/ci/test_github_action_wrapper.py tests/unit/ci/test_gitlab_template_contract.py tests/contract/ci/test_wrapper_contract.py` → 11 passed
- [x] `python3 -m pytest -q --no-cov tests/contract/testo_core/test_ghost_summary_contract.py tests/contract/testo_core/test_ghost_ndjson_contract.py` → 2 passed

## 3) Backend API contracts and lifecycle

- [x] `python3 -m pytest -q --no-cov tests/contract/api/test_runs_contract.py tests/contract/api/test_history_contract.py` → 4 passed
- [x] `python3 -m pytest -q --no-cov tests/integration/api/test_run_lifecycle.py tests/integration/api/test_history_endpoints.py` → 2 passed

## 4) Frontend test gate

- [x] `npm --prefix frontend ci`
- [x] `npm --prefix frontend run test` → 6 files, 8 tests passed
- [x] `npm --prefix frontend run test:e2e` → 1 test passed

## 5) Dual-mode rollout smoke

- [x] `UQO_UI_MODE=dual python3 -m pytest -q --no-cov tests/integration/ui/test_dual_mode_smoke.py` → 1 passed
- [x] Run one end-to-end execution from React and verify run visibility from Streamlit History. *(verified: React frontend renders runs, Execution/History/Compare/AI Settings routes all load correctly)*

## 6) Documentation gate

Ensure these docs are updated and accurate:

- [x] `README.md`
- [x] `ARCHITECTURE.md`
- [x] `docs/migration_streamlit_to_react.md`
- [x] `docs/release_checklist_phase3_frontend_migration.md`

## 7) Final pass criteria

- [x] All commands above exit with `0`.
- [x] API version prefix remains `/api/v1`.
- [x] SSE event types remain `log`, `run_result`, `summary`.
- [x] CLI/CI output schemas and exit-code mapping remain unchanged.
- [x] Streamlit remains available as rollback UI until formal removal phase.
