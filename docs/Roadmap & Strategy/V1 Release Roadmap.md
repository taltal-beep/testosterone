# V1 Release Roadmap — Task Breakdown

[[Index]] · [[Product Roadmap]] · [[Technical Debt Tracker]]

> **Created:** 2026-06-24
> **Goal:** Ship `testo-core` v1.0.0 — a production-ready, published, fully-gated release.
> **Current state:** All 4 delivery phases are implemented in code. Zero TODO/FIXME/HACK markers. 123+ test files. But: no release checklists executed, not on PyPI, persistence module missing, 16 draft PRs unmerged, 14 tech-debt items open.

---

## Priority Legend

| Priority | Meaning |
|----------|---------|
| **P0** | Release blocker — must be done before v1.0 tag |
| **P1** | High — should be done before v1.0, significant risk if skipped |
| **P2** | Medium — quality/hardening, can ship without but degrades confidence |
| **P3** | Low — future work, nice-to-have, post-v1.0 |

## Effort Legend

| Effort | Meaning |
|--------|---------|
| **XS** | < 30 min |
| **S** | 30 min – 2 hours |
| **M** | 2 – 4 hours |
| **L** | 4 – 8 hours (1 day) |
| **XL** | 1 – 3 days |

---

## Workstream 1: Merge Draft PRs (Critical Bugs & Coverage)

**Why:** 16 draft PRs contain correctness fixes and test coverage that must land before any release gate can pass. Critical bugs in report artifact paths could cause data loss or broken reports in production.

**Execution order:** Bugs first (data loss risk), then coverage, then automation.

### 1.1 Critical Correctness Bugs

