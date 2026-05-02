# Phase-3 Release Checklist (Frontend Migration)

This checklist is the go/no-go gate before marking Streamlit deprecated (not removed).

## 1) Core and packaging integrity

- `python3 -m pip install -U pip`
- `python3 -m pip install -e '.[dev]'`
- `python3 -m build`
- `uqo run --help`

## 2) Phase 1/2 contract preservation

- `python3 -m pytest -q --no-cov tests/unit/uqo_core/test_cli_run.py tests/unit/uqo_core/test_headless_engine.py tests/contract/uqo_core/test_cli_contract.py`
- `python3 -m pytest -q --no-cov tests/unit/uqo_core/test_repository_sqlite.py tests/unit/uqo_core/test_repository_factory.py tests/contract/uqo_core/test_repository_contract.py`
- `python3 -m pytest -q --no-cov tests/unit/ci/test_github_action_wrapper.py tests/unit/ci/test_gitlab_template_contract.py tests/contract/ci/test_wrapper_contract.py`
- `python3 -m pytest -q --no-cov tests/contract/uqo_core/test_ghost_summary_contract.py tests/contract/uqo_core/test_ghost_ndjson_contract.py`

## 3) Backend API contracts and lifecycle

- `python3 -m pytest -q --no-cov tests/contract/api/test_runs_contract.py tests/contract/api/test_history_contract.py`
- `python3 -m pytest -q --no-cov tests/integration/api/test_run_lifecycle.py tests/integration/api/test_history_endpoints.py`

## 4) Frontend test gate

- `npm --prefix frontend ci`
- `npm --prefix frontend run test`
- `npm --prefix frontend run test:e2e`

## 5) Dual-mode rollout smoke

- `UQO_UI_MODE=dual python3 -m pytest -q --no-cov tests/integration/ui/test_dual_mode_smoke.py`
- Run one end-to-end execution from React and verify run visibility from Streamlit History.

## 6) Documentation gate

Ensure these docs are updated and accurate:

- `README.md`
- `ARCHITECTURE.md`
- `docs/migration_streamlit_to_react.md`
- `docs/release_checklist_phase3_frontend_migration.md`

## 7) Final pass criteria

- All commands above exit with `0`.
- API version prefix remains `/api/v1`.
- SSE event types remain `log`, `run_result`, `summary`.
- CLI/CI output schemas and exit-code mapping remain unchanged.
- Streamlit remains available as rollback UI until formal removal phase.
