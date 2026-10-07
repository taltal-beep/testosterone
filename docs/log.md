---
type: log
status: current
created: 2026-10-07
updated: 2026-10-07
---

# Vault log

Append-only record of changes to the vault's shape. Rules are in the [vault schema](CLAUDE.md#log).

## 2026-06-25: vault created

Notes moved into `docs/` as an Obsidian vault, and copied once by hand to the GitHub wiki.

## 2026-10-07: restructure for GitHub

Wikilinks converted to relative markdown links, dated plans and checklists moved to `Archive/`, Index, Product Roadmap and Technical Debt Tracker rewritten (pull request 74).

## 2026-10-07: schema, lint and wiki sync

Added the [vault schema](CLAUDE.md), frontmatter on every note, `scripts/docs_vault.py lint` in CI, and a workflow that regenerates the GitHub wiki from `docs/`. The lint found four leftover wikilinks in Architecture Overview, Deep Dive - Execution Logic and GitLab Pages Demo; fixed. The wiki had not changed since 2026-06-24.
