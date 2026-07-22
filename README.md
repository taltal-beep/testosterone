# Unified Quality Orchestration (UQO) — Reporting Dashboard

UQO is a **production-oriented test orchestration system** that runs plugin-driven quality checks inside **ephemeral Docker containers**, persists run state to **Postgres**, stores artifacts in **MinIO (S3)**, and renders per-run **Allure Server** reports.

This repo ships both:
- a Streamlit UI (`app.py`) for interactive execution/history
- a headless CLI (`uqo`) for CI-friendly automation
- a FastAPI backend adapter (`testo_api`) with typed `/api/v1` JSON endpoints
- a React frontend (`frontend/`) for dashboard parity migration

## What you get

- **One UI**: start runs, stream logs, browse history.
- **Resilient lifecycle**:
  - Orchestrator crash → any stuck `RUNNING` run is auto-marked `FAILED` on startup.
  - Runaway plugin (infinite loop) → container is hard-killed on timeout.
- **Production-grade reporting**:
  - Raw results uploaded to MinIO under `projects/<run_id>/results/`
  - Allure Docker Service reads those results and generates `projects/<run_id>/reports/latest`
- **Pluggable execution**: drop in new test plugins without changing the core engine.

---

## Quickstart (copy/paste)

### 1) Clone

```bash
git clone https://github.com/taltal-beep/testosterone.git
cd testosterone
```

### 2) Configure env

Create a `.env` file (example below). MinIO credentials are required because artifacts and Allure results are stored in MinIO.

```bash
cat > .env <<'EOF'
MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=minioadmin

# Optional overrides (defaults shown)
BUCKET_NAME=uqo-artifacts
POSTGRES_USER=uqo_admin
POSTGRES_PASSWORD=admin
POSTGRES_DB=uqo_history

# Safety: hard-stop runaway test containers (seconds)
UQO_CONTAINER_TIMEOUT_S=600

# Used by the UI for the per-run Allure Server link
ALLURE_SERVER_URL=http://localhost:5050
EOF
```

### 3) Start infrastructure (Postgres + MinIO + Allure)

```bash
docker compose up -d
docker compose ps
```

Useful endpoints:
- **Streamlit UI**: `http://localhost:8501` (started below)
- **MinIO Console**: `http://localhost:9001`
- **Allure Server**: `http://localhost:5050`

### 4) Start the UI

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Phase 3 transitional UI mode (default `dual`):

```bash
export UQO_UI_MODE=dual  # streamlit | react | dual
```

---

## CLI cycles (`testo`)

The `testo` CLI reads `testosterone.yaml` and runs a named **cycle** (top-level key under `cycles:`). Each cycle contains one or more stages, and each stage declares an `equipment` (e.g. `pytest`, `behave`, `behavex`).

- **BehaveX dependency**: `behavex` is already included as a runtime dependency in `pyproject.toml`. You can verify the executable is available with:
  - `testo config validate --check-executables`

Start the new backend + frontend in parallel:

```bash
uvicorn testo_api.main:app --host 0.0.0.0 --port 8000 --reload
npm --prefix frontend install
npm --prefix frontend run dev
```

### 5) Execute your first test

Option A (recommended): use **Sandbox mode** in the UI.
- Open Streamlit → `Execution` tab → enable **Load sandbox mode** → click **Run**

Option B: point at your own repo (must be accessible on the same machine running Docker Desktop).
- Open Streamlit → set **Target repository path** → choose **Test type** → click **Run**

Option C: run headless from CLI (CI-safe JSON output).
```bash
uqo run --config load-test.yaml --ci
```

### 6) View the Allure report for a completed run

Go to `History` → expand the run → click **Open Allure Server report**.

---

## Architecture (full stack)

### Runtime services (Docker Compose)

- **Streamlit (host process)**: interactive adapter over the shared headless engine (`app.py`)
- **FastAPI (`testo_api/main.py`)**: JSON + SSE adapter over the same headless engine
- **React frontend (`frontend/`)**: dashboard client consuming `/api/v1` contracts
- **UQO CLI (`uqo`)**: non-interactive adapter over the same shared headless engine (`testo_core/cli.py`)
- **Postgres** (`uqo-postgres`): canonical run lifecycle storage (`testo_core/run_history.py`)
- **MinIO** (`uqo-minio`): S3-compatible artifact store
  - Bucket: `BUCKET_NAME` (default `uqo-artifacts`)
  - Raw Allure results: `projects/<run_id>/results/*`
  - HTML snapshots (optional): `runs/<run_id>/artifacts/*`
