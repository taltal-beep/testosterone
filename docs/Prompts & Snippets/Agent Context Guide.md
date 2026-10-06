# Agent Context Guide

You are assisting an engineer on the Testo CLI orchestration project. To save tokens and avoid scanning the entire codebase blindly, use this file as your master map to find existing documentation.

## Core Reference Map

* **Architecture & Flow:** If asked to modify execution logic, runtime state, or core modules, read `[[Architecture Overview]]` and `[[Deep Dive - Execution Logic]]` first. Do not hallucinate the lifecycle phases.
* **CLI Modifications:** Before adding, editing, or refactoring a command, flag, or exit code, reference `[[Command Reference]]` and `[[Troubleshooting and Error Codes]]` to maintain structural consistency.
* **Release & Deployments:** When dealing with CI/CD pipelines, container environments, or infrastructure runners, check the active checklists in `[[Release Management/]]` (e.g. `[[Release Checklist - Phase 2 CI Integrations]]`, `[[Release Checklist - Phase 2 Ghost Mode]]`, `[[Release Checklist - Phase 2 Runner Image]]`).
* **CI/CD & Ghost Mode:** `[[CI-CD Pipeline Setup]]`, `[[QA Strategies#CI and streaming output]]`
* **Reporting Integrations:** `[[ReportPortal Local Setup Guide]]`, `[[QA Strategies#How results are logged and surfaced]]`, `[[Command Reference]]` (reporter types section)
* **E2E Validation:** `[[E2E Harness Operations Guide]]`
* **UI:** React frontend only (`frontend/`); the Streamlit migration is complete — `[[Streamlit to React Migration Guide]]` is historical.
* **Delta Semantics:** `[[Delta Comparison Policy]]`
* **Engineering Debt:** `[[Technical Debt Tracker]]`
* **Prompts / AI Experiments:** `[[AI Prompt Engineering Lab]]`
* **Business & Strategy Context:** For the "why" behind features, upcoming milestones, or legacy migrations, read `[[Roadmap & Strategy/Product Roadmap]]`.

## Rules for AI Agent Behavior

1. **Read Before Writing:** Always check the relevant documentation file listed above before refactoring core architecture or modifying a CLI argument.
2. **Documentation Debt:** If you modify a CLI command, change execution state logic, or alter infrastructure setups in the source code, you are strictly required to update the corresponding documentation file in `/docs` within the same execution plan or pull request.
3. **Token Conservation:** Keep code explanations concise. If an architectural explanation or troubleshooting step is already detailed in the documentation, point the engineer to that file using `[[Wiki-links]]` instead of printing massive text walls in the chat.
4. **Wiki-link Stems:** Obsidian resolves `[[links]]` from filename stems. After vault refactors, update this guide and `[[Index]]` in the same change set so the knowledge graph stays intact.
