# CLI-UI Parity — Pyramid, Graphs, Deep Diff — 2026-07-23

## Symptom

The `testo` CLI had three features with no React/API equivalent:

1. **Test pyramid** — `testo_core/reporting/pyramid_viz.py` was a complete ASCII pyramid renderer (tier counts → shape classification → ASCII art) that nothing imported, no CLI command called, and no data source fed. The [[Project Audit - 2026-06-24]] listed it as "Mature" under the reporting pipeline — it wasn't even wired into the CLI, let alone the UI. It was hand-ported whole in [[Reporters Subsystem Port - 2026-07-21]] and never referenced again.
2. **"Simple graph"** — the stacked ASCII bar in `testo diff`/`testo summary` (`testo_core/cli/ui/summary_dashboard.py`) visualizing passed/failed/broken/skipped composition. The data (`/api/v1/analytics/delta`, `/api/v1/runs/{id}`) already existed; the React Compare page rendered it as plain text rows with zero visualization, and `frontend/package.json` had no charting library.
3. **Deep diff** — `testo diff`/`testo report compare` (`testo_core/services/report_archive_diff.py::diff_archives`) do a full per-test comparison: matches cases by `historyId`/`fullName`/`uuid`, classifies each as added/removed/regression/fix/status_change, grouped by suite. `/api/v1/analytics/delta` (`delta_service.py`) only ever exposed 9 run-level aggregate metrics — no per-stage or per-test breakdown reached the frontend, even though per-stage data (`CompletedRunView.stage_health`) was already computed and unused for comparison.

Separately, two API endpoints existed but were never called from the UI: `GET /api/v1/dashboard/runs/recent` and `GET /api/v1/cycle-executions/{id}`.

## Decisions

- Reuse existing pure logic rather than reinvent it: `pyramid_viz.py`'s shape classification, `report_archive_diff.py`'s per-test matching, and `stage_health`'s per-stage counts all get wired up, not rebuilt.
- No new frontend charting dependency — hand-rolled SVG/CSS components (`StackedBar`, `HealthBar`), consistent with the existing `frontend/package.json` (no recharts/d3/etc.).
- The new per-test diff endpoint computes on-demand, no caching — archives aren't large enough yet to justify the schema/invalidation work.
- Test tier (unit/integration/e2e) is a new optional `Stage.tier` config field, defaulting from `equipment` (pytest→unit, behave→integration, behavex→e2e) so existing `testosterone.yaml` cycles work unmodified.

## Phase 1 — Quick wins (2026-07-23)

- `DashboardPage.tsx` now polls `GET /api/v1/dashboard/runs/recent` on its own cadence (`refetchInterval`) instead of only reading `recent_runs` off the heavier `/dashboard/overview` call.
- `RunPanel.tsx`: on SSE `onError`, instead of assuming failure, polls `GET /api/v1/cycle-executions/{id}` (`getCycleExecutionStatus`) for the authoritative terminal status.
- New `frontend/src/components/ui/StackedBar.tsx` (`StackedBar`, `HealthBar`) — proportional bar components using the existing Tailwind success/danger/warn palette. Used in `DashboardPage.tsx` (per-run health bar) and `ComparePage.tsx` (new "Outcome Mix" section: baseline vs. current passed/failed/broken/skipped composition) — the UI equivalent of `summary_dashboard.py`'s ASCII stacked bar.
- No backend changes; all data already flowed through existing endpoints.

## Phase 2 — Test pyramid: config, aggregation, CLI (2026-07-23)

