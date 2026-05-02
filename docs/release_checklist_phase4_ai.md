# Phase 4 Release Checklist (BYOK AI + Failure Summaries)

This checklist gates rollout of BYOK AI integration and run failure summaries.

## 1) Packaging and install baseline

- `python3 -m pip install -U pip`
- `python3 -m venv .venv`
- `. .venv/bin/activate`
- `python -m pip install -e '.[dev]'`
- `python -m build`

## 2) Core AI and security gate

- `python -m pytest -q --no-cov tests/unit/uqo_core/test_ai_provider_abstraction.py`
- `python -m pytest -q --no-cov tests/unit/uqo_core/test_ai_config_model.py`
- `python -m pytest -q --no-cov tests/unit/uqo_core/test_redaction.py`
- `python -m pytest -q --no-cov tests/unit/uqo_core/test_failure_context_builder.py`
- `python -m pytest -q --no-cov tests/unit/uqo_core/test_failure_analysis_service.py`

## 3) API compatibility + AI contract gate

- `python -m pytest -q --no-cov tests/contract/api/test_runs_contract.py tests/contract/api/test_history_contract.py tests/contract/api/test_analytics_contract.py tests/contract/api/test_dashboard_contract.py tests/contract/api/test_ai_contract.py`

## 4) CLI/CI/Ghost compatibility gate

- `python -m pytest -q --no-cov tests/contract/uqo_core/test_cli_contract.py tests/contract/uqo_core/test_ghost_summary_contract.py tests/contract/uqo_core/test_ghost_ndjson_contract.py`

## 5) Frontend gate

- `npm --prefix frontend ci`
- `npm --prefix frontend run test`
- `npm --prefix frontend run test:e2e`

## 6) Manual security and behavior checks

- Verify `/settings/ai` never displays full token values after save/reload.
- Verify failed run detail page can generate/show a summary and presents no-summary fallback when disabled.
- Verify provider misconfigured/timeout/rate-limit paths return typed status or typed API error code.
- Verify no token-like values leak in UI-visible error text or backend logs.

## 7) Documentation gate

Ensure these are updated and internally consistent:

- `README.md`
- `ARCHITECTURE.md`
- `docs/release_checklist_phase4_ai.md`

## 8) Go / No-Go criteria

- **Go**:
  - all commands above exit `0`
  - legacy contracts remain green
  - AI settings are opt-in and never return secret material
  - failed-run AI summary is additive and does not alter run execution semantics
- **No-Go**:
  - any regression in existing run/history/dashboard/analytics contracts
  - any observable secret leakage
  - run execution behavior changed when AI feature is disabled/unavailable
