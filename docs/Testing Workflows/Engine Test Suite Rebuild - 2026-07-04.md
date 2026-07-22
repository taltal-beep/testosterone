# Engine Test Suite Rebuild — 2026-07-04

[[QA Strategies]] · [[Troubleshooting and Error Codes]] · [[Command Reference]]

## What happened

The coverage tables in [[QA Strategies]] (§Testing the orchestrator itself) referenced an engine/CLI test suite — `test_exit_codes.py`, `test_log_buffer.py`, `test_executor.py`, `test_orchestrator_lifecycle.py`, `test_run_exit_codes.py`, `test_run_flags.py`, `test_run_archive.py`, `test_run_ci_ndjson.py`, `test_config_discovery.py`, `test_cli_commands_smoke.py`, `test_exit_code_contract.py`, `test_subprocess_smoke.py` — that did not exist anywhere under `tests/`.

An audit found `__pycache__` remnants (compiled under pytest 9 / CPython 3.12–3.13) in `tests/fixtures/engine/`, `tests/unit/testo_core/engine/`, `tests/unit/testo_core/cli/`, and `tests/integration/testo_core/engine/`, but **zero git history** for any of those paths. The suite was written and executed in a working tree that was wiped before the files were ever committed. Only `tests/unit/testo_core/engine/test_orchestrator.py` (fail-fast lifecycle, commit `afead659`) survived.

## What was rebuilt

All twelve files above plus the `tests/fixtures/engine/` package (`EchoAdapter` / `HangAdapter` / `MissingBinaryAdapter`, `NoopRenderer`, YAML builders, NDJSON helpers, `scripts/echo.py` + `scripts/hang.py`). Stages in the CLI tests run as **real subprocesses** (`echo.py` stands in for pytest/behave), driven through Typer's `CliRunner`; the whole suite (~110 tests) runs in about 4 seconds. See the updated coverage matrix in [[QA Strategies]] for the row-by-row mapping; rows for unimplemented CLI flags (`--tag`, `--fail-fast`, `--dry-run`, `--reporter`) and archive exit-code escalation (EC-03c–e, EC-06, CLI-10) are now explicitly labelled **Gap (roadmap)**.

## Engine contract fixes restored alongside

Writing the tests exposed two places where the engine had drifted from the documented exit-code contract in [[Troubleshooting and Error Codes]]:

1. **Stage timeouts** — `executor.run_stage` recorded the raw signal returncode (e.g. `-15` after SIGTERM), so timeouts classified as exit **1** instead of the documented **3**. The executor now normalises timeouts to `returncode=124` (`timed_out=true` unchanged).
2. **Internal failures** — `classify_exit_code` had no `internal_failure` parameter, so an orchestrator-caught engine exception (synthetic stage `returncode=4`) classified as a *domain* failure (exit 1). `StageResult` gained an `internal_failure: bool` field, the orchestrator sets it on the defensive path and passes the flag to the classifier, and the artifact `events.ndjson` `stage_finished` mirror now includes it. Exit **4** is therefore reachable as documented (EC-04), while a framework genuinely returning 4 still classifies as exit 1 (EC-07).

Both fixes are locked by `tests/contract/testo_core/test_exit_code_contract.py`.

## Lessons learned

- Uncommitted work does not exist. The suite was fully written, green, and referenced from the vault — and still vanished. Commit and push incrementally (the repo rule is every change goes to origin).
- Docs written against uncommitted code become silent fiction. The coverage matrix now labels unimplemented surface as *Gap (roadmap)* instead of naming files, so a future audit can distinguish "planned" from "lost".
