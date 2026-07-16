# Testo — Second Brain Index

**Testo** (package name: `testo-core`) is the unified quality orchestration CLI for **Testosterone**. It reads `testosterone.yaml`, runs multi-stage test **cycles** (pytest, Behave, BehaveX, and more), collects artifacts under `artifacts/`, optionally archives runs to a database, and generates unified reports (Allure, Extent, ReportPortal, TestBeats).

This vault is the map of content for the project. Start here, then drill into the linked notes.

## Core topics

| Topic | Note |
|-------|------|
| Code layout, engine, adapters | [[Architecture Overview]] |
| Session init, subprocess loop, concurrency | [[Deep Dive - Execution Logic]] |
| Every `testo` subcommand, flags, exit codes | [[Command Reference]] |
| Exit codes, NDJSON errors, debugging playbook | [[Troubleshooting and Error Codes]] |
| How runs are triggered, executed, and logged | [[QA Strategies]] |
| Prioritized refactor backlog | [[Technical Debt Tracker]] |
| AI agent onboarding | [[Agent Context Guide]] |

## Project Roadmap & Strategy

| Topic | Note |
|-------|------|
| Phased delivery (WHY) | [[Product Roadmap]] |
| V1 release task breakdown | [[V1 Release Roadmap]] |
| Project audit (2026-06-24) | [[Project Audit - 2026-06-24]] |
| Report links/artifacts always empty, fix (2026-07-06) | [[Report Links and Artifacts Missing Fix - 2026-07-06]] |
| Engineering hub | [[UQO Engineering Hub]] |
| ADRs & deep specs | [[Specs & ADRs/README]] |

## Release Management

| Phase | Gate checklist |
|-------|----------------|
| Hub | [[Release Management/README]] |
| 1 Foundation | [[Release Checklist - Phase 1 Foundation]] |
| 2 CI / Ghost / Runner | [[Release Checklist - Phase 2 CI Integrations]] · [[Release Checklist - Phase 2 Ghost Mode]] · [[Release Checklist - Phase 2 Runner Image]] |
| 3 UI / Delta / Dashboard | [[Release Checklist - Phase 3 Frontend Migration]] · [[Release Checklist - Phase 3 Delta Engine]] · [[Release Checklist - Phase 3 Unified Dashboard]] |
| 4 AI | [[Release Checklist - Phase 4 AI and Failure Analysis]] |
| Delta semantics | [[Delta Comparison Policy]] |

## Process & Guides

| Topic | Note |
|-------|------|
| CI integrations | [[CI-CD Pipeline Setup]] |
| Streamlit → React | [[Streamlit to React Migration Guide]] |
| E2E harness | [[E2E Harness Operations Guide]] |
| ReportPortal local | [[ReportPortal Local Setup Guide]] |
| Allure 2 → 3 migration | [[Allure 3 Migration Plan]] |
| PyPI publishing | [[Publishing to PyPI]] |
| Docker image publishing | [[Publishing Docker Images]] |
| Prompts | [[AI Prompt Engineering Lab]] |

## Quick links

- Configuration file: `testosterone.yaml` at repo root — [[Command Reference#`testo config`]], [[QA Strategies#Defining work in `testosterone.yaml`]]
- Sample cycles: `sample-pytests`, `sample-behave`, `behavex-flow-tests` in `testosterone.yaml`
- Headless legacy entry: `uqo` (deprecated alias; prefer `testo`)
- Optional surfaces: Streamlit UI (`testo-ui`), FastAPI (`testo-api`) — same engine, different adapters

## Typical flows

```bash
# Discover cycles, run smoke, open Allure
testo cycles list
testo run --cycle sample-pytests
testo report --cycle sample-pytests
```

For CI-style machine output, use `testo run --ci` (NDJSON on stdout). See [[QA Strategies#CI and streaming output]].

## External references

| Technology | Official documentation |
|------------|------------------------|
| Allure Report 3 | https://allurereport.org/docs/v3/ |
| Allure Report (legacy v2) | https://docs.qameta.io/allure/ |
| ReportPortal | https://reportportal.io/docs/ |
| ReportPortal API | https://reportportal.io/docs/api-development/ |
| Docker Engine | https://docs.docker.com/engine/ |
| Docker Compose | https://docs.docker.com/compose/ |
| Streamlit | https://docs.streamlit.io/ |
| React | https://react.dev/ |

## Related reading in-repo

- `ARCHITECTURE.md` — full UQO platform (Docker, MinIO, Postgres, Allure Server)
- `README.md` — quickstart and infrastructure compose stack
