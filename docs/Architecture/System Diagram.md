---
type: architecture
status: current
created: 2026-10-08
updated: 2026-10-08
---

# System Diagram

The one-picture view of Testosterone, with what each box does. For module-level detail see [Architecture Overview](Architecture%20Overview.md); for the run lifecycle step by step see [Deep Dive - Execution Logic](Deep%20Dive%20-%20Execution%20Logic.md).

![Architecture: React dashboard, CI and terminal drive the REST API and testo CLI, which call testo_core (config, engine, framework adapters, reporting, insight services, persistence)](../assets/testosterone-architecture-light.png)

A dark-background copy is at [testosterone-architecture-dark.png](../assets/testosterone-architecture-dark.png); the README picks between the two by colour scheme.

## All diagrams in the vault

| Diagram | Shows | Where |
|---------|-------|-------|
| System diagram (image above) | Who uses it, interfaces, `testo_core` parts, outside systems | This note |
| Component flowchart (Mermaid) | Entry points, `CycleRunService`, engine, persistence, history read side | [Architecture Overview § High-level shape](Architecture%20Overview.md#high-level-shape) |
| Run sequence (Mermaid) | One `testo run` call from CLI to executor and back | [Deep Dive - Execution Logic](Deep%20Dive%20-%20Execution%20Logic.md) |
| Cycle flow (Mermaid) | Load, trigger gate, stages, reporters, archive | [QA Strategies](../Testing%20Workflows/QA%20Strategies.md) |
| Demo pipeline (text) | Pages demo: run on itself and fake-api, export to JSON, build, publish | [GitLab Pages Demo](../Processes%20&%20Guides/GitLab%20Pages%20Demo.md) |

Mermaid blocks render on GitHub, in the GitHub wiki and in Obsidian without plugins.

## What each part does

### Who uses it

| Part | Role |
|------|------|
| React dashboard | Starts cycles, watches them live, browses past runs, compares two runs |
| CI pipeline | Runs `testo run --ci`: NDJSON events on stdout, pass or fail through the exit code |
| Developer terminal | Runs cycles locally with Rich output, opens reports, diffs runs |

### Interfaces

| Part | Role |
|------|------|
| REST API | FastAPI under `/api/v1` (`testo_api/`). Starts cycle and ad-hoc executions in the background, streams progress over SSE, serves dashboard, history, compare and AI summary data |
| testo CLI | Typer app (`testo_core/cli/`). Commands load lazily so `testo --help` stays fast. Exit codes `0`–`4` are a fixed contract ([Command Reference § Exit codes](../CLI%20Commands/Command%20Reference.md#exit-codes)) |

Both interfaces start runs the same way: through `CycleRunService` (`testo_core/services/cycle_run.py`), which applies the trigger gate, calls the engine, then runs reporters, metrics push and the report archive. The picture folds it into the arrow into `testo_core`; the [component flowchart](Architecture%20Overview.md#high-level-shape) shows it as its own box.

### Core library (`testo_core`)

| Part | Package | Role |
|------|---------|------|
| Config | `config/` | Finds and validates `testosterone.yaml`, fills defaults and `${env:…}`, resolves a cycle into ordered stages |
| Engine | `engine/` | `run_plan()` runs stages in order; `run_stage()` runs each as a subprocess with a timeout and a tee'd log; every step is a typed event |
| Framework adapters | `frameworks/` | Turn a stage into argv for pytest, behave, behavex or `command` (any runner with JUnit XML) |
| Reporting | `reporting/` | Collects Allure results and builds Allure, Extent, ReportPortal or TestBeats output; run KPIs and their push |
| Insight services | `services/` over `history/` | Dashboard KPIs, run-to-run delta, AI failure summaries. Read run history only through `testo_core/history/` |
| Persistence | `persistence/` + `repository/` | `plan_result.json` on disk and a `RunRecord` row through the repository (SQLite, Postgres or MySQL) |

### Outside world

| Part | Role |
|------|------|
| Target repo | The project whose tests run; each stage runs inside it |
| `artifacts/` | Per cycle and stage: `run.log`, Allure results, `events.ndjson`, `plan_result.json` |
| SQL database | Run history that feeds the dashboard and Compare |
| Report outputs | HTML reports under `static/history/<run_id>/`, or results pushed to ReportPortal / TestBeats |
| LLM provider | OpenAI or Anthropic with the user's own key, only when AI summaries are on |

## Design choices the picture encodes

- **Config is the contract.** The developer, CI and the dashboard run the same cycle from the same file.
- **Events, not callbacks.** The engine only emits events; renderers (Rich, NDJSON, SSE) decide presentation.
- **Small interfaces at the seams.** Framework adapters, persistence backends, the repository, reporters and AI providers are swappable.
- **One result format.** Every framework's output becomes Allure results, so every report and comparison works for every framework.
- **Light by default.** Database, API and UI dependencies are optional extras.

The reasoning behind the current shape (one engine, one history boundary, generated frontend types) is in [Architecture Consolidation - 2026-10-06](../Specs%20&%20ADRs/Architecture%20Consolidation%20-%202026-10-06.md).
