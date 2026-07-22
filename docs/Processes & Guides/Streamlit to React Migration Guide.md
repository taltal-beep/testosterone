# Streamlit to React Migration Guide (Phase 3)

## Goal

Move dashboard UX from Streamlit to React while keeping `testo_core` as the only orchestration engine and preserving CLI/CI contracts.

### Official documentation

| Framework | Reference |
|-----------|-----------|
| Streamlit | https://docs.streamlit.io/ |
| React | https://react.dev/ |
| FastAPI (`testo_api`) | https://fastapi.tiangolo.com/ |
| Docker Compose (local stack) | https://docs.docker.com/compose/ |

## Why (product)

Streamlit was ideal for prototyping; production QA teams need a snappy, navigable React UI with explicit API contracts (JSON + SSE), independent scaling of frontend/backend, and a clear rollback path. See [[Product Roadmap#Phase 3: Enterprise UI & Analytics]] and [[Phase 3 Unified Dashboard Plan]].

## Transitional topology

- Streamlit remains available as rollback UI.
- FastAPI (`testo_api`) exposes `/api/v1` JSON + SSE contracts.
- React (`frontend/`) consumes FastAPI endpoints for execution/history/report flows.
- CLI and CI wrappers remain unchanged (`uqo run ...` contract preserved).

## Local developer workflow

1. Start infrastructure:
   - `docker compose up -d`
2. Start backend:
   - `uvicorn testo_api.main:app --host 0.0.0.0 --port 8000 --reload`
3. Start React frontend:
   - `npm --prefix frontend install`
   - `npm --prefix frontend run dev`
4. Optional Streamlit fallback:
   - `UQO_UI_MODE=dual streamlit run app.py`

## Styling

`frontend/` on `main` was documented as Vite + React + Tailwind, but Tailwind was never actually wired in on that branch — no dependency, no config, no stylesheet import, and zero components used utility classes.

The real, styled version already existed on a separate, never-merged branch (`cursor/report-infra-e976a`, diverged from `main` at `c86d7838`, last touched 2026-06-24). That branch bundled two unrelated things: a contained UI slice (Tailwind wiring + a restyled `AppShell.tsx` + a new **Live Execution Console** feature — SSE-driven cycle runner UI) and a much larger, unrelated backend "report-infra" rewrite (~5,200 lines across 55 files touching `testo_core/reporting/reporters/*`, `run_history.py`, `report_archive_diff.py`).

Ported 2026-07-02 — UI slice only, reporting rewrite deliberately left out for separate review:

- `frontend/tailwind.config.ts` + `frontend/postcss.config.cjs` (Tailwind v4 via `@tailwindcss/postcss`, not the Vite plugin).
- `frontend/src/styles.css` imported from `main.tsx`.
- Restyled `AppShell.tsx` (nav pills, dark theme) and new `frontend/src/features/runner/LiveExecutionConsole.tsx` + route (`/runner`).
- Backend support: `testo_api/routes/cycles.py`, `cycle_execution_manager.py`, plus `models.py`/`dependencies.py`/`main.py` wiring for `POST /api/v1/cycles/{cycle}/executions`.
- Skipped `testo_api/routes/history.py` from that branch — it depends on `allure_report_url_for_run()`, which only exists in the excluded reporting rewrite.

**Gotcha**: Tailwind v4's automatic content/source detection walks parent directories looking for `.gitignore` boundaries, which fails silently (empty `utilities` layer, only theme variables generated) in this sandboxed dev environment (`getcwd: cannot access parent directories: Operation not permitted`). Fix: add `@config "../tailwind.config.ts";` to `styles.css` to force the explicit v3-style config (with its `content` glob) instead of relying on auto-detection — then fully restart the Vite dev server (a page reload alone doesn't re-init Tailwind's config resolution).

Known follow-up: the "Run cycle" button in `LiveExecutionConsole.tsx` didn't fire its `onSubmit` under automated/synthetic click testing — needs a real-browser check to confirm whether it's a genuine bug or a synthetic-event artifact.

## Feature parity baseline

React must support the same baseline user journeys as Streamlit before enhancement work:

- Run execution (single/multi config) via `POST /api/v1/executions`
- Live logs + run result updates via SSE
- Run history listing (`GET /api/v1/runs`)
- Run detail + report/artifact links (`GET /api/v1/runs/{run_id}`, `/reports`)

## Rollout and rollback

- Default migration mode: `UQO_UI_MODE=dual`
- Roll forward: route user traffic to React while keeping Streamlit runnable.
- Rollback trigger examples:
  - sustained API errors
  - SSE instability
  - lifecycle persistence mismatch
  - any CLI/CI contract regression
- Rollback action:
  - switch to `UQO_UI_MODE=streamlit`
  - keep backend online for debugging and replay

---
**Context & Links:**
- [[Architecture Overview]], [[QA Strategies]], [[Release Checklist - Phase 3 Frontend Migration]], [[Release Checklist - Phase 3 Unified Dashboard]], [[Product Roadmap#Phase 3: Enterprise UI & Analytics]]
