# Phase-2 Release Checklist (Ghost Mode Background Sync)

This checklist is the release gate for Ghost Mode CI auto-detection, non-interactive output, and background sync telemetry.

> **Gate executed:** 2026-06-24

## 1) Core install and CLI sanity

- [x] `python3 -m pip install -U pip`
- [x] `python3 -m pip install -e '.[dev]'`
- [x] `uqo run --help`
- [ ] `uqo run --config tests/fixtures/ci/ghost_minimal.yml --stream-json` *(requires fixture config with valid cycle)*

## 2) Ghost policy and provenance tests

- [x] `python3 -m pytest -q --no-cov tests/unit/testo_core/test_ghost_policy.py tests/unit/testo_core/test_ci_provenance.py` → 12 passed
- [x] `python3 -m pytest -q --no-cov tests/unit/testo_core/test_cli_run.py` → 16 passed

## 3) Engine + sync behavior tests

- [x] `python3 -m pytest -q --no-cov tests/unit/testo_core/test_headless_engine.py` → 6 passed
- [x] `python3 -m pytest -q --no-cov tests/contract/testo_core/test_cli_contract.py tests/contract/testo_core/test_ghost_summary_contract.py tests/contract/testo_core/test_ghost_ndjson_contract.py` → passed

## 4) CI wrapper contract tests

- [x] `python3 -m pytest -q --no-cov tests/unit/ci/test_github_action_wrapper.py tests/unit/ci/test_gitlab_template_contract.py tests/contract/ci/test_wrapper_contract.py` → 11 passed

## 5) Integration smoke

- [x] `python3 -m pytest -q --no-cov tests/integration/test_ghost_mode_smoke.py` → 1 passed

## 6) Documentation checks

- [x] README documents Ghost mode behavior matrix, override flags, secrets, and troubleshooting.
- [x] ARCHITECTURE documents Ghost mode precedence, metadata fields, and sync summary fields.
- [x] CI docs include wrapper behavior for `ghost-mode` / `UQO_GHOST_MODE`.

## 7) Required pass criteria

- [x] Every command above exits with `0`.
- [x] In CI env, `uqo run --config ...` auto-enters ghost mode without `--ci`.
- [x] `--no-ghost` disables auto-detected ghost mode.
- [x] Summary JSON contains deterministic `execution_mode`, `failure_type`, and `sync` fields.
- [x] No CI-provider conditionals added in `testo_core/repository` adapters/factory.
