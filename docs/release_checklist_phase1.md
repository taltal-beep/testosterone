# Phase-1 Release Checklist (Foundation)

This checklist is the required gate before starting any Phase-2 work.

## 1) Environment bootstrap

- Create a clean virtual environment.
- Install package + dev dependencies:
  - `python -m pip install -U pip`
  - `python -m pip install -e '.[dev]'`
- If MySQL URL validation is required in your environment, install optional driver:
  - `python -m pip install -e '.[db_mysql]'`

## 2) Packaging reproducibility

- Build distribution artifacts:
  - `python -m build`
- Verify console script availability:
  - `uqo --help`
  - `uqo run --help`
- Verify version consistency:
  - `python -c "import testo_core; import importlib.metadata as m; print(testo_core.__version__, m.version('testo-core'))"`

## 3) Contract and regression tests

- Run focused Phase-1 closure suites:
  - `pytest -q --no-cov tests/unit/testo_core/test_repository_sqlite.py tests/unit/testo_core/test_repository_factory.py tests/contract/testo_core/test_repository_contract.py`
  - `pytest -q --no-cov tests/unit/testo_core/test_cli_run.py tests/unit/testo_core/test_headless_engine.py tests/contract/testo_core/test_cli_contract.py tests/unit/testo_core/test_config_loader.py`
  - `pytest -q --no-cov tests/contract/testo_core/test_packaging_contract.py`
- Run full suite gate:
  - `pytest -q`

## 4) Documentation gate

- Confirm `README.md` and `ARCHITECTURE.md` match runtime behavior for:
  - `uqo run` output schemas and exit-code taxonomy (`0/1/2/3/4`)
  - `trigger_source`, `ci_mode`, `schema_version` provenance fields
  - shared orchestration path (UI and CLI both use `HeadlessEngineService`)

## 5) Pass criteria

- All commands exit 0.
- No CLI contract mismatches.
- No unsupported-dialect ambiguity in DB adapter validation.
- No duplicate orchestration paths reintroduced in `app.py`.
