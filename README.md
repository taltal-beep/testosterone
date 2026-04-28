# Unified Quality Orchestration (UQO) — Reporting Dashboard

UQO is a **production-oriented test orchestration system** that runs plugin-driven quality checks inside **ephemeral Docker containers**, persists run state to **Postgres**, stores artifacts in **MinIO (S3)**, and renders per-run **Allure Server** reports.

This repo ships a Streamlit UI (`app.py`) for running tests, watching live logs, and browsing run history.

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
git clone https://github.com/YOUR_ORG/unified-quality-orchestration-reporting-dashboard.git
cd unified-quality-orchestration-reporting-dashboard
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

### 5) Execute your first test

Option A (recommended): use **Sandbox mode** in the UI.
- Open Streamlit → `Execution` tab → enable **Load sandbox mode** → click **Run**

Option B: point at your own repo (must be accessible on the same machine running Docker Desktop).
- Open Streamlit → set **Target repository path** → choose **Test type** → click **Run**

### 6) View the Allure report for a completed run

Go to `History` → expand the run → click **Open Allure Server report**.

---

## Architecture (full stack)

### Runtime services (Docker Compose)

- **Streamlit (host process)**: UI and orchestration entrypoint (`app.py`)
- **Postgres** (`uqo-postgres`): canonical run lifecycle storage (`engine/run_history.py`)
- **MinIO** (`uqo-minio`): S3-compatible artifact store
  - Bucket: `BUCKET_NAME` (default `uqo-artifacts`)
  - Raw Allure results: `projects/<run_id>/results/*`
  - HTML snapshots (optional): `runs/<run_id>/artifacts/*`
- **Allure Docker Service** (`uqo-allure`): generates per-run reports by project id
  - Report URL: `ALLURE_SERVER_URL/allure-docker-service/projects/<run_id>/reports/latest/index.html`
- **Allure sync** (`uqo-allure-sync`): mirrors MinIO `projects/` into Allure’s `/app/projects/`
- **Mock API (sandbox)**: local target used for demos (managed by Streamlit via `engine/sandbox_api.py`)

### Execution flow (happy path)

1. UI creates a DB run row in Postgres: `status=RUNNING`
2. Runner starts an ephemeral container via Docker SDK (`engine/runners.py`)
3. Plugin/test framework emits Allure result files
4. On completion:
   - DB row is updated to `COMPLETED` or `FAILED`
   - raw Allure results are uploaded to MinIO under `projects/<run_id>/results/`
5. `uqo-allure-sync` mirrors MinIO → Allure volume; Allure Docker Service updates the report
6. UI shows an **Allure Server** button for the completed run

### Resilience guarantees

- **Crash recovery**: on startup, any DB runs in `RUNNING` are marked `FAILED` with `error_message="Orphaned due to system crash"`.
- **Zombie containers**: containers are killed after `UQO_CONTAINER_TIMEOUT_S` seconds.

---

## Writing a custom test plugin (step-by-step)

UQO supports **drop-in runner plugins** via **Pluggy**. Plugins are Python modules placed under `plugins/` and loaded by `engine/orchestrator.py`.

The plugin interface is defined in `engine/specs.py` (`BaseRunnerSpec`), with these hooks:
- `get_command(config) -> list[str] | None` (first plugin to return an argv wins)
- `setup_env(config) -> dict[str, str] | None`
- `collect_artifacts(run_id) -> list[pathlib.Path] | None`

### 1) Create a plugin module

Create `plugins/my_custom_runner.py`:

```python
from __future__ import annotations

from pathlib import Path

from engine.run_config import RunConfig
from engine.specs import hookimpl


@hookimpl(firstresult=True)
def get_command(config: RunConfig) -> list[str] | None:
    # Example: handle a custom "tool" selector from RunConfig (shape depends on your RunConfig usage).
    if getattr(config, "tool", None) != "my-tool":
        return None
    return ["python", "-m", "my_tool.cli", "--flag", "value"]


@hookimpl
def setup_env(config: RunConfig) -> dict[str, str] | None:
    if getattr(config, "tool", None) != "my-tool":
        return None
    return {"MY_TOOL_MODE": "1"}


@hookimpl
def collect_artifacts(run_id: str) -> list[Path] | None:
    # Return host paths that should be uploaded (optional).
    p = Path("artifacts") / "my-tool"
    return [p] if p.exists() else None
```

### 2) Run it (developer workflow)

At runtime, `engine/orchestrator.create_plugin_manager(load_dropins=True)` scans `plugins/*.py` and registers each module.

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

## CI/CD (recommended)

- **Lint + unit tests**: run Python linters/tests on PRs.
- **Docker smoke**: `docker compose up -d` + run a sandbox test + verify:
  - orphan cleanup works (force-kill Streamlit mid-run; restart; run is `FAILED`)
  - timeout works (plugin that sleeps forever; container killed; run is `FAILED`)
  - Allure link works (`/projects/<run_id>/reports/latest/index.html` returns 200)

