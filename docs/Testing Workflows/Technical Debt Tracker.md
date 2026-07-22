# Technical Debt Tracker

[[Index]]

Living backlog for the Testo (`testo-core`) codebase. Items are derived from static analysis, architecture comments, and known contract gaps — not only inline `TODO` markers.

Related: [[Deep Dive - Execution Logic]], [[Troubleshooting and Error Codes]], [[Architecture Overview]].

---

## Scan methodology

Last full scan: repository source trees under version control.

```bash
# Explicit markers (exclude generated artifacts)
rg 'TODO|FIXME|HACK' \
  --glob '*.py' --glob '*.md' --glob '*.yml' --glob '*.yaml' \
  --glob '!artifacts/**' --glob '!reports/**' --glob '!node_modules/**'
```

### Explicit marker results

| Area | `TODO` / `FIXME` / `HACK` |
|------|---------------------------|
| `testo_core/` | **None** |
| `testo_api/` | **None** |
| `tests/` | **None** |
| `artifacts/`, `reports/` | Vendored JS only (e.g. Bootstrap) — **ignore** |

The backlog below is **inferred technical debt**: exception breadth, dual execution stacks, exit-code drift, and documented future work in module docstrings.

---

## High priority

### 1. Exit-code contract drift

- [x] **Fixed 2026-06-02; re-applied 2026-07-04** — Timeouts normalize to return code **124** in `executor.py`; orchestrator sets `internal_failure` on engine exceptions and `classify_exit_code(..., internal_failure=True)` maps plan exit to **4**. The 2026-06-02 fix was lost in an uncommitted working tree and restored — this time with committed contract tests (`tests/contract/testo_core/test_exit_code_contract.py`, `tests/unit/testo_core/engine/test_executor.py`). See [[Engine Test Suite Rebuild - 2026-07-04]].

**Risk (historical)**

CI and automation that only check `$?` misclassify infra/timeouts/internal bugs as test failures.

**Remaining**

Signal deaths other than timeout (e.g. SIGKILL rc **137**) still classify as exit **1**; locked as a documented misclassification in the contract tests pending a signal-aware classifier.

---

### 2. Dual execution stacks

- [x] **Partially resolved 2026-06-25** — `EngineExitCode` and `classify_exit_code` are now single-sourced in `engine/exit_codes.py`; headless engine imports and re-exports. Remaining: `RunBackend` protocol extraction (P3, post-v1.0).

**Evidence**

| Modern | Legacy |
|--------|--------|
| `testo_core/engine/orchestrator.py` | `testo_core/services/headless_engine.py` |
| `testo_core/engine/executor.py` | `testo_core/runners.py` (Docker streaming) |
| `testo run` | `uqo run` |

**Risk** (mitigated)

Exit code drift is eliminated. Behavioral drift between run backends remains but is bounded by contract tests (`test_exit_code_consolidation.py`).

**Recommendation**

Long-term: extract a shared `RunBackend` protocol with host and Docker implementations.

---

### 3. `--async-report-db` reliability

- [x] **Fixed 2026-06-02** — `--ci` forces synchronous archive; async path joins with a 30s timeout; required archive failure surfaces exit **3**.

**Evidence**

- `testo_core/cli/runner.py` — `threading.Thread(..., daemon=True)` for `try_persist_cycle_report`
- CLI help text warns archive may not finish before exit

**Risk**

CI jobs exit immediately after tests; report archives missing from DB with no error.

**Recommendation**

Default to synchronous archive in CI (`--ci` implies no `--async-report-db`), or join the thread with a configurable timeout before process exit; surface exit **3** if archive fails.

---

### 4. Persistence stub (Phase 4)

- [x] **Fixed 2026-06-25** — `testo_core/persistence/` module implemented with `PersistenceBackend` protocol, `JsonBackend`, `DbBackend`, and `composite_backend()` factory. `orchestrator.run_plan()` now uses the composite backend; `_try_persist` removed. `--no-persist` disables all persistence (JSON + DB).

**Evidence** (resolved)

- `testo_core/persistence/__init__.py` — public API
- `testo_core/persistence/json_backend.py` — JSON file writer
- `testo_core/persistence/db_backend.py` — DB writer via `RunRepository`
- `testo_core/persistence/composite.py` — fans out to both, swallows individual failures
- `tests/unit/testo_core/test_persistence_backends.py` — unit tests

