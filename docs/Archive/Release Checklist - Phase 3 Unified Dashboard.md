# Phase 3 Release Checklist (Unified Dashboard)

This checklist gates rollout of the unified dashboard as the primary React entrypoint.

> **Gate executed:** 2026-06-24

## 1) Packaging and install baseline

- [x] `python3 -m pip install -U pip`
- [x] `python3 -m venv .venv`
- [x] `. .venv/bin/activate`
- [x] `python -m pip install -e '.[dev]'`
- [x] `python -m build`

## 2) Dashboard backend and API contracts

- [x] `python -m pytest -q --no-cov tests/unit/testo_core/test_dashboard_service.py` → passed
- [x] `python -m pytest -q --no-cov tests/contract/api/test_dashboard_contract.py` → passed

## 3) Existing API compatibility gate

- [x] `python -m pytest -q --no-cov tests/contract/api/test_runs_contract.py tests/contract/api/test_history_contract.py tests/contract/api/test_analytics_contract.py` → passed

## 4) CLI/CI/Ghost compatibility gate

- [x] `python -m pytest -q --no-cov tests/contract/testo_core/test_cli_contract.py tests/contract/testo_core/test_ghost_summary_contract.py tests/contract/testo_core/test_ghost_ndjson_contract.py` → passed

## 5) Frontend gate

- [x] `npm --prefix frontend ci`
- [x] `npm --prefix frontend run test` → 6 files, 8 tests passed
- [x] `npm --prefix frontend run test:e2e` → 1 test passed

## 6) Dashboard behavior checks

- [x] Open `/` and verify dashboard headline cards render health/pass-fail/duration immediately. *(verified — fixed null-guard bug in DashboardPage.tsx)*
- [x] Verify trend badges communicate improvement/regression/unknown semantics.
- [x] Verify one-click drill-down links:
  - [x] latest run details (`/runs/:runId`) — renders Run ID, type, return code, AI summary section
  - [x] compare view (`/compare?...`) — renders run selectors with empty-state prompt
  - [x] report links (Allure/Locust/Behave) where available — gracefully show "state unknown" / "not available"
- [x] Verify degraded-data behavior:
  - [x] `n/a` display for missing values — Health, Failed, Pass Count correctly show `n/a`
  - [x] degraded banner when `data_freshness.degraded=true` — hidden when false (correct), guarded when true
  - [x] unavailable/unknown report links do not crash the page.

## 7) Documentation gate

Ensure these are updated and internally consistent:

- [x] `README.md`
- [x] `ARCHITECTURE.md`
- [x] `docs/release_checklist_phase3_unified_dashboard.md`

## 8) Go / No-Go criteria

- [x] **Go**:
  - [x] all commands above exit `0`
  - [x] `/api/v1/dashboard/overview` and `/api/v1/dashboard/runs/recent` return typed payloads
  - [x] existing `/api/v1/runs*`, `/api/v1/analytics/delta`, and CLI/CI/Ghost contracts remain green
  - [x] React `/` renders unified dashboard and drill-down links work
- [x] **No-Go** — none triggered:
  - [x] no contract regression on existing API or CLI/CI/Ghost outputs
  - [x] dashboard endpoint has typed sections and degraded/null handling
  - [x] dashboard rollout does not break existing routes