- `testo_core/config/schema.py`: `Stage` gained `tier: str = "unit"`; new `SUPPORTED_TIERS` and `DEFAULT_TIER_BY_FRAMEWORK`.
- `testo_core/config/loader.py::_parse_stage()`: parses an explicit `tier:` (validated against `SUPPORTED_TIERS`) or falls back to `DEFAULT_TIER_BY_FRAMEWORK[framework]`.
- New `testo_core/reporting/pyramid_data.py::build_pyramid_model(run, stages)` sums each stage's `total_tests` (already on `CompletedRunView.stage_health`, computed by `persistence/health.py::compute_stage_health`) into its tier bucket, producing the `pyramid_viz.PyramidModel` the renderer already expected.
- New CLI command `testo report pyramid RUN_ID` (`testo_core/cli/commands/report.py`) — looks up the run via `run_history.get_run()`, loads its cycle's stages via `discover_and_load()`, and prints `pyramid_viz.render_pyramid_lines()` + the classified shape.
- Note: `RUN_ID` here is the run-history run id (same id used by `/api/v1/runs/{id}` and the dashboard/history pages) — a different id space from `testo report list/open`'s `ReportArchive` UUID.
- Tests: `tests/unit/testo_core/test_pyramid_viz.py` (recreates coverage for `classify_shape`/`render_pyramid_lines` — the original `test_pyramid_viz.py` from the 2026-07-21 port was lost/never committed, only a stale `.pyc` remained), `test_pyramid_data.py`, `test_stage_tier_config.py`.
- Corrected the stale "pyramid viz — Mature" line in [[Project Audit - 2026-06-24]] and added the pyramid data flow to [[Architecture Overview#Test pyramid]].

## Phase 3 — Test pyramid: API + frontend (2026-07-23)

- New `GET /api/v1/runs/{run_id}/pyramid` (`testo_api/routes/history.py`) — thin wrapper over the same `build_pyramid_model` + `classify_shape` the CLI uses; `RunPyramidResponse` in `testo_api/models.py`. Skips config lookup (defaults to an all-"unit" bucket) when the run has no `cycle` recorded, matching the CLI command's own fallback.
- New `frontend/src/components/ui/TestPyramid.tsx` — proportional stacked bars (one per tier) plus the shape label/message, no new npm dependency. Wired into a new "Test Pyramid" card on `RunDetailPage.tsx`.
- Fixed a pre-existing crash in the same file while there: `run.stage_health.length` threw when `stage_health` was `undefined` (`RunDetailPage.test.tsx`'s "renders AI summary card for failed runs" was failing on this before Phase 3 touched the file) — changed to `(run.stage_health ?? []).length`.

## Phase 4 — Deep diff: per-stage (cheap) then per-test (full) (2026-07-23)

- **Per-stage delta**: `delta_models.py` gained `StageDelta` (matched by stage name, health-pct classification); `DeltaComparisonResult.stage_deltas`. `DeltaComparisonService._build_stage_deltas()` (`delta_service.py`) matches `current.stage_health` against `baseline.stage_health` by `name` -- reuses data already loaded on each `CompletedRunView`, no archive I/O. Exposed via the existing `/api/v1/analytics/delta` response (`DeltaStageDelta` in `testo_api/models.py`) and a new "Per-Stage Health" table on `ComparePage.tsx`.
- **Per-test delta -- design deviation from the original plan**: the plan assumed each run id could resolve to a `ReportArchive` row and reuse `diff_archives()` directly. It can't: `ReportArchive` (the `testo report list/open/diff` table) has **no `run_id` column and no link at all** to `CompletedRunView`/run-history (the `testo run` / dashboard / `/api/v1/runs/{id}` universe) -- they're two independent archiving mechanisms that both get populated by the same `testo run --cycle` but never cross-reference each other.
  - Fix: extracted the matching/classification core out of `diff_archives()` into a new public `report_archive_diff.diff_case_maps(base_cases, cur_cases)` (pure, unchanged behavior -- `diff_archives()` now just extracts its zips and calls it).
  - New `testo_core/services/run_snapshot_diff.py::diff_run_snapshots(baseline, current, tmp)` materializes each run's own snapshot (`CompletedRunView.snapshot_dir`, local or S3) into a temp dir via the already-existing `snapshot_files_for_download()` (reused as-is, no new storage-access code), then calls `_load_cases()` + `diff_case_maps()` on each -- same per-test matching (`historyId`/`fullName`/`uuid`) and classification (`added`/`removed`/`regression`/`fix`/`status_change`) the CLI's `testo diff` uses, just sourced from the run's live snapshot instead of an archived zip.
  - New `GET /api/v1/analytics/delta/cases` (`testo_api/routes/analytics.py`) wraps `diff_run_snapshots`, computed on-demand every request per the earlier no-caching decision.
  - Frontend: `ComparePage.tsx` gained an expandable "Test-Level Changes" section (lazy-fetched only when expanded, since this is the heavier on-demand endpoint) with a kind filter (all/regression/fix/added/removed/status_change) and suite-grouped listing.

## Verified (Phases 1-4)

- Frontend: `npx tsc --noEmit` shows no new errors (3 pre-existing, unrelated to files touched); `npx vitest run` — all touched-page test files pass (`DashboardPage`, `ComparePage`, `RunPanel`, `CyclesPage`, `RunDetailPage`: 14/14 across those files). One pre-existing failure in `src/e2e/happy-path.test.tsx` was confirmed present on baseline (via `git stash`) before any of this work — not introduced by it, left untouched. Manually verified in-browser against the live `sample-all-frameworks-stochastic` run history: Dashboard shows a health bar per recent run; Compare's Outcome Mix renders a green baseline bar next to a green/red/yellow current bar for a real regression; Run Detail's Test Pyramid card renders proportional bars + "Irregular tier mix" / "Non-ideal tier ordering" for the same run the CLI classified identically; Compare's Per-Stage Health table shows real per-stage regressions (e.g. `flow-tests` -100.0pp); the expandable Test-Level Changes section, against the same two live runs, returned 88 real per-test changes (matching the -88 `passed` delta from the aggregate metrics exactly) grouped by suite, with the Regression filter correctly narrowing the list.
- Backend: `pytest tests/unit/testo_core -k "config or loader or pyramid or stage_tier or report or delta or diff"` and `pytest tests/contract/api tests/integration/api` all green (54 relevant tests across the two runs, no regressions). `testo report pyramid d513f43b-8c56-4820-9f22-ad8983b9f752` and `curl localhost:8000/api/v1/runs/.../pyramid` agree exactly (`unit=130 integration=34 e2e=34 shape=irregular`). `curl localhost:8000/api/v1/analytics/delta/cases?...` against two live runs returned in ~0.44s.
