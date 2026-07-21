# Reporters Subsystem Port — 2026-07-21

## Symptom

The Run Detail page's "Report Links" section was always empty for every cycle run — `GET /api/v1/runs/{run_id}/reports` returned `static_links: {}` unconditionally. Flagged as an open follow-up in both [[API-Engine Contract Drift Fix - 2026-07-04]] and [[Report Links and Artifacts Missing Fix - 2026-07-06]].

## Root causes (two, independent)

1. **The reporters subsystem was never merged into `main`.** It existed only on branch `cursor/report-infra-e976a`, which had diverged 2,548 files / ~140k lines from `main` (mostly committed Allure JSON results and HTML reports, not real source) — a full merge was not viable, since `main` had 39 independent commits of engine/persistence evolution (repository pattern, CLI-first refactor) the branch never saw. `testo_core/reporting/reporters/` was an empty directory; `run_configured_reporters()` didn't exist anywhere.
2. **A second, deeper gap, found while investigating the first:** even with the reporters subsystem present, the Run Detail page's `static_links` is read exclusively from `STATIC_HISTORY_ROOT/<run_id>/allure_report/index.html` (`testo_core/run_history.py::list_run_sessions()`). Tracing every code path on both branches turned up **no writer for that location at all** for the modern engine-sourced run flow (`testo run --cycle` / the API's `cycle_execution_manager.py`) — it was leftover plumbing from an older Docker-based headless-runner design (`testo_core/runners.py`, `UQO_AUDIT_RUN_ID`) that was never wired to the current `run_plan()` engine. The only thing that did write near `static/` was the unrelated legacy `sync_all_reports_to_static()` (used by the deprecated Streamlit UI), which mirrors into `static/allure_reports/` — no run id, incompatible layout.

Porting the reporters subsystem alone would have generated HTML at `<artifacts_root>/allure-report/`, which `static_links` never looks at. Both gaps had to be closed together.

## What was ported (hand-port from `cursor/report-infra-e976a`, not a merge)

**Pure copy, zero conflicts:** `testo_core/reporting/reporters/{__init__,base,factory,orchestrate,allure_reporter,extent_reporter,extent_builder,reportportal_reporter,reportportal_client,testbeats_reporter,testbeats_payloads}.py` + `templates/extent_dashboard.html.j2`, plus `testo_core/reporting/{allure_results,allure_delta_transform,allure_history_serve,allure_summary_widgets,pyramid_viz}.py`.

