# Changelog Generation and CI Enforcement Policy

`CHANGELOG.md` (repo root) follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/):
an `## [Unreleased]` section plus dated `## [x.y.z] - YYYY-MM-DD` sections, paired with
the project's existing semver (`pyproject.toml` / `frontend/package.json`, currently
`0.1.0`).

## Enforcement

Two independent CI checks, both required on PRs:

- **`commitlint`** (`.github/workflows/commitlint.yml`) — lints commit messages in a
  PR against `commitlint.config.js` (`@commitlint/config-conventional`, no overrides;
  the repo's existing `feat:`/`fix:`/`test:` commits already conform).
- **`changelog_required`** (a job inside `.github/workflows/ci.yml`, the unified
  format -> test -> deploy pipeline) — fails a PR that changes non-doc files without
  also touching `CHANGELOG.md`. Escape hatch: apply the `no-changelog` label for PRs
  that don't warrant an entry (same idiom `pr-heavy.yml` uses for its `e2e-heavy` label).

## AI auto-changelog on main

`.github/workflows/changelog-on-main.yml` triggers on every push to `main` and uses
`anthropics/claude-code-base-action` to read the pushed commit range and draft an entry
under `## [Unreleased]`, then commits the result **directly to `main`, with no PR review
step**. This was a deliberate choice, not an oversight — the tradeoff:

- **Known risk**: AI-authored content lands on `main` unreviewed. A bad summary, or one
  that misattributes a change, ships without a human catching it first.
- **Mitigations**: the workflow runs `scripts/check_changelog_format.py` after the AI
  edit and refuses to push if the file is structurally broken (missing `[Unreleased]`
  heading, malformed version heading); the AI's tool access is scoped to
  read/edit `CHANGELOG.md` only, plus read-only `git log`/`git diff`; and
  `## [Unreleased]` stays human-editable right up until the next real version is cut, so
  a bad entry can be fixed before it's ever attached to a release.
- **Loop prevention** (three independent layers — verify all three still hold if any one
  is touched): `paths-ignore: [CHANGELOG.md]` on the trigger, a job-level
  `if: github.actor != 'github-actions[bot]'` guard, and `[skip ci]` in the bot's own
  commit message.

### Prerequisites (GitHub repo settings, not files)

- Secret `CHANGELOG_BOT_TOKEN` — a PAT/App token for an identity allowed to push past
  branch protection on `main` (the default `GITHUB_TOKEN` cannot).
- Secret `ANTHROPIC_API_KEY` for the Claude Code action.
- `main` branch protection updated to let that bot identity bypass "require pull
  request before merging."
- `commitlint` and `changelog_required` added to the branch protection rule's required
  status checks.

## Backfill

The initial `## [0.1.0] - 2026-07-01` entry was backfilled from the four completed
development phases, sourced from `docs/Release Management/release_checklist_phase*.md`
cross-referenced with `git log`. No version tags exist in this repo yet (`git tag -l` is
empty), so `0.1.0` covers everything shipped to date rather than being split across
invented historical releases.
