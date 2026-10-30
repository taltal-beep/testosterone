---
type: spec
status: current
created: 2026-06-25
updated: 2026-10-30
---

# Specs & ADRs

Design decisions that still describe the code. The code is the source of truth; see [Architecture Overview](../Architecture/Architecture%20Overview.md) and [Deep Dive - Execution Logic](../Architecture/Deep%20Dive%20-%20Execution%20Logic.md) for how it fits together.

| Topic | Note |
|-------|------|
| Packaging as a library (`testo-core`) | [Library Packaging](Library%20Packaging.md) |
| Database-agnostic storage | [Repository Pattern - Database-Agnostic Refactor](Repository%20Pattern%20-%20Database-Agnostic%20Refactor.md) |
| Any test runner as a stage | [Command Adapter and JUnit Import](Command%20Adapter%20and%20JUnit%20Import%20-%202026-09-25.md) |
| Run-to-run delta | [Phase 3 Delta Comparison Engine Plan](Phase%203%20Delta%20Comparison%20Engine%20Plan.md) → [Delta Comparison Policy](Delta%20Comparison%20Policy.md) |
| Unified dashboard | [Phase 3 Unified Dashboard Plan](Phase%203%20Unified%20Dashboard%20Plan.md) |
| BYOK AI failure summaries | [Phase 4 BYOK and Failure Analysis](Phase%204%20BYOK%20and%20Failure%20Analysis.md) |
| Cycles-first UI | [Phase 5 UI Redesign - Cycles-First Navigation](Phase%205%20UI%20Redesign%20-%20Cycles-First%20Navigation.md) |
| Navy glass look and sidebar | [UI Restyle - 2026-10-19](UI%20Restyle%20-%202026-10-19.md) |
| One engine, generated API types, blocking type checks | [Architecture Consolidation - 2026-10-06](Architecture%20Consolidation%20-%202026-10-06.md) |
| Interview-readiness batch (pull requests 67 to 91, v1.1.0) | [Interview Readiness Fixes - 2026-10-07](Interview%20Readiness%20Fixes%20-%202026-10-07.md) |
| Docs vault as second brain, wiki generated from `docs/` | [Docs Vault and Wiki Sync - 2026-10-07](Docs%20Vault%20and%20Wiki%20Sync%20-%202026-10-07.md) |
| Post-publish features: flaky tests, PR comments, plugins, adapters | [Open Source Features - 2026-10-19](Open%20Source%20Features%20-%202026-10-19.md) |
| Run summary and PR comment from the GitHub Action | [GitHub Action PR Comment - 2026-10-19](GitHub%20Action%20PR%20Comment%20-%202026-10-19.md) |
| Getting Started guide and the MkDocs docs site | [Docs Site - 2026-10-19](Docs%20Site%20-%202026-10-19.md) |
| Third-party frameworks and reporters through entry points | [Plugin API - 2026-10-19](Plugin%20API%20-%202026-10-19.md) |
| Playwright as its own equipment | [Playwright Adapter - 2026-10-19](Playwright%20Adapter%20-%202026-10-19.md) |
| Quarantining flaky tests so they don't fail the run | [Flaky Test Quarantine - 2026-10-22](Flaky%20Test%20Quarantine%20-%202026-10-22.md) |
| Pools of keys (VMs, devices, accounts) leased to parallel workers | [Resource Pools and Leases - 2026-10-26](Resource%20Pools%20and%20Leases%20-%202026-10-26.md) |
| Checking keys, clean releases and a delay before reusing an expired key | [Resource Lifecycle Hooks - 2026-10-26](Resource%20Lifecycle%20Hooks%20-%202026-10-26.md) |
| Playwright JSON reports: retries, flaky tests, traces | [Playwright JSON Import - 2026-10-22](Playwright%20JSON%20Import%20-%202026-10-22.md) |
| Reading Jest/Vitest, .NET, Go, Robot, RSpec, k6, XCTest, Android and Allure results in their own formats | [Runner Coverage - 2026-10-26](Runner%20Coverage%20-%202026-10-26.md) |
| Runs, stages and tests as OpenTelemetry traces (OTLP), off by default | [OpenTelemetry Export - 2026-10-30](OpenTelemetry%20Export%20-%202026-10-30.md) |
| Slack and Teams alerts, failure annotations on the diff, flaky test issues | [Alerts Where Developers Look - 2026-10-22](Alerts%20Where%20Developers%20Look%20-%202026-10-22.md) |
| BehaveX HTML report plus Allure results | [BehaveX Reports - 2026-10-21](BehaveX%20Reports%20-%202026-10-21.md) |
| JSON Schema for `testosterone.yaml` (editor autocomplete) | [Config JSON Schema - 2026-10-22](Config%20JSON%20Schema%20-%202026-10-22.md) |
| Record results from any CI (`testo ingest`) and a shared team server | [Ingest and Team Server - 2026-10-22](Ingest%20and%20Team%20Server%20-%202026-10-22.md) |
| Capped concurrent API runs and opt-in parallel stages | [Scale Runs and Stages - 2026-10-24](Scale%20Runs%20and%20Stages%20-%202026-10-24.md) |
| Optional persistent run queue and per-user accounts, off by default | [Switchable Team Features - 2026-10-24](Switchable%20Team%20Features%20-%202026-10-24.md) |
| Running each server-started stage in a throwaway container, off by default | [Throwaway Stage Containers - 2026-10-24](Throwaway%20Stage%20Containers%20-%202026-10-24.md) |
| Changelog enforcement | [changelog_automation_policy.md](../changelog_automation_policy.md) |
| Product roadmap from the product review (failing tests first, and what follows) | [Product Roadmap Work - 2026-10-25](Product%20Roadmap%20Work%20-%202026-10-25.md) |
| Product review second pass: every area except trust toward 10 | [Product to Ten - 2026-10-25](Product%20to%20Ten%20-%202026-10-25.md) |
| Project health page: a repeatable test health score and an optional AI review of the tests | [Project Health - 2026-10-26](Project%20Health%20-%202026-10-26.md) |
| README badge, asking about your tests, Jira issues from failures (and what was not built) | [Qualflare Follow-ups - 2026-10-26](Qualflare%20Follow-ups%20-%202026-10-26.md) |

Older plans and incident write-ups (Allure 3 migration plan, reporters port, report-links fix, CLI–UI parity, the `doctor`/`clean`/`watch`/`init` restore) are in the [Archive](../Archive/README.md).
