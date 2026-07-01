# Phase 2 CI Integrations

Phase 2 introduces pre-packaged CI wrappers that keep orchestration logic centralized in `testo_core` and the `uqo run` CLI contract.

## Architecture boundary

- Core execution remains in `testo_core` and `uqo run`.
- CI wrappers are thin adapters that only prepare inputs and consume stable machine outputs.
- CI provenance is normalized in service/CLI boundaries and persisted through existing repository metadata fields, with no CI-provider logic in repository adapters.

## Ghost mode (CI execution policy)

CI wrappers and direct `uqo run` invocations resolve ghost mode using:

1. `--no-ghost`
2. `--ghost`
3. `--ci`
4. provider environment auto-detection

When ghost mode is active, stdout remains machine-readable (summary JSON, or NDJSON + summary with `--stream-json`), persistence defaults to on unless `--no-persist` is passed, and final summary includes sync status details.

**Design intent:** In CI, Testo acts as a "ghost" — run tests, push metadata and artifacts to the configured DB/object store, exit without starting Streamlit or React. Provider detection and `execution_mode=ghost` metadata stay in the service layer (`testo_core/services/ghost_policy.py`, `ci_provenance.py`), not in repository adapters. Details: [[QA Strategies#CI and streaming output]], [[Deep Dive - Execution Logic]], [[Troubleshooting and Error Codes#Ghost / CI output]].

## Canonical CI provenance fields

When running in ghost mode, persisted metadata may include:

- `trigger_source=ci`
- `execution_mode=ghost`
- `ci_provider` (`github`, `gitlab`, `buildkite`, `circleci`, `jenkins`, `azure_pipelines`, `generic`)
- `ci_pipeline_id`
- `ci_job_id`
- `ci_commit_sha`
- `ci_ref_name`

## GitHub Action

Source lives under `integrations/github-action/`.

Minimal consumer usage:

```yaml
- uses: ariel-evn/uqo-action@v1
  with:
    config-path: ./.uqo/config.yaml
    runner-image: docker.io/ariel-evn/uqo-runner:v1
    runner-prebuilt: true
```

## GitLab include template

Template lives at `ci/gitlab/testo.gitlab-ci.yml`.

Minimal consumer include:

```yaml
include:
  - project: "ariel-evn/unified-quality-orchestration-reporting-dashboard"
    file: "/ci/gitlab/testo.gitlab-ci.yml"

variables:
  UQO_CONFIG_PATH: ".uqo/config.yaml"
  UQO_RUNNER_IMAGE: "docker.io/ariel-evn/uqo-runner:v1"
  UQO_RUNNER_PREBUILT: "true"
```

GitLab template variables:

- `UQO_CONFIG_PATH` (required)
- `UQO_GHOST_MODE` (`auto` default)
- `UQO_STREAM_JSON` (`false` default)
- `UQO_PERSIST` (`true` default)
- `UQO_RUNNER_IMAGE` (empty default, optional image override)
- `UQO_RUNNER_PREBUILT` (`auto` default, supports `true|false|auto`)

## Runner image behavior

- Core runner image selection is handled by `testo_core.runners` via `UQO_RUNNER_IMAGE`.
- `UQO_RUNNER_PREBUILT=true` skips runtime `pip install -r requirements.txt` in the execution container.
- `UQO_RUNNER_PREBUILT=false` keeps legacy behavior with runtime dependency install.
- `UQO_RUNNER_PREBUILT=auto` enables prebuilt behavior when a custom image is provided and keeps legacy behavior on default image.
- Image pull/auth/network failures are classified as infrastructure failures (`exit_code=3`).

## Tiered test harness commands

Tier selection is marker-driven and shared across local, GitHub Actions, and GitLab CI:

- Fast required gate:
  - `python -m pytest -q -m "tier_fast and not quarantined" --maxfail=1 --no-cov`
- Heavy optional gate:
  - `python -m pytest -q -m "tier_heavy and not tier_external" --maxfail=1 --durations=25`
- External nightly/release gate:
  - `python -m pytest -q -m "tier_external and cleanup_required" --maxfail=1 --durations=50`

Reference CI definitions:

- GitHub: `.github/workflows/ci.yml` (unified format → test → deploy pipeline; the fast-required gate lives in its `test` job), `.github/workflows/pr-heavy.yml`, `.github/workflows/nightly-external.yml`, `.github/workflows/release-gate.yml`. Code review runs via a local pre-push hook (`.claude/settings.json`), not in CI.
- GitLab: `ci/gitlab/testo.tests.gitlab-ci.yml`, `ci/gitlab/testo.external.gitlab-ci.yml`

All tier jobs upload diagnostics artifacts (`logs`, summary JSON, API responses, screenshots when present) on failure, and external suites run with `external-e2e` concurrency isolation.

## Versioning policy

- GitHub action: publish immutable semver tags (`v1.0.0`, `v1.0.1`, ...), keep `v1` moving to latest stable `v1.x`, and recommend SHA pinning for strict supply-chain policies.
- GitLab template: pin `include` to immutable tag or commit SHA in production pipelines.
- Runner image tags:
  - immutable: `v1.x.y`, `sha-<commit>`
  - moving: `v1`, `latest`
- Compatibility rule: `uqo-runner:v1.x.y` must embed a `testo-core` `1.x.y` compatible CLI contract (`uqo run` summary/NDJSON/exit semantics).

## Official documentation

| Topic | Reference |
|-------|-----------|
| Docker Engine | https://docs.docker.com/engine/ |
| Docker Compose | https://docs.docker.com/compose/ |
| Compose file spec | https://docs.docker.com/compose/compose-file/ |

---
**Context & Links:**
- [[QA Strategies#CI and streaming output]], [[Command Reference]], [[Architecture Overview]], [[Deep Dive - Execution Logic]]
- Gates: [[Release Checklist - Phase 2 CI Integrations]], [[Release Checklist - Phase 2 Ghost Mode]]
