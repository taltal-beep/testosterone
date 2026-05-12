# Phase-2 Release Checklist (Ghost Mode Background Sync)

This checklist is the release gate for Ghost Mode CI auto-detection, non-interactive output, and background sync telemetry.

## 1) Core install and CLI sanity

- `python3 -m pip install -U pip`
- `python3 -m pip install -e '.[dev]'`
- `uqo run --help`
- `uqo run --config tests/fixtures/ci/ghost_minimal.yml --stream-json`

## 2) Ghost policy and provenance tests

- `python3 -m pytest -q --no-cov tests/unit/testo_core/test_ghost_policy.py tests/unit/testo_core/test_ci_provenance.py`
- `python3 -m pytest -q --no-cov tests/unit/testo_core/test_cli_run.py`

## 3) Engine + sync behavior tests

- `python3 -m pytest -q --no-cov tests/unit/testo_core/test_headless_engine.py`
- `python3 -m pytest -q --no-cov tests/contract/testo_core/test_cli_contract.py tests/contract/testo_core/test_ghost_summary_contract.py tests/contract/testo_core/test_ghost_ndjson_contract.py`

## 4) CI wrapper contract tests

- `python3 -m pytest -q --no-cov tests/unit/ci/test_github_action_wrapper.py tests/unit/ci/test_gitlab_template_contract.py tests/contract/ci/test_wrapper_contract.py`

## 5) Integration smoke

- `python3 -m pytest -q --no-cov tests/integration/test_ghost_mode_smoke.py`

## 6) Documentation checks

- README documents Ghost mode behavior matrix, override flags, secrets, and troubleshooting.
- ARCHITECTURE documents Ghost mode precedence, metadata fields, and sync summary fields.
- CI docs include wrapper behavior for `ghost-mode` / `UQO_GHOST_MODE`.

## 7) Required pass criteria

- Every command above exits with `0`.
- In CI env, `uqo run --config ...` auto-enters ghost mode without `--ci`.
- `--no-ghost` disables auto-detected ghost mode.
- Summary JSON contains deterministic `execution_mode`, `failure_type`, and `sync` fields.
- No CI-provider conditionals added in `testo_core/repository` adapters/factory.
