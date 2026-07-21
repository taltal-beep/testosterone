# API–Engine Contract Drift Fix — 2026-07-04

## Symptom

Every cycle run triggered from the React UI failed immediately with a chain of `AttributeError`/`TypeError` surfaced through the execution manager's defensive handler:

1. `'Plan' object has no attribute 'tags'`
2. `run_plan() got an unexpected keyword argument 'fail_fast'`
3. `'TestosteroneConfig' object has no attribute 'reporters'`
4. (after those) stages ran but pytest exited 4: `ModuleNotFoundError: No module named 'jwt'`

CLI runs (`testo run --cycle`) were unaffected throughout.

## Root cause

`testo_api/cycle_execution_manager.py` was written against the **unmerged branch `cursor/report-infra-e976a`**, whose world includes `Plan.tags`, `TestosteroneConfig.reporters` (`ReporterSpec`), the full `testo_core/reporting/reporters/` package (`orchestrate.run_configured_reporters`, factory, Allure/Extent/ReportPortal/TestBeats reporters), and a `fail_fast` parameter on `run_plan()`. None of that exists on `main` — only stale `__pycache__/*.pyc` files remained as evidence. The frontend (RunPanel fail-fast toggle, SSE `plan_aborted` type) and the docs ([[Troubleshooting and Error Codes]], [[Deep Dive - Execution Logic]]) already specified the fail-fast contract.

The fourth failure was environmental: framework adapters build argv with bare tool names (`pytest`), resolved via the subprocess `PATH`. When uvicorn is launched directly from `.venv/bin/uvicorn` (no activated venv), stage subprocesses resolved a system-level pytest (Python 3.12 framework install) that lacks the project's dependencies.

## Fixes (commits on `main`)

- **`testo_api/cycle_execution_manager.py`**: removed phantom `tags=plan.tags` from `_apply_workers_override`; reporter block now uses `getattr(cfg, "reporters", ())` and treats a missing `testo_core.reporting.reporters.orchestrate` module as "skip post-run reporting" instead of crashing; stage subprocess env now prepends `Path(sys.executable).parent` to `PATH` (deliberately **not** `.resolve()` — in a venv `sys.executable` is a symlink into the base interpreter, and resolving it points at the wrong bin dir).
- **`testo_core/engine/orchestrator.py`**: implemented `run_plan(..., fail_fast=False)` per the locked NDJSON contract — a stage with non-zero returncode writes `{"event":"plan_aborted","reason":"fail_fast","completed_stages":N}` and breaks; `plan_finished` still closes the stream. This was previously documented but unimplemented.

## Follow-ups

- ~~Decide whether to merge or discard `cursor/report-infra-e976a` (reporters subsystem + `reporters:` config schema).~~ **Resolved 2026-07-21** — hand-ported into `main`, see [[Reporters Subsystem Port - 2026-07-21]].
- CLI `--fail-fast` flag remains a roadmap item ([[Command Reference]] callout) — the engine now supports it, so wiring the flag is trivial.
- Engine tests for `fail_fast`/`plan_aborted` referenced in [[QA Strategies]] (LC rows) do not actually exist yet; add them.