---

## Medium priority

### 5. Broad `except Exception` in legacy and I/O paths

**Evidence** (non-exhaustive)

- `testo_core/runners.py` — many bare handlers around Docker/streaming
- `testo_core/run_history.py` — S3/DB upload paths
- `testo_core/reporting/reporters/reportportal_client.py`, `extent_reporter.py`
- `testo_core/services/headless_engine.py`, `multi_run.py`, `event_drain.py`

**Risk**

Silent degradation (empty reports, stale RUNNING rows) without structured errors.

**Recommendation**

Catch specific exceptions (`OSError`, `ClientError`, `SQLAlchemyError`); log with `logger.warning(..., exc_info=True)`; propagate to exit **3** when the operation was required.

---

### 6. Inconsistent exit code constants in CLI

- [x] **Fixed 2026-06-25** — All `raise typer.Exit(code=2)` in `config.py` and `plans.py` replaced with `raise typer.Exit(code=int(EngineExitCode.INVALID_INPUT))`.

**Evidence** (resolved)

All CLI commands now use `EngineExitCode` enum for exit codes. Contract test `test_exit_code_consolidation.py` verifies the imports are the canonical class.

---

### 7. Swallowed BehaveX / native report errors

**Evidence**

- `testo_core/engine/executor.py` — `except Exception: pass` around `ensure_behavex_report_html`
- `testo_core/reporting/native_reports.py` — similar patterns

**Risk**

`testo report native` finds no HTML; users blame Testo reporting instead of missing BehaveX output.

**Recommendation**

Log at DEBUG; set `StageResult.error` when HTML generation fails so NDJSON and panels show a warning.

---

### 8. Reporter factory partial failure

**Evidence**

- `testo_core/reporting/reporters/factory.py` — per-reporter `except Exception`
- `run_configured_reporters` — may return empty list on `ValueError` without failing the run

**Risk**

Post-run integrations silently skipped after a green test run.

**Recommendation**

Add `reporters_required: true` config or fail the run with exit **3** when a configured reporter fails; aggregate errors into one Rich panel / NDJSON `reporter_failed` event.

---

### 8a. mypy baseline (43 errors, 14 files) — advisory in CI, not yet blocking

- **Added 2026-07-02** — `mypy` landed in `pyproject.toml` (`[tool.mypy]`) and as an
  advisory step in `.github/workflows/ci.yml`'s `format` job (`continue-on-error: true`).
  `ruff check .` is separately clean and blocking in the same job.

**Evidence** (by file, `mypy testo_core`)

| File | Errors | Nature |
|------|--------|--------|
| `testo_core/runners.py` | 17 | `callable?[Any, None]` not callable (13×); redefined names; container/context-manager type drift |
| `testo_core/services/ai/integration_settings.py` | 7 | `dataclasses.replace(**dict[str, object])` can't narrow to the per-field literal/str/int/bool types |
| `testo_core/cli/commands/report.py` | 3 | `Path \| None` passed where `Path` expected — likely a real missing-None-check |
| `testo_core/run_history.py`, `repository/report_archive_repository.py`, `repository/models.py`, `repository/factory.py`, `repository/adapters.py` | 2 each | `datetime \| None` attribute access, redefined names, repository adapter return-type union not narrowed |
| `services/headless_engine.py`, `reporting/exporter.py`, `persistence/composite.py`, `engine/executor.py`, `cli/ui/renderers.py`, `cli/legacy.py` | 1 each | assorted union-narrowing and `object`-typed attribute access |

**Risk**

Low urgency individually (mostly missing `is not None` narrowing / union handling), but
`report.py`'s `Path | None` cases and `runners.py`'s `callable?` cluster are worth a closer
look — they're the kind of thing that surfaces as a real `None`/attribute crash at runtime
under specific flag combinations, not just a type-checker nitpick.

**Recommendation**

Tackle `testo_core/runners.py` first (17 of 43, one file) since it's already flagged as a
complexity hotspot below. Once the count is near zero, flip the CI step to blocking. Do not
fix these as a side effect of unrelated PRs — track here and land as its own reviewed
change per file/cluster.

---

### 9. Git trigger fallback is silent

**Evidence**

