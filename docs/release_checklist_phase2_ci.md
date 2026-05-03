# Phase-2 Release Checklist (CI Integrations)

This is the go/no-go gate before assigning/re-pointing `v1` for the GitHub action and publishing the GitLab template.

## 1) Core/package integrity

- `python3 -m pip install -U pip`
- `python3 -m pip install -e '.[dev]'`
- `python3 -m build`
- `uqo run --help`

## 2) Core contract suites

- `python3 -m pytest -q --no-cov tests/unit/uqo_core/test_cli_run.py tests/unit/uqo_core/test_headless_engine.py tests/contract/uqo_core/test_cli_contract.py`
- `python3 -m pytest -q --no-cov tests/unit/uqo_core/test_repository_sqlite.py tests/unit/uqo_core/test_repository_factory.py tests/contract/uqo_core/test_repository_contract.py`

## 3) CI integration suites

- `python3 -m pytest -q --no-cov tests/unit/ci/test_github_action_wrapper.py tests/unit/ci/test_gitlab_template_contract.py tests/contract/ci/test_wrapper_contract.py`
- `python3 -m pytest -q --no-cov tests/integration/test_runner_image_mode_smoke.py`

## 4) Documentation and adoption checks

- README contains:
  - GitHub Action quickstart
  - GitLab template quickstart
  - required variables/secrets
  - troubleshooting section
- Copy snippets to a scratch project and confirm they require only documented variables.

## 5) Action versioning checks (`ariel-evn/uqo-action`)

- Confirm `action.yml` is at the action repository root.
- Create immutable tag `v1.0.0`.
- Move major tag `v1` to the same commit.
- Re-verify consumer workflow resolves `uses: ariel-evn/uqo-action@v1`.

## 6) Runner image release checks (`uqo-runner`)

- `docker buildx build --load -f Dockerfile.uqo-runner -t uqo-runner:rc .`
- `docker run --rm uqo-runner:rc run --help`
- `UQO_RUNNER_IMAGE=uqo-runner:rc UQO_RUNNER_PREBUILT=true python3 -m pytest -q --no-cov tests/integration/test_runner_image_mode_smoke.py`
- `python3 scripts/ci/compare_runner_latency.py --baseline artifacts/legacy.json --candidate artifacts/image.json --max-startup-regression 0 --min-e2e-improvement-pct 20`

## 7) Final pass criteria

- All commands above exit with `0`.
- No unversioned changes to `SUMMARY_SCHEMA_KEYS` or NDJSON event types.
- No CI-provider conditionals were added to repository adapters/factory/DB wiring.
- Runner image path shows no runtime dependency install command in smoke logs.
- Image pull/auth failures classify as infra failure (`exit_code=3`) in summary.

## 8) Tiered E2E gate criteria

- Fast required gate command:
  - `python -m pytest -q -m "tier_fast and not quarantined" --maxfail=1 --no-cov`
  - Pass threshold: 100% pass, deterministic rerun, zero cleanup ledger failures.
- Heavy optional gate command:
  - `python -m pytest -q -m "tier_heavy and not tier_external" --maxfail=1 --durations=25`
  - Pass threshold: 100% pass for executed scenarios and diagnostics artifacts available on failure.
- External nightly/release gate command:
  - `python -m pytest -q -m "tier_external and cleanup_required" --maxfail=1 --durations=50`
  - Pass threshold: 100% pass for GitHub+GitLab lifecycle scenarios, plugin path coverage included, cleanup audit reports zero leaked resources.
