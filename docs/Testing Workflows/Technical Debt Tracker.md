# Technical Debt Tracker

[Index](../Index.md)

Open backlog for the `testo-core` codebase. Items come from code reading and known contract gaps, not only inline `TODO` markers (there are none in `testo_core/`, `testo_api/` or `tests/`).

Related: [Deep Dive - Execution Logic](../Architecture/Deep%20Dive%20-%20Execution%20Logic.md), [Troubleshooting and Error Codes](../CLI%20Commands/Troubleshooting%20and%20Error%20Codes.md), [Architecture Overview](../Architecture/Architecture%20Overview.md).

---

## Open

### 1. Signal deaths classify as test failures

Timeouts normalize to return code **124** (exit **3**) and engine exceptions to exit **4**, but other signal deaths (e.g. SIGKILL, rc **137**) still classify as exit **1**. This is locked as a known misclassification in `tests/contract/testo_core/test_exit_code_contract.py` until a signal-aware classifier lands.

### 2. Broad `except Exception` in I/O paths

- `testo_core/reporting/reporters/reportportal_client.py`, `extent_reporter.py`

Risk: silent degradation (empty reports) without a structured error. Fix: catch specific exceptions (`OSError`, `ClientError`, `SQLAlchemyError`), log with `exc_info=True`, and surface exit **3** when the operation was required.

### 3. Swallowed BehaveX / native report errors

`testo_core/engine/executor.py` wraps `ensure_behavex_report_html` in `except Exception: pass`; `testo_core/reporting/native_reports.py` does the same. `testo report native` then finds no HTML and the cause is invisible. Fix: log at DEBUG and set `StageResult.error` so NDJSON and panels show a warning.

### 4. Reporter failures don't fail the run

`testo_core/reporting/reporters/factory.py` catches per-reporter exceptions, so a configured integration can be skipped silently after a green run. Fix: an opt-in `reporters_required: true` that maps a reporter failure to exit **3**, plus a `reporter_failed` NDJSON event.

### 5. Git trigger fallback is silent

`testo_core/triggers.py` falls back to snapshot mode on `OSError` / `TimeoutExpired` / `RuntimeError` without telling anyone, which can cause an unexpected full run. Fix: emit `{"event":"trigger_fallback",...}` under `--ci`; `testo doctor` could check git availability.

### 6. `mypy testo_api` is not in CI

`mypy testo_core` is clean and blocking. `testo_api` still has type errors (mostly `cycle_execution_manager.py` and `routes/ai.py`) and is not checked in CI yet.

### 7. Sequential-only orchestrator

Stages run one at a time (`engine/orchestrator.py`); parallelism today is framework-internal (e.g. BehaveX `--workers`). Opt-in parallel stages need isolated `artifacts/<cycle>/<stage>/` trees, aggregated exit classification and documented resource limits.

### 8. Log reader join timeout

`executor.py` calls `reader.join(timeout=2.0)` after the subprocess exits, so a very large final stdout burst could be cut short. Fix: drain until EOF; add an integration test with a large burst.

## Known and intentional

- **Per-stage Allure wipe**: `executor.py` removes the stage's `allure-results/` before each run to isolate stages. Retries must use separate stage names.
- **`LogBuffer.on_chunk` swallows renderer errors** (`engine/log_buffer.py`) so a broken renderer cannot crash a run.
- **Orchestrator catch-all**: `run_plan()` turns an exception from `run_stage()` into an internal-failure stage result, which classifies the plan as exit **4** rather than crashing.

## Resolved

- Exit-code contract single-sourced in `engine/exit_codes.py`; timeouts → 124 → exit 3, engine errors → exit 4.
- The second, Docker-based execution stack (`HeadlessEngineService`, `runners.py`, pluggy plugins, `/api/v1/executions`, Streamlit UI) was removed in v1.1; every run goes through `CycleRunService` and the engine.
- `--ci` forces a synchronous report archive; a required archive failure exits **3**.
- `testo_core/persistence/` (`JsonBackend`, `DbBackend`, `composite_backend()`) replaced the persistence stub.
- MinIO, the pre-v1.1 snapshot reads and the Docker-stack record shape in `history/` were removed in v1.1.
- `mypy testo_core` reports 0 errors and blocks CI, as does `ruff format --check`.

## Refreshing this note

On each release or large refactor, re-run `rg 'TODO|FIXME|HACK' testo_core testo_api tests`, look for new `except Exception` sites in `testo_core/engine/`, and move fixed items to **Resolved**.
