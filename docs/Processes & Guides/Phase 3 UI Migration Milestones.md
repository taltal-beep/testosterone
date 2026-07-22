# Phase 3 UI Migration Milestones (Streamlit → React + FastAPI)

This document is the execution checklist for migrating the Testo UI from the Streamlit prototype (`testo_ui/streamlit_app.py`) to a decoupled React SPA (`frontend/`) backed by FastAPI (`testo_api/`), while keeping `testo_core` as the single source of truth for orchestration and preserving CI/NDJSON contracts.

References:
- `docs/Architecture/Deep Dive - Execution Logic.md`
- `docs/CLI Commands/Troubleshooting and Error Codes.md`
- `docs/Processes & Guides/Streamlit to React Migration Guide.md`

---

## Phase 0 — Contracts locked (no UI changes)

- **Execution model**: standardize on **plan/cycle execution** (`testo run` lifecycle) as the primary web contract.
- **Streaming transport**: standardize on **SSE** from backend → frontend.
- **Event schema**: SSE `data:` payloads are the same objects as NDJSON `events.ndjson` lines (top-level `event` field and documented payload shapes).

Exit criteria:
- A single written contract for: `plan_started`, `stage_started`, `stage_finished`, `plan_finished`, `plan_aborted`, `cycle_trigger`, `error`.

Rollback:
- Keep Streamlit runnable.

---

## Phase 1 — Backend: plan/cycle execution API (headless)

Deliverables:
- `POST /api/v1/cycles/{cycle}/executions` to start a cycle run.
- `GET /api/v1/cycle-executions/{id}` for execution status.
- `GET /api/v1/cycle-executions/{id}/events` SSE stream that tails `artifacts/<cycle>/events.ndjson`.

Exit criteria:
- A cycle run can be started and observed end-to-end via SSE.
- Durable artifacts are written under `artifacts/<cycle>/` (`events.ndjson`, `plan_result.json`).

Rollback:
- Continue using the existing headless execution endpoints (`/api/v1/executions`) for legacy UI paths.

---

## Phase 2 — Frontend: React scaffold + contract mapping

Deliverables:
- Vite + TypeScript app under `frontend/`.
- Routes/pages:
  - **DashboardHome**: uses `/api/v1/dashboard/overview`
  - **Runner/LiveExecutionConsole**: uses new cycle execution endpoints + SSE
  - **History/ReportViewer**: uses `/api/v1/runs` / `/api/v1/runs/{id}` / `/api/v1/runs/{id}/reports`

Exit criteria:
- The SPA loads, navigates, and can start a cycle run with live event streaming.

Rollback:
- Streamlit remains available for the same user journeys.

---

## Phase 3 — Runner UX hardening (logs + artifacts + reports)

Deliverables:
- Runner view shows:
  - stage timeline and final exit classification
  - direct links to `run.log` (per stage) and `events.ndjson` / `plan_result.json`
- History links open the right report surfaces:
  - Allure Server per `run_id` when configured
  - static report mirrors (Allure/Extent) where available

Exit criteria:
- Feature parity with Streamlit “Execution + Analytics + History” journeys.

Rollback:
- Streamlit stays as fallback while production traffic is gradually shifted.

---

## Phase 4 — Production readiness (multi-user + isolation)

Deliverables:
- Concurrency control per cycle and/or per execution workspace.
- Optional cancellation endpoint(s) and cleanup.
- AuthN/AuthZ if required.
- Better SSE resilience: reconnection with offset semantics (server can support `Last-Event-ID` or explicit offset).

Exit criteria:
- Stable operations under concurrent users, with predictable resource usage and clean teardown.


---

> [!note] Superseded in part (2026-07-04)
> The Phase 3 route map (`/runner`, `/history`, `/execution`) was reorganized by the Phase 5 UI redesign: cycles-first navigation, cycle discovery endpoints, and a consolidated Run panel. Old routes redirect. See [[Phase 5 UI Redesign - Cycles-First Navigation]].
