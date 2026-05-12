# Phase 3 Release Checklist (Unified Dashboard)

This checklist gates rollout of the unified dashboard as the primary React entrypoint.

## 1) Packaging and install baseline

- `python3 -m pip install -U pip`
- `python3 -m venv .venv`
- `. .venv/bin/activate`
- `python -m pip install -e '.[dev]'`
- `python -m build`

## 2) Dashboard backend and API contracts

- `python -m pytest -q --no-cov tests/unit/testo_core/test_dashboard_service.py`
- `python -m pytest -q --no-cov tests/contract/api/test_dashboard_contract.py`

## 3) Existing API compatibility gate

- `python -m pytest -q --no-cov tests/contract/api/test_runs_contract.py tests/contract/api/test_history_contract.py tests/contract/api/test_analytics_contract.py`

## 4) CLI/CI/Ghost compatibility gate

- `python -m pytest -q --no-cov tests/contract/testo_core/test_cli_contract.py tests/contract/testo_core/test_ghost_summary_contract.py tests/contract/testo_core/test_ghost_ndjson_contract.py`

## 5) Frontend gate

- `npm --prefix frontend ci`
- `npm --prefix frontend run test`
- `npm --prefix frontend run test:e2e`

## 6) Dashboard behavior checks

- Open `/` and verify dashboard headline cards render health/pass-fail/duration immediately.
- Verify trend badges communicate improvement/regression/unknown semantics.
- Verify one-click drill-down links:
  - latest run details (`/runs/:runId`)
  - compare view (`/compare?...`)
  - report links (Allure/Locust/Behave) where available.
- Verify degraded-data behavior:
  - `n/a` display for missing values
  - degraded banner when `data_freshness.degraded=true`
  - unavailable/unknown report links do not crash the page.

## 7) Documentation gate

Ensure these are updated and internally consistent:

- `README.md`
- `ARCHITECTURE.md`
- `docs/release_checklist_phase3_unified_dashboard.md`

## 8) Go / No-Go criteria

- **Go**:
  - all commands above exit `0`
  - `/api/v1/dashboard/overview` and `/api/v1/dashboard/runs/recent` return typed payloads
  - existing `/api/v1/runs*`, `/api/v1/analytics/delta`, and CLI/CI/Ghost contracts remain green
  - React `/` renders unified dashboard and drill-down links work
- **No-Go**:
  - any contract regression on existing API or CLI/CI/Ghost outputs
  - dashboard endpoint missing typed sections or degraded/null handling
  - dashboard rollout breaks existing routes (`/execution`, `/history`, `/compare`, `/runs/:runId`)