- **Allure Docker Service** (`uqo-allure`): generates per-run reports by project id
  - Report URL: `ALLURE_SERVER_URL/allure-docker-service/projects/<run_id>/reports/latest/index.html`
- **Allure sync** (`uqo-allure-sync`): mirrors MinIO `projects/` into Allure’s `/app/projects/`
- **Mock API (sandbox)**: local target used for demos (managed by Streamlit via `testo_core/sandbox_api.py`)

### Execution flow (happy path)

1. UI or CLI calls the shared engine service (`testo_core/services/headless_engine.py`)
1.1 React calls FastAPI `/api/v1`; FastAPI calls the same `HeadlessEngineService`
2. Engine creates DB run row(s) in Postgres: `status=RUNNING`
3. Runner starts an ephemeral container via Docker SDK (`testo_core/runners.py`)
3. Plugin/test framework emits Allure result files
4. On completion:
   - DB row is updated to `COMPLETED` or `FAILED`
   - raw Allure results are uploaded to MinIO under `projects/<run_id>/results/`
5. `uqo-allure-sync` mirrors MinIO → Allure volume; Allure Docker Service updates the report
6. UI shows an **Allure Server** button for the completed run

## Headless CLI contract

`uqo run` uses YAML config and returns machine-readable output for automation:

```bash
uqo run --config load-test.yaml --stream-json
uqo run --config load-test.yaml --ghost --stream-json
uqo run --config load-test.yaml --no-ghost
```

- `--ci`: legacy-compatible alias for ghost behavior (forces non-interactive mode)
- `--ghost`: force ghost mode on
- `--no-ghost`: force ghost mode off (even in CI)
- `--json`: print final summary JSON object
- `--stream-json`: print NDJSON event lines and then final summary JSON (always)
- `--no-persist`: execute without DB/history persistence

Ghost mode auto-detection and precedence:

- `--no-ghost` wins over every other signal
- `--ghost` forces on
- `--ci` forces on (backward compatibility)
- otherwise CI environment auto-detection enables ghost mode (`github`, `gitlab`, `buildkite`, `circleci`, `jenkins`, `azure_pipelines`, or generic `CI=true`)

Stable process exit codes:
- `0`: successful run
- `1`: run executed but test/audit failed
- `2`: invalid config/arguments
- `3`: infrastructure/runtime dependency failure
- `4`: unexpected internal error

Final summary JSON schema (`schema_version=1`) is stable for `uqo run`:
- `schema_version`, `trigger_source`, `ci_mode`, `persist`
- `exit_code`, `aggregate_returncode`
- `started_at`, `finished_at`, `duration_s`
- `runs` (list of run records), `error` (nullable)
- `execution_mode` (`headless` or `ghost`)
- `failure_type` (`test_failure`, `sync_failure`, `infra_failure`, or `null`)
- `sync` (DB/artifact sync status with per-run attempt/error details)

NDJSON event schema (`--stream-json`):
- `{"event":"log","stream":"stdout|stderr|meta","line":"...","ts":<float>}`
- `{"event":"run_result","returncode":<int>,"started_at":<float>,"finished_at":<float>,"run_id":"...","test_type":"...","cwd":"..."}`

Contract scope note:
- machine JSON contract applies to the `uqo run ...` execution path.
- parser/help failures before command execution may emit argparse usage text to stderr.

Minimal single-run YAML example:

```yaml
test_type: pytest
target_repo: ./sample_target_repo
cli_args: "-q"
timeout_s: 600
```

Multi-run YAML example:

```yaml
runs:
  - test_type: pytest
    target_repo: ./sample_target_repo
    cli_args: "-q"
  - test_type: locust
    target_repo: ./sample_target_repo
    locust_users: 20
    locust_spawn_rate: 5
    locust_run_time: "2m"
```

## Migration notes

