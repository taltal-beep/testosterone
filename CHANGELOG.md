# Changelog

All notable changes to `testo-core` will be documented in this file.

This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Added
- `.pre-commit-config.yaml`: local `ruff`, changelog-format, and whitespace/YAML/TOML hooks (`pre-commit install` to enable)
- `mypy` type-check tooling: `[tool.mypy]` config in `pyproject.toml`, advisory step in `ci.yml`'s `format` job
- Extended `[tool.ruff.lint]` selection (added `UP`, `B`) and made `ruff check` blocking in `ci.yml` now that the tree is clean
- Persistence module with `PersistenceBackend` protocol, JSON and DB backends
- Single-sourced `EngineExitCode` across modern and legacy execution stacks
- Contract tests asserting exit code consistency between stacks
- Execution stack boundary documentation in Architecture Overview

### Changed
- `--no-persist` / `--persist` CLI flags with clarified semantics
- `classify_exit_code` consolidated into `engine/exit_codes.py`
- Literal exit code constants in CLI replaced with `EngineExitCode` enum

### Fixed
- Sprint 2 release gate execution across all 4 phases
- Contract test assertion mismatch (`--plan` vs `--cycle`)
- Allure CLI unit test mock for `resolve_allure_command`

---

## [0.1.0] — Phase 1–4 Feature Complete

### Phase 4: BYOK AI Failure Summaries

*AI-powered test failure analysis with bring-your-own-key provider support.*

#### Added
- `testo_core/services/failure_analysis_service.py` — context-aware AI failure summary generation
- `PUT /api/v1/ai/config` — runtime AI provider/model configuration (memory-only key storage)
- `GET /api/v1/runs/{run_id}/ai-summary` — cached AI summary retrieval
- `POST /api/v1/runs/{run_id}/ai-summary:generate` — on-demand summary generation for failed runs
- `GET /api/v1/ai/config/status` — non-secret AI configuration status endpoint
- React AI Settings page (`/settings/ai`) — provider config, key management, model selection
- AI summary display on Run Detail page (`/runs/:runId`)
- AI summary caching — generate once, retrieve cached on refresh
- AI failure context capture tests
- Passing-run AI summary skip regression test

#### Security
- Raw API keys never returned by backend responses
- Runtime key input memory-only by default (not persisted to DB/files)
- Token-like values redacted from internal error surfaces before transport
- AI integration explicit opt-in (`enabled=false` by default)

#### Fixed
- AI summary refresh data loss on forced refresh failure (#32)
- AI failure summary and context builder regression coverage (#33, #34)

---

### Phase 3: Unified Dashboard, Delta Engine, Frontend Migration

*React frontend, run comparison analytics, and unified dashboard.*

#### Added
- FastAPI backend (`testo_api/`) — thin adapter over `HeadlessEngineService`
- React frontend (`frontend/`) — Vite + React + Tailwind dashboard
- Dashboard overview page (`/`) — KPI cards, trend badges, drill-down links
- Delta comparison engine (`testo_core/services/delta_service.py`) — regression/improvement classification
- Compare page (`/compare`) — run selection and delta visualization
- SSE client (`frontend/src/lib/sse-client.ts`) — real-time execution log streaming
- `GET /api/v1/dashboard/overview` — unified dashboard payload endpoint
- `GET /api/v1/analytics/delta` — core-owned run delta comparison endpoint
- `POST /api/v1/executions` — create run execution job endpoint
- `GET /api/v1/executions/{id}/events` — SSE stream for log/result/summary events
- Health probes: `GET /api/v1/health/live`, `GET /api/v1/health/ready`
- Degraded-data behavior (n/a display, degraded banner, missing report links)
- Report DB archives, diff CLI, Allure history, hybrid cycles
- Report archive extraction path hardening (#28, #30)
- Report archive diff regression tests (#27, #29)
- Execution accepted-status regression test (#26)
- Frontend unit tests (Vitest) and E2E test harness

#### Fixed
- Race condition in 202 Accepted response status for `/executions`

---

### Phase 2: CI Integrations, Ghost Mode, Runner Image

*CI wrappers, headless ghost execution, and prebuilt Docker runner.*

#### Added
- GitHub Action wrapper (`ariel-evn/uqo-action@v1`) with typed inputs/outputs
- GitLab CI template (`ci/gitlab/testo.gitlab-ci.yml`)
- Ghost mode — CI auto-detection for GitHub, GitLab, Buildkite, CircleCI, Jenkins, Azure Pipelines
- `--ghost` / `--no-ghost` / `--ci` CLI flags with precedence rules
- `Dockerfile.testo-runner` — prebuilt runner image for CI execution
- Configurable runner image path (`UQO_RUNNER_IMAGE`)
- NDJSON event streaming (`--stream-json`) for CI log consumption
- Ghost summary and NDJSON contract tests
- CI provenance unit tests
- GitHub Action and GitLab wrapper contract tests

#### Changed
- Renamed `uqo`-prefixed CI files to `testo`-prefixed

---

### Phase 1: Foundation

*Core engine, CLI, packaging, database adapters, Allure reporting.*

#### Added
- `testo_core/` — config-driven orchestration engine reading `testosterone.yaml`
- `testo` CLI entrypoint (via Typer) with `run`, `report`, `cycles`, `config` subcommands
- `uqo` legacy CLI alias (deprecated)
- Framework adapters: `PytestAdapter`, `BehaveAdapter`, `BehaveXAdapter`
- Repository pattern (`testo_core/repository/`) — SQLite default, Postgres/MySQL optional
- Allure reporting pipeline with per-framework isolation and unified reports
- MinIO S3 artifact storage (`testo_core/s3_client.py`)
- Docker-based ephemeral test execution (`testo_core/runners.py`)
- Dockerless local fallback when Docker is unavailable
- Streamlit UI (`testo_ui/`) for interactive execution and history
- Pluggy-based plugin system for drop-in runner extensions
- Shared headless engine service (`testo_core/services/headless_engine.py`)
- Hatchling-based packaging (`pyproject.toml`) with extras: `ui`, `api`, `db`, `docker`, `metrics`, `dev`
- Stable exit codes: 0 (success), 1 (test failure), 2 (invalid input), 3 (infra failure), 4 (internal error)
- Crash recovery: orphaned `RUNNING` rows auto-marked `FAILED` on startup
- Container timeout safety net (`UQO_CONTAINER_TIMEOUT_S`)
- Docker Compose infrastructure: Postgres, MinIO, Allure static host, Allure sync

#### Fixed
- Docker runner path mapping
- Mock API and built-in Pluggy hooks restoration
- Multi-run batch locking until complete
- Multi-run polling active until batch ends

---

[Unreleased]: https://github.com/taltal-beep/unified-quality-orchestration-reporting-dashboard/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/taltal-beep/unified-quality-orchestration-reporting-dashboard/releases/tag/v0.1.0
