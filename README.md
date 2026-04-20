# Unified Quality Orchestration & Reporting Dashboard (UQO)

UQO is a **Streamlit-based orchestrator** that runs **Pytest**, **BehaveX**, and **Locust** against a target repository, aggregates **Allure** results, mirrors native HTML reports, and can **push metrics** to **InfluxDB** and **Prometheus** for Grafana-style dashboards.

## Features

- **Single UI** to configure runs, watch live logs, and open Allure / BehaveX / Locust reports.
- **Full System Audit** — sequential Pytest → BehaveX → Locust into one Allure results folder with a master HTML report.
- **Run history** — SQLite metadata and downloadable HTML snapshots under `artifacts/history/`.
- **Enterprise integrations** — optional InfluxDB and Prometheus Pushgateway sync (with connection tests and auto-push after runs).

## Quick start

### Prerequisites

- **Python 3.11+** recommended.
- **Allure CLI** for HTML generation (`brew install allure` on macOS, or your OS package manager).
- Target repo with tests (or use the bundled **sandbox** sample).

### Install

```bash
git clone https://github.com/YOUR_ORG/unified-quality-orchestration-reporting-dashboard.git
cd unified-quality-orchestration-reporting-dashboard
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env        # optional: add InfluxDB / Pushgateway URLs and tokens
streamlit run app.py
```

Open the URL shown in the terminal (default `http://localhost:8501`).

## Architecture

| Layer | Role |
|--------|------|
| **Streamlit (`app.py`)** | UI, session state, worker threads, integrations tab. |
| **Runners (`engine/runners.py`)** | Subprocess orchestration, PATH resolution, audit multi-phase runs. |
| **Command builders** | Builds argv for pytest / behavex / locust and Allure dirs. |
| **Report generator** | Allure HTML, static mirrors, BehaveX tree copy, Locust HTML path. |
| **Metrics** | Parses Allure `*-result.json` for KPIs. |
| **Metrics extractor** | Reads `allure-report/widgets/summary.json` when present, else falls back to raw results. |
| **Integrations** | InfluxDB line protocol via `influxdb-client`; Prometheus text exposition to Pushgateway. |
| **Run history** | SQLite DB + per-run snapshot folder under `artifacts/`. |

Test stacks:

- **Pytest** — Allure results via `--alluredir` and drop-in hooks.
- **BehaveX** — parallel BDD with native HTML under `artifacts/behave_reports/`, mirrored to `static/behave/`.
- **Locust** — headless run with HTML under `artifacts/locust_report.html`, mirrored to `static/`.

## Integrations (Grafana / Influx / Prometheus)

1. Copy **`.env.example`** to **`.env`** and set at least:
   - `INFLUXDB_URL`, `INFLUXDB_ORG`, `INFLUXDB_BUCKET`, `INFLUXDB_TOKEN`
   - optionally `PROMETHEUS_PUSHGATEWAY_URL`, `PROMETHEUS_JOB_NAME`
2. In the app **Integrations** tab, use **Test connection** for InfluxDB and Pushgateway.
3. Enable **auto-push** toggles to send metrics after each completed run (failures are logged to the console output and do not stop the run).

Metrics are derived from the **latest Allure report** (`widgets/summary.json`) when available, otherwise from **`artifacts/allure-results`** JSON files.

## Project layout (high level)

```
app.py                 # Streamlit entrypoint
engine/                # Orchestration, metrics, integrations, history
drop_in_hooks/         # Pytest / BehaveX / Locust hooks
sample_target_repo/    # Example API + tests for sandbox mode
artifacts/             # Allure results, reports, DB (gitignored where appropriate)
static/                # Mirrored HTML for Streamlit static serving (gitignored)
```

## License

MIT — see [LICENSE](LICENSE).

## Contributing

Issues and pull requests are welcome. Please keep changes focused and match existing code style.
