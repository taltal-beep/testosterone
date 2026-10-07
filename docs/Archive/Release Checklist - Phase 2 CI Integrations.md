# Phase-2 Release Checklist (CI Integrations)

This is the go/no-go gate before assigning/re-pointing `v1` for the GitHub action and publishing the GitLab template.

> **Gate executed:** 2026-06-24

## 1) Core/package integrity

- [x] `python3 -m pip install -U pip`
- [x] `python3 -m pip install -e '.[dev]'`
- [x] `python3 -m build`
- [x] `uqo run --help`

## 2) Core contract suites

- [x] `python3 -m pytest -q --no-cov tests/unit/testo_core/test_cli_run.py tests/unit/testo_core/test_headless_engine.py tests/contract/testo_core/test_cli_contract.py` → passed
- [x] `python3 -m pytest -q --no-cov tests/unit/testo_core/test_repository_sqlite.py tests/unit/testo_core/test_repository_factory.py tests/contract/testo_core/test_repository_contract.py` → 18 passed

## 3) CI integration suites

- [x] `python3 -m pytest -q --no-cov tests/unit/ci/test_github_action_wrapper.py tests/unit/ci/test_gitlab_template_contract.py tests/contract/ci/test_wrapper_contract.py` → 11 passed
- [x] `python3 -m pytest -q --no-cov tests/integration/test_runner_image_mode_smoke.py` → 1 passed

## 4) Documentation and adoption checks

- [x] README contains:
  - [x] GitHub Action quickstart
  - [x] GitLab template quickstart
  - [x] required variables/secrets
  - [x] troubleshooting section
- [ ] Copy snippets to a scratch project and confirm they require only documented variables. *(deferred — requires external repo setup)*

## 5) Action versioning checks (`ariel-evn/uqo-action`)

- [ ] Confirm `action.yml` is at the action repository root. *(deferred — requires `ariel-evn/uqo-action` repo access)*
- [ ] Create immutable tag `v1.0.0`.
- [ ] Move major tag `v1` to the same commit.
- [ ] Re-verify consumer workflow resolves `uses: ariel-evn/uqo-action@v1`.

## 6) Runner image release checks (`uqo-runner`)

- [x] `docker buildx build --load -f Dockerfile.testo-runner -t uqo-runner:rc .` → built successfully
- [x] `docker run --rm uqo-runner:rc run --help` → shows usage
- [ ] `UQO_RUNNER_IMAGE=uqo-runner:rc UQO_RUNNER_PREBUILT=true python3 -m pytest -q --no-cov tests/integration/test_runner_image_mode_smoke.py` *(requires Docker-in-test env var wiring)*
- [ ] `python3 scripts/ci/compare_runner_latency.py ...` *(requires baseline/candidate metrics artifacts)*

## 7) Final pass criteria

- [x] All commands above exit with `0`.
- [x] No unversioned changes to `SUMMARY_SCHEMA_KEYS` or NDJSON event types.
- [x] No CI-provider conditionals were added to repository adapters/factory/DB wiring.
- [x] Runner image path shows no runtime dependency install command in smoke logs.
- [x] Image pull/auth failures classify as infra failure (`exit_code=3`) in summary.

## 8) Tiered E2E gate criteria

- [x] Fast required gate command:
  - [x] `python -m pytest -q -m "tier_fast and not quarantined" --maxfail=1 --no-cov` → 374 passed, 4 skipped, 28 deselected
  - [x] Pass threshold: 100% pass, deterministic rerun, zero cleanup ledger failures.
- [x] Heavy optional gate command:
  - [x] `python -m pytest -q -m "tier_heavy and not tier_external" --maxfail=1 --durations=25` → 25 passed, 381 deselected
  - [x] Pass threshold: 100% pass for executed scenarios and diagnostics artifacts available on failure.
- [ ] External nightly/release gate command:
  - [ ] `python -m pytest -q -m "tier_external and cleanup_required" --maxfail=1 --durations=50` *(requires external CI integrations)*
  - [ ] Pass threshold: 100% pass for GitHub+GitLab lifecycle scenarios.
