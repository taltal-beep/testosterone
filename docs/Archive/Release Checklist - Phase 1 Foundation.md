# Phase-1 Release Checklist (Foundation)

This checklist is the required gate before starting any Phase-2 work.

> **Gate executed:** 2026-06-24

## 1) Environment bootstrap

- [x] Create a clean virtual environment.
- [x] Install package + dev dependencies:
  - [x] `python -m pip install -U pip`
  - [x] `python -m pip install -e '.[dev]'`
- [ ] If MySQL URL validation is required in your environment, install optional driver:
  - [ ] `python -m pip install -e '.[db_mysql]'` *(not required in this environment)*

## 2) Packaging reproducibility

- [x] Build distribution artifacts:
  - [x] `python -m build`
- [x] Verify console script availability:
  - [x] `uqo --help`
  - [x] `uqo run --help`
- [x] Verify version consistency:
  - [x] `python -c "import testo_core; import importlib.metadata as m; print(testo_core.__version__, m.version('testo-core'))"` → `0.1.0 | 0.1.0`

## 3) Contract and regression tests

- [x] Run focused Phase-1 closure suites:
  - [x] `pytest -q --no-cov tests/unit/testo_core/test_repository_sqlite.py tests/unit/testo_core/test_repository_factory.py tests/contract/testo_core/test_repository_contract.py` → 18 passed
  - [x] `pytest -q --no-cov tests/unit/testo_core/test_cli_run.py tests/unit/testo_core/test_headless_engine.py tests/contract/testo_core/test_cli_contract.py tests/unit/testo_core/test_config_loader.py` → 29 passed
  - [x] `pytest -q --no-cov tests/contract/testo_core/test_packaging_contract.py` → 5 passed (fixed `--plan` hidden-flag contract assertion)
- [x] Run full suite gate:
  - [x] `pytest -q` → 402 passed, 4 skipped, 62% coverage

## 4) Documentation gate

- [x] Confirm `README.md` and `ARCHITECTURE.md` match runtime behavior for:
  - [x] `uqo run` output schemas and exit-code taxonomy (`0/1/2/3/4`)
  - [x] `trigger_source`, `ci_mode`, `schema_version` provenance fields
  - [x] shared orchestration path (UI and CLI both use `HeadlessEngineService`)

## 5) Pass criteria

- [x] All commands exit 0.
- [x] No CLI contract mismatches.
- [x] No unsupported-dialect ambiguity in DB adapter validation.
- [x] No duplicate orchestration paths reintroduced in `app.py`.
