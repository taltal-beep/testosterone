# Streamlit to React Migration Guide (Phase 3)

## Goal

Move dashboard UX from Streamlit to React while keeping `uqo_core` as the only orchestration engine and preserving CLI/CI contracts.

## Transitional topology

- Streamlit remains available as rollback UI.
- FastAPI (`uqo_api`) exposes `/api/v1` JSON + SSE contracts.
- React (`frontend/`) consumes FastAPI endpoints for execution/history/report flows.
- CLI and CI wrappers remain unchanged (`uqo run ...` contract preserved).

## Local developer workflow

1. Start infrastructure:
   - `docker compose up -d`
2. Start backend:
   - `uvicorn uqo_api.main:app --host 0.0.0.0 --port 8000 --reload`
3. Start React frontend:
   - `npm --prefix frontend install`
   - `npm --prefix frontend run dev`
4. Optional Streamlit fallback:
   - `UQO_UI_MODE=dual streamlit run app.py`

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
