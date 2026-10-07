# Changelog

All notable changes to `testo-core` will be documented in this file.

This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Added
- Pages demo on GitHub and GitLab: `.github/workflows/pages-demo.yml` (GitHub Pages, `https://<owner>.github.io/<repo>/`) and `.gitlab-ci.yml` (GitLab Pages) each run testosterone's own suite (`self-test` cycle) and the deliberately broken [fake-api](https://github.com/taltal-beep/fake-api) app (`fake-api` cycle), then publishes the React UI as a read-only snapshot of those runs (`scripts/export_static_site.py` freezes the API's own responses; `frontend/src/lib/static-backend.ts` serves them to the unchanged pages). Run history is cached between pipelines. `.github/workflows/mirror-to-gitlab.yml` mirrors `main` to GitLab, inert until configured
- `frontend` CI job in `ci.yml`: runs the React dashboard's typecheck, vitest suite and production build on every PR (the frontend had no CI coverage)
- `POST /api/v1/adhoc-executions`: run one framework (`pytest`, `behave`, `behavex`, `command`) against a repo without defining a cycle. It runs as a one-stage `adhoc` cycle through `CycleRunService`, with status and SSE events under `/api/v1/cycle-executions/{id}`
- Quick Run page in the React frontend (`/quick-run`, under Advanced) built on that endpoint; it replaces the Legacy Execution page
- Engine run records now store failure evidence for failed runs (failing cases, first traceback, log tail, timeout flag; all redacted) for the AI failure summary, and CI provenance (`ci_provider`, `ci_pipeline_id`, `ci_job_id`, `ci_commit_sha`, `ci_ref_name`) when run in CI
- After every cycle run, test KPIs are pushed to InfluxDB and/or a Prometheus Pushgateway when `INFLUXDB_*` / `PROMETHEUS_PUSHGATEWAY_URL` are set

