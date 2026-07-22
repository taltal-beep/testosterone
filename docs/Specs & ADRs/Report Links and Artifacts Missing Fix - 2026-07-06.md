# Report Links and Artifacts Missing Fix — 2026-07-06

## Symptom

Every cycle run — CLI (`testo run --cycle`) and API/React UI (`POST /cycles/{cycle}/executions`) alike — showed **empty Report Links and Artifacts** on the Run Detail page (`GET /api/v1/runs/{run_id}/reports` → `static_links: {}`, `artifact_links: []`), even for fully passing, 100%-health runs. Reported as "all cycles always fail and there are no Report Links nor Artifacts."

Separately, the Runs list showed cycle executions permanently stuck in **"Running"** status (never transitioning to Completed/Failed).

Note: `sample-all-frameworks` itself was not actually failing — it passed consistently (verified via CLI and live UI). The "FAILED" entries seen in history belong to `sample-all-frameworks-stochastic`, which intentionally injects random failures (`TESTO_SAMPLE_RANDOM_FAIL_P=0.35`) per its own description — expected behavior, not a bug.

## Root cause

Two independent, unrelated defects, both in code paths shared by every `run_plan()` caller (CLI and API):

1. **Missing artifacts/report links** — `testo_core/persistence/db_backend.py`'s `DbBackend.persist()` (the engine-level persistence backend registered via `composite_backend()`, invoked by `orchestrator.run_plan()` after every cycle) wrote a `RunRecord` with only summary fields (`plan`, `exit_code`, `stages`, …). It never set `snapshot_dir` or `test_kind`. `testo_core/run_history.py`'s `snapshot_files_for_download()` returns `[]` whenever `record.snapshot_dir` is falsy, and `list_run_sessions()`'s `links_under_static` only checks a `static/history/<run_id>/` layout that the modern host-subprocess engine never populates. Since `snapshot_dir` was never set for any engine-sourced run, `artifact_links` was unconditionally empty for 100% of runs — regardless of pass/fail. (Report Links specifically for Allure/Behave HTML also require a `reporters:` block in `testosterone.yaml`, which the sample cycles don't define — that half is a config gap, not a code bug.)

2. **Runs stuck at "Running" forever** — `testo_core/run_history.py` already has `cleanup_orphaned_runs()` ("mark any RUNNING runs as FAILED... prevents the UI from displaying runs interrupted by a crash as still executing"), but it was only ever called from the legacy `testo_ui/streamlit_app.py`. The FastAPI app (`testo_api/main.py`) never called it. Any run in flight when the uvicorn process restarted (`--reload`, crash) left its `RunRecord` at `RUNNING` permanently.

## Fixes

- **`testo_core/persistence/db_backend.py`**: `DbBackend` now takes `artifacts_root` in its constructor and computes `snapshot_dir` as the plan's artifacts directory relative to the repo root (`ORCHESTRATOR_ROOT`), matching the local-path branch `snapshot_files_for_download()` already supported but nothing wired into. Also sets `test_kind: "cycle"` (was rendering as "unknown" in the Run Detail summary).
- **`testo_core/persistence/composite.py`**: `composite_backend()` now passes `artifacts_root` through to `DbBackend(artifacts_root)`.
- **`testo_api/main.py`**: added a FastAPI `startup` event that calls `cleanup_orphaned_runs()`, mirroring what the Streamlit app already did.
- **Tests**: updated `tests/unit/testo_core/test_persistence_backends.py` for the new `DbBackend` constructor arg; added coverage for the `snapshot_dir` relative-path computation (both the in-repo and outside-repo cases).

Verified via CLI (`testo run --cycle sample-all-frameworks`, repeated) and live through the React UI + `GET /api/v1/runs/{run_id}/reports`: `artifact_links` now lists the real per-stage `run.log` / `allure-results/*` files (712 files on the last CLI run); the 3 previously-stuck `RUNNING` rows now correctly show `FAILED` (orphaned) after a server restart.

## Follow-ups

- ~~`static_links` (native Allure/Behave HTML report links) will stay empty until a `reporters:` block is added to `testosterone.yaml` and the reporters subsystem ... is merged/enabled.~~ **Resolved 2026-07-21** — see [[Reporters Subsystem Port - 2026-07-21]]. That note also flags a *second*, still-open gap it uncovered: `static/` is never mounted by any FastAPI route, so a browser following a `static_links` URL will 404 even now that the data is populated — not fixed in this change, tracked as an open follow-up there.
- Consider unifying `ReportArchive` (zip blob, `testo_core/services/report_archive.py`) and `RunRecord` (`testo_core/run_history.py`) — they're two separate tables populated by two separate calls for the same cycle run today; nothing enforces they stay consistent.
