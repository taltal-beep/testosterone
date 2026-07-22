# Contributing to Testosterone

## Setup

```bash
git clone https://github.com/taltal-beep/testosterone.git
cd testosterone
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pre-commit install   # one-time; runs ruff + changelog-format checks before each commit
```

See [README Quickstart](README.md#quickstart-copypaste) for the full local infrastructure setup (Postgres, MinIO, Allure, frontend).

## Before opening a PR

- **Tests**: `pytest -q -m "tier_fast and not quarantined" --no-cov` — this is the required check in CI (`ci.yml`'s `test` job).
- **Lint**: `ruff check .` — blocking in CI. `mypy testo_core` is advisory (see [Technical Debt Tracker](docs/Testing%20Workflows/Technical%20Debt%20Tracker.md) for the known baseline).
- **Commit messages**: [Conventional Commits](https://www.conventionalcommits.org/) (`feat:`, `fix:`, `test:`, `chore:`, `docs:`, ...) — enforced by `commitlint` in CI against `commitlint.config.js`.
- **Changelog**: add an entry under `## [Unreleased]` in `CHANGELOG.md` (Keep a Changelog format) for any non-doc change. CI's `changelog_required` job fails PRs that skip this — apply the `no-changelog` label if the change genuinely doesn't warrant an entry (pure test/CI/refactor with no user-facing effect).
- **Behave features**: always target explicitly (`behave features/smoke.feature`), never rely on cwd auto-discovery — see [Command Reference](docs/CLI%20Commands/Command%20Reference.md).

## Docs

If your change alters CLI arguments, exit codes, `testosterone.yaml` config parsing, or a workflow lifecycle, update the matching note under `docs/` (the Obsidian vault — start at [docs/Index.md](docs/Index.md)) in the same PR. Large or multi-step changes (migrations, refactors, new architecture) should also get an entry in `docs/Specs & ADRs/` or `docs/Testing Workflows/Technical Debt Tracker.md` as appropriate.

## PR review

Code review runs as a local pre-push hook (`.claude/settings.json`), not in CI — see commit `990be121` for why the earlier CI-based review was dropped.