- `testo_core/triggers.py` — `except (OSError, subprocess.TimeoutExpired, RuntimeError): pass` then snapshot mode
- No CI event when git evaluation fails

**Risk**

Unexpected full runs (snapshot “everything changed”) without audit trail in CI logs.

**Recommendation**

Emit NDJSON `{"event":"trigger_fallback","mode":"snapshot","reason":"..."}` when `--ci` is set; optional `testo doctor` check for git availability.

---

### 10. Orchestrator defensive catch masks bugs

**Evidence**

- `orchestrator.run_plan` — `except Exception` around `run_stage` → synthetic failure with rc=4 → classified as exit **1**

**Risk**

Programming errors in adapters look like test failures.

**Recommendation**

Re-raise `KeyboardInterrupt` / `SystemExit`; narrow to expected adapter errors; use exit **4** at plan level for true internal failures.

---

## Low priority

### 11. Sequential-only orchestrator

**Evidence**

- `orchestrator.py` module docstring: only place to add concurrent stages

**Recommendation**

Design opt-in parallel stages with isolated `artifacts/<cycle>/<stage>/` trees and aggregated exit classification; document resource limits (CPU, DB connections).

---

### 12. Duplicate `EngineExitCode` definitions

- [x] **Fixed 2026-06-25** — `headless_engine.py` now imports `EngineExitCode` and `classify_exit_code` from `engine/exit_codes.py`; duplicate class and function removed. Contract test `test_exit_code_consolidation.py` asserts identity (`is`, not just equality).

---

### 13. `LogBuffer.on_chunk` exception swallow

**Evidence**

- `testo_core/engine/log_buffer.py` — renderer exceptions must not crash the run

**Recommendation**

Acceptable for stability; optional debug callback or counter for dropped chunk handlers in development builds.

---

### 14. Pluggy optional imports

**Evidence**

- `testo_core/orchestrator.py`, `specs.py` — `ModuleNotFoundError` / broad `except` for pluggy

**Recommendation**

Document optional `[plugins]` extra in README; `testo doctor` could list whether pluggy is installed.

---

### 15. Log reader join timeout (2s)

**Evidence**

- `executor.py` — `reader.join(timeout=2.0)` after subprocess exit

**Recommendation**

Join without timeout or loop until buffer drained; add integration test with large stdout burst.

---

### 16. Per-stage Allure directory wipe

**Evidence**

- `executor.py` — `shutil.rmtree(results_dir)` before each run

**Recommendation**

Not a bug — intentional isolation. Document that retry-within-stage must not depend on prior Allure files; use separate stage names for retries.

---

## Complexity hotspots (no inline TODO)

Functions/modules worth extra care when refactoring:

| Location | Concern |
|----------|---------|
| `testo_core/runners.py` | Large Docker streaming loop; many exception handlers |
| `testo_core/run_history.py` | Postgres + S3 sync; transactional edge cases |
| `testo_core/config/loader.py` | Legacy schema compatibility paths |
| `testo_core/cli/runner.py` | `execute_plan_command` branches (`all`, tags, dry-run, triggers) |
| `testo_core/services/headless_engine.py` | Multi-run aggregation and ghost JSON contract |

---

## How to refresh this document

On each release or large refactor:

1. Re-run the `rg` command under [Scan methodology](#scan-methodology).
2. Review `testo_core/engine/` and `testo_core/runners.py` for new `except Exception` sites.
3. Run contract tests for exit codes (`tests/` grep `EngineExitCode`, `exit_code`).
4. Update priority tables if items are fixed or superseded.
5. Link new vault notes from [[Index]].
6. After a release gate, reset `- [ ]` checkboxes in the matching [[Release Management/]] checklist or mark completed items `- [x]`.

---

## Vault hygiene

- [ ] Re-run the scan methodology `rg` command after each major refactor.
- [ ] After shipping a phase gate, update the corresponding release checklist checkboxes in [[Release Management/README]].

---

## Related notes

- [[Deep Dive - Execution Logic]] — bottlenecks and threading
- [[Troubleshooting and Error Codes]] — operator-facing symptoms
- [[Architecture Overview]] — intended architecture
- [[QA Strategies]] — how teams run cycles today
- [[CI-CD Pipeline Setup]], [[ReportPortal Local Setup Guide]], [[E2E Harness Operations Guide]]