**Hand-reconciled** (existed on both branches, `main` had evolved independently since the fork):
- `collector.py` — appended `collect_results_docker_run()` (additive only).
- `history_inject.py` — `try_inject_prior_history()` gained a `trend_depth: int = 1` param (behavior-preserving at the default).
- `allure.py` — rewritten to delegate to `allure_cli.py` (the project's actual Allure-3-via-npm resolution, already used everywhere else) instead of a stale bare `shutil.which("allure")` lookup. Not optional cleanup — the ported `AllureReporter` imports `generate_html`/`AllureCLINotFoundError` from this module, and the old version would have silently used the wrong Allure resolution strategy.
- `entry.py`, `exporter.py`, `paths.py`, `server.py` — **left untouched**. `main`'s independent versions already satisfy everything the ported code calls into; the cursor branch's diffs for `paths.py` (deletes the `safe_child_path()` traversal guard) and `server.py` (a net regression vs. `main`'s rewrite) were deliberately not ported.

**New config surface:** `testo_core/config/schema.py` gained `SUPPORTED_REPORTER_TYPES`, `ReporterSpec`, and `TestosteroneConfig.reporters`. `testo_core/config/loader.py` gained `_parse_reporters()`, wired into both `_build_cycle_config()` and `_build_legacy_runs_config()`. `pyproject.toml` gained `Jinja2>=3.1.0` (required by `extent_builder.py`'s Jinja templating). `testosterone.yaml` gained a top-level `reporters:` block (currently `- type: allure`).

## The run-id / static-links bridge

`run_plan()` (`testo_core/engine/orchestrator.py`) already called `composite_backend(...).persist(plan_result)` as its last step, and `DbBackend.persist()` already called `repo.create_run(...)` — which returns the created `RunRecord` (with `id` assigned, and `metadata["run_id"]` set to it before insert). Both return values were being discarded.

Fix: `DbBackend.persist()` and `_CompositeBackend.persist()` now return the persisted run id (`str | None`); `run_plan()` captures it and attaches it to the (previously unused) `PlanResult.extra["run_id"]` field via `dataclasses.replace()`.

Rather than generating Allure HTML to `<artifacts_root>/allure-report/` and then copying/mirroring it into `STATIC_HISTORY_ROOT/<run_id>/allure_report/` afterward, the wiring computes that destination path up front and passes it as `out_dir` straight into `run_configured_reporters()` / `AllureReporter.publish()` — both already accept an explicit `out_dir` and write directly there when given. One I/O pass, no separate mirror step, no second failure mode.

**Wiring is a single shared helper**, not duplicated logic: `_maybe_run_configured_reporters()` lives in `testo_core/cli/runner.py` next to the existing `_maybe_archive_cycle_report()` (the analogous archive-to-DB hook), and both `runner.py`'s own call site and `testo_api/cycle_execution_manager.py` (which already imports `_maybe_archive_cycle_report` from `runner.py` for the sibling step) call into it.

## Verified

- Full test suite: 558 passed, 4 skipped (up from 549 passed pre-change; added 9 new tests covering `reporters:` YAML parsing, `DbBackend`/composite return-value propagation, and `PlanResult.extra["run_id"]`).
- `testo run --cycle sample-pytests` end-to-end: CLI printed `Reporter: Allure HTML at .../static/history/<run_id>/allure_report/index.html`; confirmed the file exists on disk; confirmed `GET /api/v1/runs/<run_id>/reports` returns `"static_links": {"pytest": "history/<run_id>/allure_report/index.html"}` via a live `uvicorn` process.
- Repeated via the API-triggered path (`POST /api/v1/cycles/sample-pytests/executions`) — same result, confirming `cycle_execution_manager.py`'s wiring matches the CLI's.
- `.gitignore` gained `static/history/` (sibling to the existing `static/allure_report/` etc. entries) — this path didn't exist before this change, so nothing had ignored it yet.

## Open follow-up (not fixed here)

~~`testo_api/main.py` mounts no `StaticFiles` route anywhere...~~ **Resolved same day** — see "Follow-up: per-framework links, 404 fix, Extent scoping" below.

## Follow-up: per-framework links, 404 fix, Extent scoping — 2026-07-21

Live-tested `sample-all-frameworks-stochastic` through the React dashboard (3 stages: pytest, native Behave, BehaveX) and found the "Resolved 2026-07-21" state above still only ever surfaced a single link labeled **"pytest"**, regardless of which frameworks actually ran, and clicking it 404'd. Three more root causes, on top of the already-tracked static-mount gap:

1. **Every cycle run was mislabeled "pytest".** `_maybe_run_configured_reporters()` (`testo_core/cli/runner.py`) pointed Allure's `out_dir` at one unified `STATIC_HISTORY_ROOT/<run_id>/allure_report/` (singular) merging all stages together. `list_run_sessions()` only recognized that singular path via its back-compat branch, which unconditionally maps it to `links["pytest"]` — a behave/behavex cycle got the same misleading label.
2. **Extent could never be linked, and clobbered across runs.** `ExtentReporter.publish()` ignored `context.out_dir` entirely, always writing to the shared `<artifacts_root>/reports/extent/` — not run-scoped, and not under `STATIC_HISTORY_ROOT`, so no run's Extent output was ever individually addressable.
3. **Hardcoded framework taxonomy.** Even the existing per-framework "new layout" branch only checked a fixed tuple `("pytest", "behavex", "behave_native")` — but the native Behave adapter (`testo_core/frameworks/behave_adapter.py`) names its results subdir `"behave"`, not `"behave_native"`, so it could never have matched.

### Fix

- `ReportContext` (`reporters/base.py`) gained a `run_report_root: Path | None` field — the per-run base dir each reporter derives its own subdir from, alongside (not replacing) the existing single-purpose `out_dir`.
- `AllureReporter.publish()` now generates **one Allure report per framework** (reusing the already-present-but-previously-unused `CollectedResults.by_framework`) under `run_report_root/allure_reports/<framework>/index.html`, when `run_report_root` is set and no explicit `out_dir` is given. The CLI's single-merged-report path (`testo report`, explicit `out_dir`) is unchanged.
- `ExtentReporter.publish()` now defaults to `run_report_root/extent_report/` when set, instead of the shared unscoped path.
- `orchestrate.py` / `cli/runner.py` thread `run_report_root = STATIC_HISTORY_ROOT/<run_id>` through instead of the old singular `out_dir`.
- `run_history.py`'s `list_run_sessions()` now scans `allure_reports/` dynamically (link key = actual subdir name) instead of a hardcoded 3-key tuple, fixing the `behave`/`behave_native` mismatch for free, plus checks `extent_report/index.html` → `links["extent"]`. The old singular back-compat branch is untouched, so already-persisted historical runs keep their existing (if mislabeled) link.
- `testo_api/main.py` now mounts `app.mount("/history", StaticFiles(directory=STATIC_HISTORY_ROOT), name="history")` (creating the directory first, since it's `.gitignore`'d and may not exist on a fresh checkout).
- `frontend/src/lib/api-client.ts` exports `API_BASE`; `RunDetailPage.tsx`'s Report Links card prefixes each href with it.

### Not fixed here

ReportPortal (remote launch URL, no local HTML) and TestBeats (webhook + JSON summary, no HTML index) don't fit the `index.html` link-card pattern and weren't touched.
