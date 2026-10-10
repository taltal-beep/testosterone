## Summary

<!-- What does this PR change, and why? -->

## Test plan

<!-- How did you verify this? Commands run, tests added, manual steps. -->

## Checklist

- [ ] `pytest -q -m "tier_fast and not quarantined" --no-cov` passes locally
- [ ] `ruff check .` passes locally
- [ ] `CHANGELOG.md` updated under `## [Unreleased]`, or this PR has the `no-changelog` label
- [ ] Relevant `docs/` note updated if this changes CLI args, exit codes, `testosterone.yaml` parsing, or a workflow lifecycle (its `updated` date bumped; `python scripts/docs_vault.py lint` passes)