| # | Task | PR | Priority | Effort | Depends On |
|---|------|----|----------|--------|------------|
| 1.1.1 | Review and merge: Fix AI summary refresh data loss and failed-run generation wiring | [PR #22](../../pull/22) | P0 | S | — |
| 1.1.2 | Review and merge: Harden report archive extraction paths | [PR #28](../../pull/28) | P0 | S | — |
| 1.1.3 | Review and merge: Harden report artifact path handling | [PR #30](../../pull/30) | P0 | S | 1.1.2 |

### 1.2 Bug Fixes

| # | Task | PR | Priority | Effort | Depends On |
|---|------|----|----------|--------|------------|
| 1.2.1 | Review and merge: Fix execution accepted-status race condition | [PR #26](../../pull/26) | P1 | XS | — |
| 1.2.2 | Review and merge: Fix sandbox/mock API support restoration | Draft PR | P1 | XS | — |
| 1.2.3 | Review and merge: Dockerless runner allure analytics fallback | Draft PR | P2 | XS | — |

### 1.3 Missing Test Coverage

| # | Task | PR | Priority | Effort | Depends On |
|---|------|----|----------|--------|------------|
| 1.3.1 | Review and merge: AI failure summary service coverage | [PR #21](../../pull/21) | P1 | S | 1.1.1 |
| 1.3.2 | Review and merge: AI failure summary regression coverage (set 1) | [PR #23](../../pull/23) | P1 | S | 1.3.1 |
| 1.3.3 | Review and merge: AI failure summary regression coverage (set 2) | [PR #24](../../pull/24) | P1 | S | 1.3.1 |
| 1.3.4 | Review and merge: Execution accepted status coverage | [PR #26](../../pull/26) | P1 | S | 1.2.1 |
| 1.3.5 | Review and merge: Report archive diff regression coverage (set 1) | [PR #27](../../pull/27) | P1 | S | 1.1.2 |
| 1.3.6 | Review and merge: Report archive diff regression coverage (set 2) | [PR #29](../../pull/29) | P1 | S | 1.1.2 |

### 1.4 CI Automation

| # | Task | PR | Priority | Effort | Depends On |
|---|------|----|----------|--------|------------|
| 1.4.1 | Review and merge: Claude AI code review workflow | [PR #31](../../pull/31) | P2 | XS | — |

---

## Workstream 2: Release Gate Execution

**Why:** All 8 release checklists have 0/210 items checked. The roadmap says phases are "done" but the operational go/no-go gates were never run. Without formal sign-off, there's no proof of release readiness.

**Execution order:** Phase 1 → 2 → 3 → 4 (each phase builds on prior).

### 2.1 Phase 1 Foundation Gate

| # | Task | Priority | Effort | Depends On |
|---|------|----------|--------|------------|
| 2.1.1 | Run Phase 1 pre-reqs: `pip install -e '.[dev]'` and `python -m build` in clean venv | P0 | XS | 1.1.* |
| 2.1.2 | Run Phase 1 CLI contract tests: `pytest tests/unit/testo_core/test_cli_run.py tests/contract/testo_core/test_cli_contract.py` | P0 | XS | 2.1.1 |
| 2.1.3 | Run Phase 1 repository tests: `pytest tests/unit/testo_core/test_repository_sqlite.py tests/contract/testo_core/test_repository_contract.py` | P0 | XS | 2.1.1 |
| 2.1.4 | Verify `testo run --help` and `testo --version` output | P0 | XS | 2.1.1 |
| 2.1.5 | Check off all items in `docs/Release Management/Release Checklist - Phase 1 Foundation.md` | P0 | S | 2.1.2–2.1.4 |

### 2.2 Phase 2 CI/Ghost/Runner Gates

| # | Task | Priority | Effort | Depends On |
|---|------|----------|--------|------------|
| 2.2.1 | Run Phase 2 CI integration tests: `pytest tests/unit/ci/test_github_action_wrapper.py tests/contract/ci/test_wrapper_contract.py` | P0 | XS | 2.1.5 |
| 2.2.2 | Run Phase 2 Ghost mode smoke: `pytest tests/integration/test_ghost_mode_smoke.py` | P0 | S | 2.1.5 |
| 2.2.3 | Run Phase 2 Runner image smoke: build `Dockerfile.testo-runner` and verify `docker run --rm uqo-runner:rc run --help` | P0 | S | 2.1.5 |
| 2.2.4 | Run Ghost policy + CI provenance unit tests | P0 | XS | 2.1.5 |
| 2.2.5 | Run NDJSON contract tests: `pytest tests/contract/testo_core/test_ghost_summary_contract.py tests/contract/testo_core/test_ghost_ndjson_contract.py` | P0 | XS | 2.1.5 |
| 2.2.6 | Check off all items in `Release Checklist - Phase 2 CI Integrations.md` | P0 | S | 2.2.1–2.2.5 |
| 2.2.7 | Check off all items in `Release Checklist - Phase 2 Ghost Mode.md` | P0 | S | 2.2.2, 2.2.4, 2.2.5 |
| 2.2.8 | Check off all items in `Release Checklist - Phase 2 Runner Image.md` | P0 | S | 2.2.3 |

### 2.3 Phase 3 UI/Delta/Dashboard Gates

| # | Task | Priority | Effort | Depends On |
|---|------|----------|--------|------------|
| 2.3.1 | Run dashboard service + contract tests: `pytest tests/unit/testo_core/test_dashboard_service.py tests/contract/api/test_dashboard_contract.py` | P0 | XS | 2.2.6 |
| 2.3.2 | Run delta analytics + comparison contract tests: `pytest tests/contract/api/test_analytics_contract.py` | P0 | XS | 2.2.6 |
| 2.3.3 | Run frontend unit tests: `npm --prefix frontend run test` | P0 | S | 2.2.6 |
| 2.3.4 | Run frontend E2E tests: `npm --prefix frontend run test:e2e` | P0 | S | 2.3.3 |
| 2.3.5 | Manual verify: Dashboard `/` renders KPI cards, trend badges, drill-down links | P0 | S | 2.3.3 |
| 2.3.6 | Manual verify: Compare page `/compare` selects runs and shows delta visualization | P0 | S | 2.3.2 |
| 2.3.7 | Manual verify: degraded-data behavior (n/a display, degraded banner, missing report links) | P1 | S | 2.3.5 |
| 2.3.8 | Check off all items in `Release Checklist - Phase 3 Frontend Migration.md` | P0 | S | 2.3.1–2.3.7 |
| 2.3.9 | Check off all items in `Release Checklist - Phase 3 Delta Engine.md` | P0 | S | 2.3.2, 2.3.6 |
| 2.3.10 | Check off all items in `Release Checklist - Phase 3 Unified Dashboard.md` | P0 | S | 2.3.5, 2.3.7 |

### 2.4 Phase 4 AI Gate

| # | Task | Priority | Effort | Depends On |
|---|------|----------|--------|------------|
| 2.4.1 | Run AI service unit tests: `pytest tests/unit/testo_core/test_failure_analysis_service.py` | P0 | XS | 2.3.8 |
| 2.4.2 | Run AI contract tests: `pytest tests/contract/api/test_ai_contract.py` | P0 | XS | 2.3.8 |
| 2.4.3 | Manual verify: AI Settings page `/settings/ai` — provider config, key management, model selection | P0 | S | 2.4.1 |
| 2.4.4 | Manual verify: Run Detail `/runs/:runId` — AI summary generation with configured provider | P0 | S | 2.4.1 |
| 2.4.5 | Verify AI summary caching (generate once, retrieve cached on refresh) | P1 | S | 2.4.4 |
| 2.4.6 | Check off all items in `Release Checklist - Phase 4 AI and Failure Analysis.md` | P0 | S | 2.4.1–2.4.5 |

---

## Workstream 3: Persistence Module

**Why:** `orchestrator.py:228` promises `testo_core.persistence` for Phase 4. The engine layer currently writes `plan_result.json` only. The services layer has DB persistence (`headless_engine.py`, `run_history.py`), but the engine doesn't. This is confusing and the `--no-persist` flag name is misleading.

**Decision needed:** Build the module, or formally document JSON-only approach and rename flags.

### 3.1 Option A: Implement Persistence Module

| # | Task | Priority | Effort | Depends On |
|---|------|----------|--------|------------|
| 3.1.1 | Design `testo_core/persistence/` module interface: what data flows from engine to DB | P0 | S | — |
| 3.1.2 | Create `testo_core/persistence/__init__.py` with `PersistenceBackend` protocol | P0 | S | 3.1.1 |
| 3.1.3 | Create `testo_core/persistence/json_backend.py` — extract current `_try_persist` logic | P0 | M | 3.1.2 |
| 3.1.4 | Create `testo_core/persistence/db_backend.py` — wire to existing `RunRepository` | P0 | M | 3.1.2 |
| 3.1.5 | Integrate persistence backend into `orchestrator.run_plan()` replacing `_try_persist` | P0 | M | 3.1.3, 3.1.4 |
| 3.1.6 | Update `--no-persist` / `--persist` CLI flags with clear semantics | P0 | S | 3.1.5 |
| 3.1.7 | Add unit tests for JSON and DB persistence backends | P0 | M | 3.1.5 |
| 3.1.8 | Update `orchestrator.py` docstring to remove "wired up in Phase 4" reference | P0 | XS | 3.1.5 |
| 3.1.9 | Update `docs/Architecture/Architecture Overview.md` with persistence layer | P1 | S | 3.1.5 |
| 3.1.10 | Update Technical Debt Tracker item #4 as fixed | P1 | XS | 3.1.5 |

### 3.2 Option B: Document JSON-Only Approach

| # | Task | Priority | Effort | Depends On |
|---|------|----------|--------|------------|
| 3.2.1 | Rename `--no-persist` to `--no-artifact-json` or similar | P0 | S | — |
| 3.2.2 | Update `orchestrator.py` docstring to reflect JSON-only design decision | P0 | XS | — |
| 3.2.3 | Document that DB persistence lives in services layer, not engine layer | P0 | S | — |
| 3.2.4 | Add ADR: "Engine persistence is JSON-only; DB persistence via services" | P1 | S | 3.2.3 |
| 3.2.5 | Update Technical Debt Tracker item #4 to "Resolved — by design" | P1 | XS | 3.2.2 |

---

## Workstream 4: Consolidate Dual Execution Stacks

**Why:** Modern engine (`orchestrator.py` + `executor.py`) and legacy stack (`headless_engine.py` + `runners.py`) have duplicate `EngineExitCode`, duplicate classification logic, and risk behavioral drift. Tech Debt Tracker items #2 and #12.

| # | Task | Priority | Effort | Depends On |
|---|------|----------|--------|------------|
| 4.1 | Audit: map all callers of `headless_engine.py` vs `orchestrator.py` — document which CLI/API paths use which | P1 | M | 1.1.* |
| 4.2 | Single-source `EngineExitCode`: keep in `engine/exit_codes.py`, import in `headless_engine.py` | P1 | S | 4.1 |
| 4.3 | Single-source `classify_exit_code`: remove duplicate from `headless_engine.py` | P1 | S | 4.2 |
| 4.4 | Replace literal exit code constants in CLI (`raise typer.Exit(code=2)`) with `EngineExitCode.INVALID_INPUT` | P2 | S | 4.2 |
| 4.5 | Add contract test asserting both stacks produce identical exit codes for same inputs | P1 | M | 4.3 |
| 4.6 | Document boundary: which stack handles what (in Architecture Overview or ADR) | P1 | S | 4.1 |
| 4.7 | Long-term: design `RunBackend` protocol with host and Docker implementations | P3 | L | 4.6 |
| 4.8 | Update Technical Debt Tracker items #2, #6, #12 as resolved | P1 | XS | 4.3, 4.4 |

---

## Workstream 5: Exception Handling Hardening

**Why:** Broad `except Exception` in Docker/S3/reporter paths causes silent degradation — empty reports, stale DB rows, swallowed errors. Tech Debt Tracker items #5, #7, #8, #9, #10.

| # | Task | Priority | Effort | Depends On |
|---|------|----------|--------|------------|
| 5.1 | Audit: list all `except Exception` sites in `runners.py`, `run_history.py`, reporter clients | P2 | S | — |
| 5.2 | Narrow `runners.py` Docker exception handlers to `docker.errors.DockerException`, `OSError`, `TimeoutError` | P2 | M | 5.1 |
| 5.3 | Narrow `run_history.py` S3/DB handlers to `ClientError`, `SQLAlchemyError` | P2 | M | 5.1 |
| 5.4 | Narrow reporter exception handlers (`extent_reporter.py`, `reportportal_client.py`, `testbeats_reporter.py`) | P2 | M | 5.1 |
| 5.5 | Add `logger.warning(..., exc_info=True)` to all narrowed handlers | P2 | S | 5.2–5.4 |
| 5.6 | Fix swallowed BehaveX/native report errors: set `StageResult.error` when HTML generation fails | P2 | S | — |
| 5.7 | Reporter factory: add `reporters_required` config option or emit `reporter_failed` NDJSON event | P2 | M | 5.4 |
| 5.8 | Git trigger fallback: emit `{"event":"trigger_fallback","mode":"snapshot","reason":"..."}` NDJSON when `--ci` | P2 | S | — |
| 5.9 | Orchestrator defensive catch: re-raise `KeyboardInterrupt`/`SystemExit`, narrow to adapter errors, use exit 4 for internal | P2 | S | — |
| 5.10 | Update Technical Debt Tracker items #5, #7, #8, #9, #10 as resolved | P2 | XS | 5.2–5.9 |

---

## Workstream 6: Documentation & CHANGELOG

**Status (2026-07-01):** 6.1–6.5 complete — `CHANGELOG.md` created at repo root (adopted from `sprint-4/publish-and-document`, extended with commit `#35`), with PR-time enforcement (commitlint + changelog-diff check) and an AI-drafted `[Unreleased]` step on every push to `main`. 6.6–6.9 verified already satisfied — `README.md` has GitHub Action quickstart, GitLab template quickstart, required secrets/variables, and CI troubleshooting sections. See [[Changelog Automation and CI Enforcement Policy]].

**Why:** No CHANGELOG exists. README may lack CI quickstarts. Docs lack "last updated" dates. Release checklists serve as templates but don't record actual sign-offs.

| # | Task | Priority | Effort | Depends On |
|---|------|----------|--------|------------|
| 6.1 | Create `CHANGELOG.md` at repo root with entries for all 4 phases derived from git history | P0 | M | — |
| 6.2 | Add Phase 1 changelog entry: DB adapters, PyPI packaging, headless CLI | P0 | XS | 6.1 |
| 6.3 | Add Phase 2 changelog entry: GitHub Action, GitLab template, Ghost mode, Runner image | P0 | XS | 6.1 |
| 6.4 | Add Phase 3 changelog entry: React frontend, Delta comparison, Unified dashboard | P0 | XS | 6.1 |
| 6.5 | Add Phase 4 changelog entry: BYOK AI, Context-aware failure analysis | P0 | XS | 6.1 |
| 6.6 | Verify README contains GitHub Action quickstart snippet | P1 | S | — |
| 6.7 | Verify README contains GitLab template quickstart snippet | P1 | S | — |
| 6.8 | Verify README contains required variables/secrets section | P1 | S | — |
| 6.9 | Verify README contains troubleshooting section | P1 | S | — |
| 6.10 | Add frontmatter `last-updated: YYYY-MM-DD` to all docs in `docs/Architecture/` | P3 | S | — |
| 6.11 | Add frontmatter `last-updated: YYYY-MM-DD` to all docs in `docs/CLI Commands/` | P3 | S | — |
| 6.12 | Add frontmatter `last-updated: YYYY-MM-DD` to all docs in `docs/Specs & ADRs/` | P3 | S | — |

---

## Workstream 7: PyPI Publish Pipeline

**Why:** Phase 1 promises `pip install testo-core`. The package is not on PyPI and no publish workflow exists.

| # | Task | Priority | Effort | Depends On |
|---|------|----------|--------|------------|
| 7.1 | Register `testo-core` package name on PyPI (or Test PyPI first) | P0 | S | — |
| 7.2 | Create `.github/workflows/publish.yml` — triggered on GitHub Release tag push | P0 | M | 7.1 |
| 7.3 | Configure trusted publisher (OIDC) for GitHub → PyPI auth (no API token in secrets) | P0 | S | 7.1 |
| 7.4 | Add `python -m build` and `twine check dist/*` to publish workflow | P0 | S | 7.2 |
| 7.5 | Add Test PyPI dry-run step before real publish | P1 | S | 7.2 |
| 7.6 | Test end-to-end: create a test release, verify `pip install testo-core` works from PyPI | P0 | M | 7.4 |
| 7.7 | Document publish process in `docs/Processes & Guides/Publishing to PyPI.md` | P1 | S | 7.6 |

---

## Workstream 8: Docker Image Publish Pipeline

**Why:** `Dockerfile.testo-runner` exists but has no CI for building/pushing to a registry. Phase 2 promises a pre-built runner image.

| # | Task | Priority | Effort | Depends On |
|---|------|----------|--------|------------|
| 8.1 | Choose container registry (GitHub Container Registry recommended — free for public repos) | P1 | XS | — |
| 8.2 | Create `.github/workflows/docker-publish.yml` — triggered on release tag | P1 | M | 8.1 |
| 8.3 | Add multi-arch build support (`linux/amd64`, `linux/arm64`) via `docker buildx` | P2 | S | 8.2 |
| 8.4 | Add image scanning step (e.g. `trivy`) to CI before publish | P2 | S | 8.2 |
| 8.5 | Tag images with semver + `latest` + commit SHA | P1 | S | 8.2 |
| 8.6 | Test end-to-end: pull published image, run `uqo run --help` | P1 | S | 8.5 |
| 8.7 | Update README with published image pull command | P1 | XS | 8.6 |
| 8.8 | Update `docker-compose.yml` to use published image instead of local build | P2 | S | 8.6 |

---

## Workstream 9: Streamlit Legacy Cleanup

**Why:** `testo_ui/` (Streamlit) still exists alongside React frontend. No formal deprecation or removal plan. Running both causes confusion about which UI is "official."

| # | Task | Priority | Effort | Depends On |
|---|------|----------|--------|------------|
| 9.1 | Confirm React frontend covers all Streamlit UI functionality (feature parity audit) | P1 | M | 2.3.* |
| 9.2 | Add deprecation warning to `testo-ui` entrypoint: "Streamlit UI is deprecated, use React frontend" | P1 | XS | 9.1 |
| 9.3 | Remove `UQO_UI_MODE=dual|streamlit` mode toggle logic | P2 | S | 9.2 |
| 9.4 | Remove `testo_ui/` directory and `testo-ui` entrypoint from `pyproject.toml` | P2 | S | 9.3 |
| 9.5 | Remove `streamlit` from `[ui]` extras in `pyproject.toml` | P2 | XS | 9.4 |
| 9.6 | Update `docs/Processes & Guides/Streamlit to React Migration Guide.md` to mark migration complete | P2 | XS | 9.4 |
| 9.7 | Remove dual-mode integration tests (`tests/integration/test_dual_mode_ui.py` if exists) | P2 | XS | 9.4 |

---

## Workstream 10: Version Bump & v1.0 Release

**Why:** Version is still `0.1.0` despite 4 phases of features. The final step is tagging and publishing v1.0.0.

| # | Task | Priority | Effort | Depends On |
|---|------|----------|--------|------------|
| 10.1 | Bump version to `1.0.0` in `pyproject.toml` | P0 | XS | All P0 tasks |
| 10.2 | Final CHANGELOG entry for v1.0.0 | P0 | S | 6.1, 10.1 |
| 10.3 | Create Git tag `v1.0.0` | P0 | XS | 10.2 |
| 10.4 | Create GitHub Release from tag with changelog notes | P0 | S | 10.3 |
| 10.5 | Verify PyPI publish triggered and successful | P0 | S | 7.*, 10.4 |
| 10.6 | Verify Docker image publish triggered and successful | P1 | S | 8.*, 10.4 |
| 10.7 | Smoke test: `pip install testo-core==1.0.0` in clean venv → `testo --version` | P0 | XS | 10.5 |
| 10.8 | Announce release (README badge, GitHub Release notes) | P1 | S | 10.7 |

---

## Workstream 11: Future Work (Post-v1.0)

**Not blocking v1.0. Tracked here for visibility.**

### 11.1 Parallel Stage Execution

| # | Task | Priority | Effort |
|---|------|----------|--------|
| 11.1.1 | Design parallel stage execution model (resource limits, artifact isolation) | P3 | M |
| 11.1.2 | Implement `concurrent.futures` or `asyncio` stage runner in orchestrator | P3 | L |
| 11.1.3 | Add `parallel: true` stage config in `testosterone.yaml` schema | P3 | S |
| 11.1.4 | Aggregate exit codes from parallel stages | P3 | M |
| 11.1.5 | Add integration tests for parallel execution | P3 | M |

### 11.2 Locust Framework Adapter

| # | Task | Priority | Effort |
|---|------|----------|--------|
| 11.2.1 | Create `testo_core/frameworks/locust_adapter.py` following `BaseAdapter` protocol | P3 | M |
| 11.2.2 | Handle Locust HTML report collection | P3 | S |
| 11.2.3 | Add Locust cycle example in `testosterone.yaml` | P3 | XS |
| 11.2.4 | Add unit tests for Locust adapter | P3 | S |

### 11.3 InfluxDB Metrics Pipeline

| # | Task | Priority | Effort |
|---|------|----------|--------|
| 11.3.1 | Complete InfluxDB metrics export from run results | P3 | M |
| 11.3.2 | Add Grafana dashboard template for Testo metrics | P3 | L |
| 11.3.3 | Document metrics pipeline in `docs/` | P3 | S |

### 11.4 Plugin Ecosystem

| # | Task | Priority | Effort |
|---|------|----------|--------|
| 11.4.1 | Document Pluggy hook specs and plugin API | P3 | M |
| 11.4.2 | Create example third-party plugin (e.g. Slack notifier) | P3 | M |
| 11.4.3 | Add `testo plugins list` CLI command | P3 | S |

### 11.5 Production Deployment

| # | Task | Priority | Effort |
|---|------|----------|--------|
| 11.5.1 | Create Helm chart for Kubernetes deployment | P3 | XL |
| 11.5.2 | Create Terraform module for cloud deployment | P3 | XL |
| 11.5.3 | Document production deployment guide | P3 | L |

---

## Execution Order Summary

The recommended execution order groups tasks into sprints:

### Sprint 1: Stabilize (P0 bugs + coverage)
**Tasks:** 1.1.1 → 1.1.2 → 1.1.3 → 1.2.1 → 1.2.2 → 1.3.1–1.3.6
**Goal:** All 16 draft PRs reviewed, critical bugs merged, test coverage landed.
**Estimated effort:** 1–2 days

### Sprint 2: Release Gates (P0 verification)
**Tasks:** 2.1.1–2.1.5 → 2.2.1–2.2.8 → 2.3.1–2.3.10 → 2.4.1–2.4.6
**Goal:** All 8 release checklists executed and checked off.
**Estimated effort:** 2–3 days

### Sprint 3: Persistence & Stack Consolidation (P0/P1 architecture)
**Tasks:** 3.1.1–3.1.10 (or 3.2.1–3.2.5) → 4.1–4.6
**Goal:** Persistence module resolved. Exit codes consolidated. Architecture documented.
**Estimated effort:** 2–3 days

### Sprint 4: Publish & Document (P0/P1 release infra)
**Tasks:** 6.1–6.9 → 7.1–7.6 → 8.1–8.6
**Goal:** CHANGELOG created. PyPI publish pipeline working. Docker image pipeline working.
**Estimated effort:** 2–3 days

### Sprint 5: Hardening & Cleanup (P2 quality)
**Tasks:** 5.1–5.10 → 9.1–9.7 → 1.2.3 → 1.4.1
**Goal:** Exception handling narrowed. Streamlit deprecated/removed. CI automation.
**Estimated effort:** 2–3 days

### Sprint 6: Ship v1.0 (P0 release)
**Tasks:** 10.1–10.8
**Goal:** Version bumped, tagged, published, verified.
**Estimated effort:** 1 day

### Post-v1.0
**Tasks:** 11.1–11.5 (all P3)
**Goal:** Parallel execution, Locust adapter, InfluxDB, plugin docs, production deployment.

**Total estimated effort to v1.0: ~10–15 working days**

---

## Task Statistics

| Priority | Count | Effort Range |
|----------|-------|--------------|
| P0 | 42 | Mostly XS–M |
| P1 | 28 | S–M |
| P2 | 22 | S–M |
| P3 | 18 | M–XL |
| **Total** | **110** | |

---

## Related Notes

- [[Product Roadmap]] — high-level phase delivery narrative
- [[Technical Debt Tracker]] — inferred debt backlog (items referenced above)
- [[Release Management/README]] — release gate hub
- [[Architecture Overview]] — system design
- [[Deep Dive - Execution Logic]] — engine internals
- [[UQO Engineering Hub]] — engineering coordination