- Added a shared headless application engine in `testo_core/services/headless_engine.py`.
- Added package CLI entrypoint `uqo` in `pyproject.toml`.
- Streamlit main run path now delegates orchestration to the same core engine used by CLI.
- Removed legacy unused UI worker helpers that directly orchestrated `run_streaming` / `AuditService` paths.
- Existing `RunConfig`, repository interfaces, and persistence/update flow remain in `testo_core`.
- Backward compatibility is preserved; metadata now includes `trigger_source`, `ci_mode`, and `schema_version`.
- Optional MySQL runtime driver is available via `pip install -e '.[db_mysql]'`.

### Resilience guarantees

- **Crash recovery**: on startup, any DB runs in `RUNNING` are marked `FAILED` with `error_message="Orphaned due to system crash"`.
- **Zombie containers**: containers are killed after `UQO_CONTAINER_TIMEOUT_S` seconds.

---

## Writing a custom test plugin (step-by-step)

UQO supports **drop-in runner plugins** via **Pluggy**. Plugins are Python modules placed under `plugins/` and loaded by `testo_core/orchestrator.py`.

The plugin interface is defined in `testo_core/specs.py` (`BaseRunnerSpec`), with these hooks:
- `get_command(config) -> list[str] | None` (first plugin to return an argv wins)
- `setup_env(config) -> dict[str, str] | None`
- `collect_artifacts(run_id) -> list[pathlib.Path] | None`

The built-in Streamlit workflow uses `testo_core.command_builders.TestType` for `pytest`, `behavex`, `behave_native`, and `locust`. A custom plugin can participate in a runner path that calls `create_plugin_manager(load_dropins=True)`, but adding a file under `plugins/` does not automatically add a new option to the UI.

### 1) Create a plugin module

Create `plugins/my_custom_runner.py` at the repository root:

```python
from __future__ import annotations

from pathlib import Path
from typing import Mapping

from testo_core.command_builders import RunConfig, TestType
from testo_core.specs import hookimpl


@hookimpl
def get_command(config: RunConfig) -> list[str] | None:
    # Example: override Locust command construction for a specialized runner.
    if config.test_type != TestType.LOCUST:
        return None
    return ["python", "-m", "my_tool.cli", "--results", str(config.shared_allure_results_dir)]


@hookimpl
def setup_env(config: RunConfig) -> Mapping[str, str] | None:
    if config.test_type != TestType.LOCUST:
        return None
    return {"MY_TOOL_MODE": "1"}


@hookimpl
def collect_artifacts(run_id: str) -> list[Path] | None:
    # Return host paths that should be uploaded (optional).
    p = Path("artifacts") / "my-tool"
    return [p] if p.exists() else None
```

### 2) Run it (developer workflow)

At runtime, `testo_core/orchestrator.create_plugin_manager(load_dropins=True)` scans `plugins/*.py` and registers each module.

If you’re extending the system to execute custom plugins from the UI, the typical wiring is:
- build a `RunConfig` that expresses what tool/framework should run
- ask Pluggy for `get_command(config)` to obtain the argv
- merge env from `setup_env(config)`
- execute inside the Docker runner and upload artifacts from `collect_artifacts(run_id)`

### 3) Production tips

- **Timeouts**: rely on `UQO_CONTAINER_TIMEOUT_S` as a hard safety net for runaway tools.
- **Allure**: write results into `UQO_SHARED_ALLURE_RESULTS_DIR` so UQO can upload them to MinIO and Allure Server can render the report.
- **Artifacts**: keep output under `artifacts/` so it’s easy to snapshot/upload.

---

## Operations and troubleshooting

### Required local infrastructure

Run `docker compose up -d` before starting Streamlit. The runner creates one-off `python:3.11-slim` containers on Docker network `uqo-net`; if Compose is down, execution cannot attach to the expected network.

Use these checks when reports or history links are missing:

```bash
docker compose ps
docker compose logs --tail=100 allure-sync
docker compose logs --tail=100 minio-init
```

### Allure report link returns 404

Allure Docker Service reads from a mirrored volume, not directly from MinIO. After a run completes:

1. Confirm raw results exist in MinIO under `projects/<run_id>/results/`.
2. Wait for the `uqo-allure-sync` mirror loop (`CHECK_RESULTS_EVERY_SECONDS` and the sync loop both use 5-second defaults).
3. Verify `ALLURE_SERVER_URL` points at the browser-visible Allure service, for example `http://localhost:5050`.
4. Open `ALLURE_SERVER_URL/allure-docker-service/projects/<run_id>/reports/latest/index.html`.

### MinIO snapshots or download links are missing

