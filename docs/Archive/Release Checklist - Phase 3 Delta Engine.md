# Phase 3 Release Checklist (Delta Comparison Engine)

This checklist gates the merge of Phase 3 delta analytics across core, API, and React.

> **Gate executed:** 2026-06-24

## 1) Packaging and install baseline

- [x] `python3 -m pip install -U pip`
- [x] `python3 -m pip install -e '.[dev]'`
- [x] `python3 -m build`

## 2) Core delta analytics tests

- [x] `python3 -m pytest -q --no-cov tests/unit/testo_core/test_delta_service.py` → passed
- [x] `python3 -m pytest -q --no-cov tests/unit/testo_core/test_run_history_unit.py` → 7 passed, 4 skipped

## 3) API contract and regression gate

- [x] `python3 -m pytest -q --no-cov tests/contract/api/test_analytics_contract.py` → 4 passed
- [x] `python3 -m pytest -q --no-cov tests/contract/api/test_runs_contract.py tests/contract/api/test_history_contract.py` → 4 passed

## 4) CLI/CI contract guard

- [x] `python3 -m pytest -q --no-cov tests/contract/testo_core/test_cli_contract.py tests/contract/testo_core/test_ghost_summary_contract.py tests/contract/testo_core/test_ghost_ndjson_contract.py` → passed

## 5) Frontend gate

- [x] `npm --prefix frontend ci`
- [x] `npm --prefix frontend run test` → 6 files, 8 tests passed
- [x] `npm --prefix frontend run test:e2e` → 1 test passed

## 6) Policy and docs gate

Confirm these documents are updated and internally consistent:

- [x] `docs/delta_comparison_policy.md`
- [x] `README.md`
- [x] `ARCHITECTURE.md`
- [x] `docs/release_checklist_phase3_delta_engine.md`

## 7) Go/No-Go criteria

- [x] **Go**:
  - [x] All commands exit with `0`.
  - [x] Existing `/api/v1/runs*` endpoints remain backward-compatible.
  - [x] `GET /api/v1/analytics/delta` returns typed metrics and status-summary payload.
  - [x] React compare page shows loading/error/empty/success states with clear labels. *(verified — shows run selectors and empty-state prompt)*
- [x] **No-Go** — none triggered:
  - [x] No regression in existing API or CLI/CI contract suites.
  - [x] No mismatch between implementation and `docs/delta_comparison_policy.md`.
