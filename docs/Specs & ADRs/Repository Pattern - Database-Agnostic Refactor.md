---
type: spec
status: current
created: 2026-06-25
updated: 2026-11-01
---

# Repository Pattern — Database-Agnostic Refactor

<!-- source: notion https://www.notion.so/354d95cd031280a0b949f5d011bab26b -->

## Decision (WHY)

Teams should adopt Testo without migrating to a mandated database. Run history and archives must work against SQLite (zero-config local), PostgreSQL (compose/default), or MySQL (enterprise) via a single connection string.

## Current implementation (HOW — codebase)

| Piece | Location |
|-------|----------|
| URL resolution | `testo_core/repository/db_config.py` — `DATABASE_URL`, legacy `POSTGRES_*`, default SQLite |
| Service locator | `testo_core/repository/db.py` — `get_repository()`, `get_report_archive_repository()` |
| Protocol | `testo_core/repository/base.py` — `BaseRunRepository` |
| Adapters | `testo_core/repository/adapters.py`, `factory.py` |
| Models | `testo_core/repository/models.py` — dialect-portable JSON columns |
| Schema migrations | `testo_core/repository/migrations/` — Alembic revisions, run in-process by `create_db_and_tables()` |

Configure via `database.url` in [testosterone.yaml](../../testosterone.yaml) or `DATABASE_URL`. See [Command Reference § Environment variables (common)](../CLI%20Commands/Command%20Reference.md#environment-variables-common) and [Architecture Overview § Configuration as the single source of truth](../Architecture/Architecture%20Overview.md#configuration-as-the-single-source-of-truth).

## Schema migrations (2026-11-01)

Until 1.5.0 the schema came from `SQLModel.metadata.create_all()` at startup, and a column added to an existing table needed a manual `ALTER TABLE` (or each store patched its own table at startup, as `resources/store.py` did). Since [Architecture Review - 2026-10-31](Architecture%20Review%20-%202026-10-31.md) recommendation 1, the schema is owned by Alembic revisions in `testo_core/repository/migrations/versions/`, numbered `0001_baseline.py`, `0002_…`:

- `create_db_and_tables()` (`repository/db_config.py`) upgrades the active database to the newest revision. Every store (`accounts.py`, `services/triage.py`, `resources/store.py`, `testo_api/run_queue.py`) and the repository locator call it; nothing calls `create_all()` on a real database any more. Several processes starting on one database at once is fine: the first upgrades, the rest find the schema at head.
- A database from 1.5.0 or earlier (tables but no `alembic_version`) is adopted on first open: missing tables and columns are added with the models' defaults, then it is stamped at `0001` and upgraded. Nothing is dropped and nobody runs a command by hand; the team server's Postgres upgrades in place when the image restarts.
- A model change ships with a revision in the same pull request. `python scripts/db_revision.py "what changed"` writes it from the model diff (read it: autogenerate cannot see renames). `tests/unit/testo_core/repository/test_migrations.py` compares the models with the migrated schema and fails on any difference.
- `alembic` is a core dependency, like `sqlmodel`, because `testo run` always saves history.

## Release verification

[Release Checklist - Phase 1 Foundation](../Archive/Release%20Checklist%20-%20Phase%201%20Foundation.md) — repository contract tests and packaging gate.

---
**Context & Links:** [Architecture Overview](../Architecture/Architecture%20Overview.md), [Product Roadmap § Phase 1: Decoupling & Distribution (Foundation)](../Roadmap%20&%20Strategy/Product%20Roadmap.md#how-it-got-here), [Release Checklist - Phase 1 Foundation](../Archive/Release%20Checklist%20-%20Phase%201%20Foundation.md)
