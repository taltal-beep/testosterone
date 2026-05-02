# Phase 2 CI Integrations

Phase 2 introduces pre-packaged CI wrappers that keep orchestration logic centralized in `uqo_core` and the `uqo run` CLI contract.

## Architecture boundary

- Core execution remains in `uqo_core` and `uqo run`.
- CI wrappers are thin adapters that only prepare inputs and consume stable machine outputs.
- CI provenance is normalized in service/CLI boundaries and persisted through existing repository metadata fields, with no CI-provider logic in repository adapters.

## Ghost mode (CI execution policy)

CI wrappers and direct `uqo run` invocations resolve ghost mode using:

1. `--no-ghost`
2. `--ghost`
3. `--ci`
4. provider environment auto-detection

When ghost mode is active, stdout remains machine-readable (summary JSON, or NDJSON + summary with `--stream-json`), persistence defaults to on unless `--no-persist` is passed, and final summary includes sync status details.

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

Template lives at `ci/gitlab/uqo.gitlab-ci.yml`.

Minimal consumer include:

```yaml
include:
  - project: "ariel-evn/unified-quality-orchestration-reporting-dashboard"
    file: "/ci/gitlab/uqo.gitlab-ci.yml"

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

- Core runner image selection is handled by `uqo_core.runners` via `UQO_RUNNER_IMAGE`.
- `UQO_RUNNER_PREBUILT=true` skips runtime `pip install -r requirements.txt` in the execution container.
- `UQO_RUNNER_PREBUILT=false` keeps legacy behavior with runtime dependency install.
- `UQO_RUNNER_PREBUILT=auto` enables prebuilt behavior when a custom image is provided and keeps legacy behavior on default image.
- Image pull/auth/network failures are classified as infrastructure failures (`exit_code=3`).

## Versioning policy

- GitHub action: publish immutable semver tags (`v1.0.0`, `v1.0.1`, ...), keep `v1` moving to latest stable `v1.x`, and recommend SHA pinning for strict supply-chain policies.
- GitLab template: pin `include` to immutable tag or commit SHA in production pipelines.
- Runner image tags:
  - immutable: `v1.x.y`, `sha-<commit>`
  - moving: `v1`, `latest`
- Compatibility rule: `uqo-runner:v1.x.y` must embed a `uqo-core` `1.x.y` compatible CLI contract (`uqo run` summary/NDJSON/exit semantics).