### Changed
- Running a cycle (trigger gate, engine, reporters, native report snapshot, report archive, trigger snapshot) now lives in one application service, `testo_core/services/cycle_run.py` (`CycleRunService`). `testo run` and `POST /api/v1/cycles/{cycle}/executions` both call it, so the API no longer imports private helpers from `testo_core/cli/runner.py`
- API cycle executions now save the trigger snapshot after a successful triggered run, as `testo run` already did; before, a cycle with `trigger:` started from the dashboard never advanced its snapshot
- Frontend API types are now generated from FastAPI's OpenAPI schema (`frontend/openapi.json` → `frontend/src/lib/api-schema.ts`) instead of being hand-written; CI's `frontend` job runs `tsc` and fails on a stale schema or generated file
- `ARCHITECTURE.md` and `README.md` now describe the single execution engine (config → `CycleRunService` → engine → framework adapters → reporting/persistence) with a system diagram, layer table and the typed Pydantic-to-React contract
- `testo_core/run_history.py` is replaced by the `testo_core/history/` package: `views` (typed run views), `read_model` (queries), `report_links`, `snapshots`, `s3_snapshots` (pre-1.1 MinIO lookups only) and `maintenance`. All of it goes through the run repository, which gains `merge_run_metadata()`; `STATIC_HISTORY_ROOT` moves to `testo_core.paths`
- GitHub Action and GitLab template now run `testo run --ci` (they called `uqo run --config … --ghost`, which v1.0's `uqo` alias no longer accepted). Action inputs are `config-path`, `cycle`, `ci-mode`, `persist`, `python-version`; `ghost-mode`, `stream-json`, `runner-image`, `runner-prebuilt` and the `run_id` output are gone. GitLab variables are now `TESTO_CONFIG_PATH`, `TESTO_CYCLE`, `TESTO_PERSIST`
- CI's `format` job now blocks on `mypy testo_core` and `ruff format --check` (both were advisory); the codebase was reformatted once with `ruff format`, and a `ruff-format` pre-commit hook was added

### Removed
- The second, Docker-based execution stack: `HeadlessEngineService`, `testo_core/runners.py`, `command_builders.py`, `multi_run.py`, `event_drain.py`, `config_loader.py`, `audit_service.py`, `ghost_policy.py`, `result_management.py`, and the pluggy `orchestrator.py` / `specs.py` / `plugins_builtin.py`. Every run now goes through the cycle engine
- The v1.0 `uqo run --config <runs.yaml>` contract (`--ghost`, `--no-ghost`, `--json`, `--stream-json`, summary JSON). `uqo` still forwards to `testo`; use `testo run --cycle <name> --ci`
- `POST /api/v1/executions`, `GET /api/v1/executions/{id}` and `GET /api/v1/executions/{id}/events`; use `POST /api/v1/adhoc-executions` or `POST /api/v1/cycles/{cycle}/executions`
- The Streamlit UI (`testo_ui/`, `testo-ui` script, `ui` extra), as scheduled in 1.0.0
- The `docker` extra and the `pluggy` runtime dependency
- Run-history writer functions in `run_history.py` (`create_run`, `record_completed_run`, MinIO uploads), the unused `compare_latest_two()` and the `db_path` arguments on history queries
- Generated run output that was committed by mistake (`artifacts/allure-report*`, `artifacts/allure-results-archive/`, `artifacts/metrics.json`); these paths are now ignored
- `testo_core/reporting/allure_delta_transform.py`, `allure_history_serve.py` and `allure_summary_widgets.py`: unreferenced modules that could not be imported (they depended on functions no longer in `services/report_archive_diff.py`)

### Fixed
- The test pyramid (`testo report pyramid`, `/api/v1/runs/{id}/pyramid`) bucketed a run by the tiers in the *current* `testosterone.yaml`, so renaming a stage re-counted old runs as "unit". Run records now store each stage's `tier`; only older records without one fall back to the YAML
- A `command` stage's `junit_xml:` reports were never imported by `testo run` or the API, so the stage showed 0 tests and PASS. Cycle resolution and the `--workers` override rebuilt each stage without its `junit_xml` and `tier`; they now copy the stage with `dataclasses.replace`
- Pytest stages ignored the target repo's own pytest config (`pythonpath`, markers) when the target sat inside another pytest project, such as a repo cloned into the testosterone checkout in CI, so tests failed to import the target's code. The adapter passed `--alluredir <path>` as two tokens, and pytest counted the results path when choosing its rootdir; it now passes `--alluredir=<path>`
- Compare's test-level changes were always empty for two runs of the same cycle, and a run's artifact download returned whichever run of that cycle came last. Run records pointed `snapshot_dir` at the shared `artifacts/<cycle>/` tree, which every run overwrites; each run now keeps its own copy at `static/history/<run_id>/artifacts/`
- Frontend typecheck errors surfaced by the generated types: `/health/ready` is typed `"ready" | "degraded"` as the API returns, and `StatusPill` handles a `null` status
- `mypy testo_core` reports 0 errors, down from 59: reporters take a typed Rich `Console`, `testo report` narrows its optional open path before use, and the persistence, repository and CLI UI code is fully annotated
- `equipment: behavex`: every BehaveX stage failed at startup with `OSError: AF_UNIX path too long`, because BehaveX points `TEMP` at its output folder and the multiprocessing socket landed there; the adapter now pins `TMPDIR` to the system temp dir
- API errors surfaced in the UI as `API error <status>`; the client now shows the message the API returned, and the Run detail page reports a failed AI-summary request instead of swallowing it
- Run detail, dashboard and compare showed a wall duration of 0 ms for every cycle run; engine-sourced records store `duration_s`, which the history view now falls back to

---

## [1.0.0] - 2026-09-27

First public release. Published to PyPI (`testo-core`), GHCR (`testo-runner`), and JFrog Artifactory.

### Deprecated
- `testo-ui` / Streamlit interface: prints a deprecation notice on stderr and is scheduled for removal in v1.1. The React frontend (`frontend/`) is the official UI.
- `uqo` CLI alias: continues to forward to `testo`; removal in a future release.

### Added
- `.pre-commit-config.yaml`: local `ruff`, changelog-format, and whitespace/YAML/TOML hooks (`pre-commit install` to enable)
- `mypy` type-check tooling: `[tool.mypy]` config in `pyproject.toml`, advisory step in `ci.yml`'s `format` job
- Extended `[tool.ruff.lint]` selection (added `UP`, `B`) and made `ruff check` blocking in `ci.yml` now that the tree is clean
- `changelog_required` CI gate in `ci.yml`: fails PRs with non-doc changes that don't touch `CHANGELOG.md` (escape hatch: `no-changelog` label)
- `commitlint` CI check (`.github/workflows/commitlint.yml`, `commitlint.config.js`) enforcing Conventional Commits on PR commit messages
- `changelog-on-main.yml`: AI-drafted `CHANGELOG.md [Unreleased]` entries on push to `main`, gated by `scripts/check_changelog_format.py` — see `docs/changelog_automation_policy.md` for the review-step tradeoff and required secrets/branch-protection setup
- `CONTRIBUTING.md`, `.github/PULL_REQUEST_TEMPLATE.md`, `.github/ISSUE_TEMPLATE/` (bug report, feature request), and `CODEOWNERS`
- Root-level `CLAUDE.md` pointing any directly-invoked AI agent at `docs/Index.md` and the Agent Context Guide
- Persistence module with `PersistenceBackend` protocol, JSON and DB backends
- Single-sourced `EngineExitCode` across modern and legacy execution stacks
- Contract tests asserting exit code consistency between stacks
- Execution stack boundary documentation in Architecture Overview
- `_SENSITIVE_KEY_PATTERN` in `redaction.py` to detect sensitive mapping keys (#35)
- `_redacted_context_text()` in `failure_context_builder.py` for structured metadata redaction (#35)
- Allure failure context wiring in `record_completed_run()` for run recording (#35)
- `equipment: command`: run any test runner (Jest, Playwright, Maestro, `go test`, ...) as a stage. `args` is the full argv
- Stage key `junit_xml` (glob or list, relative to `target_repo`): JUnit XML written by the stage is converted into Allure results after it exits, so non-Allure runners count in summaries, health % and every reporter (`testo_core/reporting/junit_import.py`)
- `artifactory-publish.yml`: mirrors the release to JFrog Artifactory (PyPI + Docker repos), inert until `ARTIFACTORY_URL` is set — see `docs/Processes & Guides/Publishing to Artifactory.md`

### Changed
- `--no-persist` / `--persist` CLI flags with clarified semantics
- `classify_exit_code` consolidated into `engine/exit_codes.py`
- Literal exit code constants in CLI replaced with `EngineExitCode` enum

### Fixed
- Sprint 2 release gate execution across all 4 phases
- Contract test assertion mismatch (`--plan` vs `--cycle`)
- Allure CLI unit test mock for `resolve_allure_command`
- `publish.yml`: post-publish verification installed `testo-core==v1.0.0` from the raw git tag, which is not a valid version specifier; the leading `v` is now stripped
- `docker-publish.yml`: Trivy scan and verify steps referenced an image tag that never existed (`docker/metadata-action` strips the `v`); both now use the resolved metadata version
- `docker-publish.yml`: the `latest` tag was gated on `is_default_branch`, which is never true for a release event, so `latest` would never have been published
- `.gitattributes`: GitHub reported the repository as HTML because the generated 3.2 MB `artifacts/allure-report/index.html` outweighed all authored Python and TypeScript; generated and vendored paths are now excluded from language statistics
- `Dockerfile.testo-runner`: the image ran as root, which fails the release workflow's blocking Trivy config scan (DS002, HIGH); it now runs as an unprivileged `testo` user, and the entrypoint is `testo` instead of the deprecated `uqo` alias

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

[Unreleased]: https://github.com/taltal-beep/testosterone/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/taltal-beep/testosterone/compare/v0.1.0...v1.0.0
[0.1.0]: https://github.com/taltal-beep/testosterone/releases/tag/v0.1.0
