# Changelog Automation and CI Enforcement Policy

## Decision (WHY)

`CHANGELOG.md` (repo root, [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) format) closes [[V1 Release Roadmap#Workstream 6: Documentation & CHANGELOG]] items 6.1–6.5. Two problems beyond "does the file exist": nothing stopped it from going stale, and nothing kept future entries consistent. This spec adds CI enforcement plus an AI-drafted entry step so the file stays current without relying on someone remembering to update it by hand.

## Current implementation (HOW)

| Item | Location |
|------|----------|
| Changelog | `CHANGELOG.md` — `## [Unreleased]` + dated `## [x.y.z] - YYYY-MM-DD` sections, paired with `pyproject.toml` / `frontend/package.json` semver (currently `0.1.0`) |
| Commit message linting | `commitlint.config.js` (`@commitlint/config-conventional`, no overrides — existing `feat:`/`fix:`/`test:` commits already conform) + `.github/workflows/commitlint.yml` |
| PR-time changelog check | `changelog_required` job in `.github/workflows/pr-fast.yml` — fails a PR that changes non-doc files without touching `CHANGELOG.md`. Escape hatch: `no-changelog` label (same idiom as `pr-heavy.yml`'s `e2e-heavy` label) |
| AI auto-draft on `main` | `.github/workflows/changelog-on-main.yml` — triggers on every push to `main`, runs `anthropics/claude-code-base-action` to summarize the pushed commit range into `## [Unreleased]`, then the workflow (not the action) commits and pushes directly to `main` |
| Format guard | `scripts/check_changelog_format.py` — asserts exactly one `## [Unreleased]` heading and that every version heading is `x.y.z - YYYY-MM-DD`; run after the AI edit before it's allowed to push |

## Known risk: no review step on the AI path

`changelog-on-main.yml` pushes straight to `main` — there is deliberately no PR/review gate on this path. A bad or misattributed summary ships without a human catching it first. Mitigations:

- The AI's tool access is scoped to `Read`/`Edit` on `CHANGELOG.md` plus read-only `git log`/`git diff` — it cannot touch any other file.
- `scripts/check_changelog_format.py` runs after every AI edit; a structurally broken file blocks the push.
- `## [Unreleased]` stays human-editable right up until the next version is cut, so a bad entry can still be corrected before it's ever attached to a release.

**Loop prevention** (three independent layers — if you touch one, re-verify the other two still hold): `paths-ignore: [CHANGELOG.md]` on the workflow trigger, a job-level `if: github.actor != 'github-actions[bot]'` guard, and `[skip ci]` in the bot's own commit message.

## Prerequisites (GitHub repo settings, not files)

- Secret `CHANGELOG_BOT_TOKEN` — a PAT/App token for an identity allowed to bypass "require pull request before merging" on `main` (the default `GITHUB_TOKEN` cannot push past branch protection).
- Secret `ANTHROPIC_API_KEY` for the Claude Code action.
- `commitlint` and `changelog_required` added to the branch protection rule's required status checks.

## Backfill provenance

The `## [0.1.0]` entry was adopted from `sprint-4/publish-and-document` (commit `3b1bfb18`, unmerged at the time this spec was written), which had already derived it from git history and the four `Release Checklist - Phase *` gates. One commit was added on top to cover work that landed on `main` after that branch diverged (`#35`, sensitive-key redaction and failure-context wiring).

## Operator commands

`no-changelog` PR label to skip the changelog-required check on trivial PRs. See [[V1 Release Roadmap#Workstream 6: Documentation & CHANGELOG]], [[Release Management/README]].

---
**Context & Links:** [[V1 Release Roadmap]], [[Product Roadmap]], [[CI-CD Pipeline Setup]]
