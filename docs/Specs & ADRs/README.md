---
type: spec
status: current
created: 2026-06-25
updated: 2026-10-07
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
| Changelog enforcement | [changelog_automation_policy.md](../changelog_automation_policy.md) |

Older plans and incident write-ups (Allure 3 migration plan, reporters port, report-links fix, CLI–UI parity, the `doctor`/`clean`/`watch`/`init` restore) are in the [Archive](../Archive/README.md).
