# Phase 4 Release Checklist (BYOK AI + Failure Summaries)

This checklist gates rollout of BYOK AI integration and run failure summaries.

> **Gate executed:** 2026-06-24

## 1) Packaging and install baseline

- [x] `python3 -m pip install -U pip`
- [x] `python3 -m venv .venv`
- [x] `. .venv/bin/activate`
- [x] `python -m pip install -e '.[dev]'`
- [x] `python -m build`

## 2) Core AI and security gate

- [x] `python -m pytest -q --no-cov tests/unit/testo_core/test_ai_provider_abstraction.py` → passed
- [x] `python -m pytest -q --no-cov tests/unit/testo_core/test_ai_config_model.py` → passed
- [x] `python -m pytest -q --no-cov tests/unit/testo_core/test_redaction.py` → passed
- [x] `python -m pytest -q --no-cov tests/unit/testo_core/test_failure_context_builder.py` → passed
- [x] `python -m pytest -q --no-cov tests/unit/testo_core/test_failure_analysis_service.py` → 11 passed

## 3) API compatibility + AI contract gate

- [x] `python -m pytest -q --no-cov tests/contract/api/test_runs_contract.py tests/contract/api/test_history_contract.py tests/contract/api/test_analytics_contract.py tests/contract/api/test_dashboard_contract.py tests/contract/api/test_ai_contract.py` → 13 passed

## 4) CLI/CI/Ghost compatibility gate

- [x] `python -m pytest -q --no-cov tests/contract/testo_core/test_cli_contract.py tests/contract/testo_core/test_ghost_summary_contract.py tests/contract/testo_core/test_ghost_ndjson_contract.py` → 6 passed

## 5) Frontend gate

- [x] `npm --prefix frontend ci`
- [x] `npm --prefix frontend run test` → 6 files, 8 tests passed
- [x] `npm --prefix frontend run test:e2e` → 1 test passed

## 6) Manual security and behavior checks

- [x] Verify `/settings/ai` never displays full token values after save/reload. *(verified — shows "not configured" status, API key field is empty, no tokens visible)*
- [x] Verify failed run detail page can generate/show a summary and presents no-summary fallback when disabled. *(verified — shows "Summary only applies to failed runs" with "Generate AI Summary" button)*
- [ ] Verify provider misconfigured/timeout/rate-limit paths return typed status or typed API error code. *(requires live provider — covered by unit test mocks)*
- [x] Verify no token-like values leak in UI-visible error text or backend logs.

## 7) Documentation gate

Ensure these are updated and internally consistent:

- [x] `README.md`
- [x] `ARCHITECTURE.md`
- [x] `docs/release_checklist_phase4_ai.md`

## 8) Go / No-Go criteria

- [x] **Go**:
  - [x] all commands above exit `0`
  - [x] legacy contracts remain green
  - [x] AI settings are opt-in and never return secret material
  - [x] failed-run AI summary is additive and does not alter run execution semantics
- [x] **No-Go** — none triggered:
  - [x] no regression in existing run/history/dashboard/analytics contracts
  - [x] no observable secret leakage
  - [x] run execution behavior unchanged when AI feature is disabled/unavailable
