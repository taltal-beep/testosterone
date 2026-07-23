# Architecture Overview

Testo is a **config-driven test orchestration CLI** built around a small, sequential **engine** and **framework adapters**. Heavy dependencies (database, Docker runner for legacy UQO paths) are optional extras; the default `testo run` path executes frameworks as **host subprocesses**.

See also: [[Index]], [[Command Reference]], [[QA Strategies]].

## High-level shape

```text
testosterone.yaml
       │
       ▼
testo_core/config/     discover_and_load → resolve_plan / resolve_stages
       │
       ▼
testo_core/cli/runner   execute_plan_command (triggers, renderers, reporters)
       │
       ▼
testo_core/engine/
  orchestrator.run_plan  sequential stages
  executor.run_stage     subprocess per stage
       │
       ├──▶ testo_core/persistence/   JsonBackend + DbBackend (best-effort)
       │
       ▼
testo_core/frameworks/  pytest | behave | behavex adapters → argv + Allure dirs
       │
       ▼
artifacts/<cycle>/<stage>/   run.log, allure-results/, events.ndjson, plan_result.json
       │
       ▼
testo_core/reporting/   collect → Allure generate / Extent / ReportPortal / TestBeats
```

## Core modules

### `testo_core/cli/`

| Module | Role |
|--------|------|
| `app.py` | Typer entry (`testo`); lazy command registration |
| `runner.py` | Bridges CLI → config → engine → reporters → archive |
| `commands/*` | One module per subcommand (`run`, `report`, `config`, …) |
| `ui/` | Rich panels, CI NDJSON renderer, summary dashboards |

The CLI deliberately **defers imports** until a command runs so `testo --help` stays fast.

### `testo_core/config/`

- **`loader.py`** — discovers `testosterone.yaml` (or `--config` path) and parses YAML.
- **`schema.py`** — `TestosteroneConfig`, `Plan` (cycle), `Stage`, `ReporterSpec`, triggers.
- **`resolver.py`** — merges defaults, interpolates `${env:…}`, resolves stages per cycle.

Cycles are defined under `cycles:` in YAML (legacy key `plans:` is still accepted in some loaders).

### `testo_core/engine/`

| Module | Role |
|--------|------|
| `orchestrator.py` | `run_plan()` — iterates stages, emits events, writes `events.ndjson` |
| `executor.py` | `run_stage()` — spawns subprocess, timeouts, `run.log` tee |
| `exit_codes.py` | `EngineExitCode` taxonomy (0–4) — single source for both engine and headless stacks |
| `result.py` | `StageResult`, `PlanResult` aggregates |

`testo_core/persistence/` provides the `PersistenceBackend` protocol used by the orchestrator (JSON + DB backends, composite fanout). See **Persistence** below.

Execution is **sequential by design**; parallelization today is framework-internal (e.g. BehaveX `--workers`).

### `testo_core/frameworks/`

Each **equipment** name maps to an adapter implementing `FrameworkAdapter`:

- `pytest` → `PytestAdapter`
- `behave` → `BehaveAdapter`
- `behavex` → `BehaveXAdapter`

Adapters build `argv`, set Allure output under `allure-results/<framework>/`, and run in `stage.target_repo` as cwd.

### `testo_core/reporting/`

- **`collector.py`** — walks `artifacts/<cycle>/` for Allure result trees.
- **`entry.py`** — `testo report` dispatch (generate, serve, json/junit export).
- **`reporters/`** — plug-in reporters: `allure`, `extent`, `reportportal`, `testbeats`.

Post-run reporters are invoked from `cli/runner.py` after `run_plan()` when `reporters:` is set in YAML or `--reporter` is passed.

### `testo_core/triggers.py`