The S3 client requires `MINIO_ROOT_USER` and `MINIO_ROOT_PASSWORD`. It defaults to bucket `uqo-artifacts`, endpoint `http://localhost:9000` on the host, and `http://uqo-minio:9000` in Docker. Set `MINIO_PUBLIC_BASE_URL` when browser download URLs need a different public host.

`minio-init` creates the bucket and applies anonymous download policy. If history downloads fail, check that this container completed successfully.

### Optional metrics integrations

The Integrations tab can push metrics after a run or on demand:

- InfluxDB: set `INFLUXDB_URL`, `INFLUXDB_TOKEN`, `INFLUXDB_ORG`, and `INFLUXDB_BUCKET`.
- Prometheus Pushgateway: set `PROMETHEUS_PUSHGATEWAY_URL`; optionally set `PROMETHEUS_JOB_NAME` (defaults to `uqo`).

Metrics pushes are best-effort. They do not change the run result.

---

## CI/CD (recommended)

- **Lint + unit tests**: `.github/workflows/ci.yml`'s `format` job runs on every PR — `ruff check .` (blocking), `ruff format --check` (advisory), `mypy testo_core` (advisory, see `docs/Testing Workflows/Technical Debt Tracker.md`) — followed by the `test` job's fast pytest tier. Run locally before pushing:
  ```bash
  pip install -e ".[dev]"
  ruff check .
  mypy testo_core
  ```
- **Pre-commit hooks**: catches the same `ruff`/changelog-format checks locally before you push, plus basic whitespace/YAML/TOML hygiene. One-time setup:
  ```bash
  pip install -e ".[dev]"
  pre-commit install
  ```
- **Docker smoke**: `docker compose up -d` + run a sandbox test + verify:
  - orphan cleanup works (force-kill Streamlit mid-run; restart; run is `FAILED`)
  - timeout works (plugin that sleeps forever; container killed; run is `FAILED`)
  - Allure link works (`/projects/<run_id>/reports/latest/index.html` returns 200)
- Use [`docs/release_checklist_phase1.md`](docs/release_checklist_phase1.md) as the mandatory Foundation go/no-go gate.

### GitHub Action quickstart

Use one line in your workflow job steps:

```yaml
- uses: ariel-evn/uqo-action@v1
  with:
    config-path: ./.uqo/config.yaml
```

Supported inputs:

- `config-path` (required)
- `ci-mode` (`true` by default)
- `ghost-mode` (`auto` by default; `true` forces `--ghost`, `false` forces `--no-ghost`)
- `stream-json` (`false` by default)
- `persist` (`true` by default)
- `runner-image` (empty by default; sets `UQO_RUNNER_IMAGE` for the execution engine)
- `runner-prebuilt` (`auto` by default; `true` skips runtime dependency install inside the runner container, `false` forces legacy install path)
- `python-version` (`3.11` by default)

Action outputs:

- `exit_code`
- `run_id`
- `summary_json`
- `summary_path`
- `status`

### GitLab template quickstart

Include the shared template and set the config path:

```yaml
include:
  - project: "ariel-evn/unified-quality-orchestration-reporting-dashboard"
    file: "/ci/gitlab/testo.gitlab-ci.yml"

variables:
  UQO_CONFIG_PATH: ".uqo/config.yaml"
  UQO_RUNNER_IMAGE: "docker.io/ariel-evn/uqo-runner:v1"
  UQO_RUNNER_PREBUILT: "true"
```

Both wrappers call the same contract:

```bash
uqo run --config <path> --ci [--ghost|--no-ghost]
```

GitLab template variables:

- `UQO_CONFIG_PATH` (required; path to config YAML)
- `UQO_GHOST_MODE` (`auto` by default)
- `UQO_STREAM_JSON` (`false` by default)
- `UQO_PERSIST` (`true` by default)
- `UQO_RUNNER_IMAGE` (empty by default; set to prebuilt image reference)
- `UQO_RUNNER_PREBUILT` (`auto` by default; `true|false|auto`)

### Required secrets and variables

Set these in your CI provider when persistence/artifact upload is enabled:

