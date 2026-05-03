# E2E Harness Operations

This document defines deterministic execution and cleanup for the tiered E2E harness.

## Flow lifecycle

All flow scenarios follow:

1. `provision`
2. `execute`
3. `poll`
4. `verify`
5. `cleanup` (always runs in `finally`)

Implementation lives under `tests/e2e/flows/`, `tests/e2e/provisioners/`, and `tests/e2e/verifiers/`.

## Tier commands

- Fast required: `python -m pytest -q -m "tier_fast and not quarantined" --maxfail=1 --no-cov`
- Heavy optional: `python -m pytest -q -m "tier_heavy and not tier_external" --maxfail=1 --durations=25`
- External nightly/release: `python -m pytest -q -m "tier_external and cleanup_required" --maxfail=1 --durations=50`

## Environment model

Common:

- `UQO_E2E_RUN_ID` (optional; auto-generated if not set)
- `UQO_E2E_KEEP_ON_FAIL` (default `false`)
- `UQO_E2E_MAX_CLEANUP_ATTEMPTS` (default `3`)
- `UQO_E2E_EXTERNAL_DRY_RUN` (`true` by default; set `false` in external CI gates)

GitHub external:

- `UQO_E2E_GITHUB_TOKEN`
- `UQO_E2E_GITHUB_OWNER`

GitLab external:

- `UQO_E2E_GITLAB_TOKEN`
- `UQO_E2E_GITLAB_GROUP_ID`
- `UQO_E2E_GITLAB_BASE_URL` (optional, defaults to `https://gitlab.com/api/v4`)

## Isolation and naming

- Ephemeral resources are named using `uqo-e2e-<run-id>-<provider>-<scenario>`.
- Artifacts are written under `.artifacts/e2e/<run-id>/`.
- External CI jobs use `external-e2e` concurrency/resource locking.

## Cleanup guarantees

- Every scenario writes cleanup records through `cleanup_ledger`.
- Session finalizer emits `.artifacts/e2e/<run-id>/cleanup-ledger.json`.
- External gates fail if cleanup audit detects any `cleanup_failed` record.

## Diagnostics artifacts

On failed heavy/external runs, upload:

- logs (`*.log`)
- summary JSON (`*summary*.json`)
- API responses (`*api*.json`)
- screenshots (`*.png`, if UI scenarios are enabled)

## Security and redaction

- Provider tokens must be injected via masked CI secrets/variables only.
- Do not print or serialize tokens into logs/artifacts.
- Keep provider API logic inside `tests/e2e/provisioners/` adapters.