Optional per-cycle **selective execution**: Git diff or filesystem snapshot against glob patterns. Skipped cycles exit `0` without running stages (unless `--force`). Documented in [[QA Strategies#Selective triggers]].

### Adjacent packages (same repo)

| Package | Purpose |
|---------|---------|
| `testo_api/` | FastAPI `/api/v1` — cycle discovery (`GET /cycles`, `GET /cycles/{cycle}`), runs, SSE, report archives, health probes |
| `frontend/` | React UI (primary) — cycles-first navigation, see [[Phase 5 UI Redesign - Cycles-First Navigation]] |
| `testo_ui/` | Streamlit dashboard (legacy fallback) |
| `testo_core/runners.py` | Legacy **Docker** streaming runner used by UQO headless path |
| `testo_core/services/` | Headless engine, report archive diff, config DB helpers |

Modern **`testo run`** does not require Docker; the compose stack in `docker-compose.yml` supports the full UQO reporting platform (Postgres, MinIO, Allure Server) when those extras are enabled.

### Official documentation

| Technology | Reference |
|------------|-----------|
| Allure Report | https://docs.qameta.io/allure/ |
| ReportPortal | https://reportportal.io/docs/ |
| Docker Engine | https://docs.docker.com/engine/ |
| Docker Compose | https://docs.docker.com/compose/ |
| Compose file spec | https://docs.docker.com/compose/compose-file/ |

## Execution logic (happy path)

1. User runs [[Command Reference#testo run]] with `--cycle <name>`.
2. `discover_and_load()` loads `testosterone.yaml`.
3. `resolve_plan()` / `resolve_stages_for_plan()` build the effective stage list.
4. If the cycle has a `trigger:` block and not `--force`, `evaluate_cycle_trigger()` may skip the run.
5. Renderer is chosen: Rich buffered (`default`), live stream (`--stream`), or NDJSON (`--ci`).
6. `run_plan()` runs each stage via `run_stage()` (subprocess + timeout from `defaults.timeout_s` or per-stage override).
7. Events land in `artifacts/<cycle>/events.ndjson`; per-stage logs in `artifacts/<cycle>/<stage>/run.log`.
8. Configured **reporters** run (`run_configured_reporters`).
9. Optional **report archive** writes zip + metrics to SQL DB (`testo-core[db]`).

## Artifact layout

```text
artifacts/
  <cycle>/
    events.ndjson
    plan_result.json
    <stage>/
      run.log
      allure-results/
        pytest/ | behave/ | behavex/
          *-result.json
```

The collector and `testo report` both assume this layout. See `testo_core/reporting/collector.py`.

## Test pyramid

Each `Stage` carries a `tier: unit | integration | e2e` (`testo_core/config/schema.py`), explicit in `testosterone.yaml` or inferred from `equipment` (pytest→unit, behave→integration, behavex→e2e). `testo_core/reporting/pyramid_data.py::build_pyramid_model` sums each stage's `total_tests` (from the run's existing `stage_health`, computed by `testo_core/persistence/health.py::compute_stage_health`) into its tier bucket, producing a `PyramidModel(unit, integration, e2e)`.

`testo_core/reporting/pyramid_viz.py` classifies the shape (`HEALTHY`, `TOP_HEAVY`, `MID_BULGE`, `IRREGULAR`) and renders it as ASCII. Reached via `testo report pyramid RUN_ID` ([[Command Reference#testo report]]) and, from the API/UI side, `GET /api/v1/runs/{id}/pyramid` feeding a Run Detail visualization — see the "CLI-UI Parity" note under Specs & ADRs for why this existed as dead code before 2026-07-23.

## Exit code contract

Propagated unchanged for CI consumers (`EngineExitCode`):

| Code | Meaning |
|------|---------|
| `0` | Success (including trigger-skipped cycle) |
| `1` | Domain/test failure (non-zero stage return code) |
| `2` | Invalid config or CLI input |
| `3` | Infrastructure failure (timeout 124, missing exe 127, DB/Docker errors) |
| `4` | Internal/unexpected engine error |

Details and examples: [[Command Reference#Exit codes]].

## Configuration as the single source of truth

`testosterone.yaml` drives cycles, defaults (`artifacts_root`, `timeout_s`, `workers`), optional `database.url`, `reporters:`, and per-cycle `tags`, `trigger`, and `stages`. The interactive wizard is `testo init`; non-interactive scaffold is `testo config init`.

### Persistence

Two persistence layers exist, each at a different abstraction level:

**Engine-level** (`testo_core/persistence/`): Called by `orchestrator.run_plan()` after a cycle completes. Uses a `PersistenceBackend` protocol with two built-in backends:

- `JsonBackend` — writes `plan_result.json` to the artifacts tree (always active).
- `DbBackend` — upserts a `RunRecord` via the repository layer (active when DB extras are installed).

A `composite_backend()` factory fans out to both; individual backend failures never fail the run. Controlled by `--no-persist`.

**Service-level** (`testo_core/repository/`): Dialect-agnostic adapters selected by `DATABASE_URL` / `database.url` (SQLite default, PostgreSQL/MySQL for teams with existing infra). Used by the headless engine, API layer, and report archive system. Rationale: [[Repository Pattern - Database-Agnostic Refactor]]. Factory: `testo_core/db.py` → `get_repository()`.

**Two separate, unlinked id spaces** — easy to conflate, worth calling out explicitly (found while building per-test diff for the API, see [[CLI-UI Parity - Pyramid, Graphs, Deep Diff - 2026-07-23]]):

- **Run-history runs** (`RunRecord` / `CompletedRunView`, `run_history.py`): one row per `testo run --cycle` execution, keyed by `run_id`. This is what the dashboard, history, run detail, and delta/compare pages all use (`/api/v1/runs/{run_id}`, `/api/v1/analytics/delta`). Carries `stage_health`, `snapshot_dir` (the run's own raw artifact tree, local or S3).
- **Report archives** (`ReportArchive`, `testo_core/repository/report_archive_repository.py`): one row per `testo report list/open/diff` archive, a zipped Allure snapshot keyed by its own UUID (`report_id`), with **no `run_id` column linking it back** to the run that produced it. Populated separately via `_maybe_archive_cycle_report()` in `testo_core/cli/runner.py`.

Code that needs per-test data for a *run_id* (not a *report_id*) should extract from `CompletedRunView.snapshot_dir` (via `snapshot_files_for_download()`), not attempt to resolve a `ReportArchive` row — there isn't one to resolve to. See `testo_core/services/run_snapshot_diff.py` for the pattern.

## Related operational docs

- Release gates: [[Release Management/README]]
- CI & ghost mode: [[CI-CD Pipeline Setup]], [[QA Strategies#CI and streaming output]]
- Migration & local setup: [[Streamlit to React Migration Guide]], [[ReportPortal Local Setup Guide]]
- Phased strategy: [[Product Roadmap]]
