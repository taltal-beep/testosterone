# Repository Pattern — Database-Agnostic Refactor

<!-- source: notion https://www.notion.so/354d95cd031280a0b949f5d011bab26b -->

## Decision (WHY)

Teams should adopt Testo without migrating to a mandated database. Run history and archives must work against SQLite (zero-config local), PostgreSQL (compose/default), or MySQL (enterprise) via a single connection string.

## Current implementation (HOW — codebase)

| Piece | Location |
|-------|----------|
| URL resolution | `testo_core/db_config.py` — `DATABASE_URL`, legacy `POSTGRES_*`, default SQLite |
| Service locator | `testo_core/db.py` — `get_repository()`, `get_report_archive_repository()` |
| Protocol | `testo_core/repository/base.py` — `BaseRunRepository` |
| Adapters | `testo_core/repository/adapters.py`, `factory.py` |
| Models | `testo_core/repository/models.py` — dialect-portable JSON columns |

Configure via `database.url` in [testosterone.yaml](../../testosterone.yaml) or `DATABASE_URL`. See [Command Reference § Environment variables (common)](../CLI%20Commands/Command%20Reference.md#environment-variables-common) and [Architecture Overview § Configuration as the single source of truth](../Architecture/Architecture%20Overview.md#configuration-as-the-single-source-of-truth).

## Release verification

[Release Checklist - Phase 1 Foundation](../Archive/Release%20Checklist%20-%20Phase%201%20Foundation.md) — repository contract tests and packaging gate.

---
**Context & Links:** [Architecture Overview](../Architecture/Architecture%20Overview.md), [Product Roadmap § Phase 1: Decoupling & Distribution (Foundation)](../Roadmap%20&%20Strategy/Product%20Roadmap.md#how-it-got-here), [Release Checklist - Phase 1 Foundation](../Archive/Release%20Checklist%20-%20Phase%201%20Foundation.md)