- Database: `DATABASE_URL` (or `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, optional `POSTGRES_HOST`, `POSTGRES_PORT`)
- MinIO/S3: `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD`, optional `BUCKET_NAME`, `MINIO_ENDPOINT`, `MINIO_PUBLIC_BASE_URL`
- Optional reporting URL: `ALLURE_SERVER_URL`

### CI troubleshooting

- `exit_code=2`: invalid config path or schema; verify `--config` points to a valid YAML file.
- `exit_code=3`: infrastructure dependency issue (Docker/DB/network/credentials); check DB and storage env vars.
- Runner image pull errors: verify image reference, registry auth, and network egress; this is reported as infrastructure failure (`exit_code=3`).
- Missing `run_id` output: run did not produce a terminal summary run entry; inspect `summary_json` and `uqo-output.ndjson`.
- Upload/report link failures: verify MinIO credentials and bucket permissions for CI runner identity.

Release gate for wrappers is documented in [`docs/release_checklist_phase2_ci.md`](docs/release_checklist_phase2_ci.md).

Ghost-mode release gate is documented in [`docs/release_checklist_phase2_ghost_mode.md`](docs/release_checklist_phase2_ghost_mode.md).

Runner image release gate is documented in [`docs/release_checklist_phase2_runner_image.md`](docs/release_checklist_phase2_runner_image.md).

---

## Phase 3 API contracts (`/api/v1`)

- `POST /api/v1/executions`: create run execution job from one or more run specs
- `GET /api/v1/executions/{execution_id}`: poll execution status and final summary
- `GET /api/v1/executions/{execution_id}/events`: SSE stream for `log`, `run_result`, and `summary` events
- `GET /api/v1/runs`: list persisted run sessions
- `GET /api/v1/runs/{run_id}`: run details
- `GET /api/v1/runs/{run_id}/reports`: report links + artifact metadata
- `GET /api/v1/dashboard/overview`: unified dashboard payload (headline KPIs, trend indicators, reliability/performance rollups, report links, freshness)
- `GET /api/v1/dashboard/runs/recent`: compact recent run list for dashboard refresh paths
- `GET /api/v1/analytics/delta?current_run_id=<id>&baseline_run_id=<id>`: core-owned run delta comparison
- `GET /api/v1/health/live`, `GET /api/v1/health/ready`: liveness/readiness probes

The backend and frontend are migration adapters only; orchestration remains centralized in `testo_core`.

## Phase 4 AI/BYOK contracts

- `GET /api/v1/ai/config/status`: returns non-secret AI configuration status.
- `PUT /api/v1/ai/config`: updates provider/model/timeouts and optional runtime key input.
- `GET /api/v1/runs/{run_id}/ai-summary`: returns stored summary or typed no-summary payload.
- `POST /api/v1/runs/{run_id}/ai-summary:generate`: generates or refreshes a failed-run summary.

Security and behavior guarantees:

- AI integration is explicit opt-in (`enabled=false` by default).
- Raw API keys are never returned by backend responses.
- Runtime key input is memory-only by default (not persisted to DB/files).
- Token-like values are redacted from internal error surfaces before transport.
- Existing run execution and CLI/CI contracts are unchanged when AI is unavailable.

Release gate: `docs/release_checklist_phase4_ai.md`.

### Unified dashboard interpretation rules

- Primary React entrypoint is `/` and renders a single overview page fed by `GET /api/v1/dashboard/overview`.
- KPI/trend computations stay in backend/core (`testo_core/services/dashboard_service.py`); React renders provided values and states.
- Trend semantics:
  - `health`: higher is better
  - `failed_count`: lower is better
  - `duration`: lower is better
- Unknown/degraded behavior:
  - missing values stay nullable (`null`) and are rendered as `n/a`
  - trend direction can be `unknown` when baseline/current is unavailable
  - `data_freshness.degraded=true` indicates partial aggregation and includes reason notes
- Report link states:
  - `available`: render as clickable link
  - `missing`: render as unavailable
  - `unknown`: render as unknown state (no hard failure)

### Delta comparison semantics

- Baseline/current roles and sign rules are deterministic and documented in [`docs/delta_comparison_policy.md`](docs/delta_comparison_policy.md).
- Core analytics logic lives in `testo_core/services/delta_service.py`; route and React layers map and render only.
- Classification labels: `regression`, `improvement`, `neutral`, `unknown`.

Unified dashboard release gate is documented in [`docs/release_checklist_phase3_unified_dashboard.md`](docs/release_checklist_phase3_unified_dashboard.md).
