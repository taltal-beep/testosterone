# CI Integrations

Pre-packaged CI wrappers keep orchestration in `testo_core`: they install `testo-core`, run `testo run --ci`, and keep its machine output.

## Architecture boundary

- Execution is `testo run` → `CycleRunService` → `engine.run_plan()`, the same path as a local run and an API execution.
- CI wrappers are thin adapters that only prepare flags and consume the NDJSON stream.
- CI provenance is detected from the environment by `DbBackend` (`testo_core/services/ci_provenance.py`) and stored on the run record; repository adapters stay provider-agnostic.

## Output contract in CI

`testo run --ci` writes one JSON object per line on stdout (`plan_started`, `stage_started`, `stage_finished`, `plan_finished`, plus `cycle_trigger` / `error` when relevant). The last line is `plan_finished` with `exit_code` and per-stage results. Exit codes `0`–`4`: [Troubleshooting and Error Codes](../CLI%20Commands/Troubleshooting%20and%20Error%20Codes.md).

v1.0's "ghost mode" (`uqo run --config … --ghost/--json/--stream-json` and a summary JSON) was removed in v1.1 together with the Docker-based headless runner it drove.

## Canonical CI provenance fields

Run records written in CI include (when the provider exposes them):

- `ci_provider` (`github`, `gitlab`, `buildkite`, `circleci`, `jenkins`, `azure_pipelines`, `generic`)
- `ci_pipeline_id`
- `ci_job_id`
- `ci_commit_sha`
- `ci_ref_name`

## GitHub Action

Source lives under `integrations/github-action/` (inputs: `config-path`, `cycle`, `ci-mode`, `persist`, `python-version`; outputs: `exit_code`, `status`, `summary_json`, `summary_path`).

```yaml
- uses: taltal-beep/testosterone/integrations/github-action@v1
  with:
    cycle: smoke
```

## GitLab include template

Template lives at `ci/gitlab/testo.gitlab-ci.yml`.

```yaml
include:
  - project: "taltal-beep/testosterone"
    file: "/ci/gitlab/testo.gitlab-ci.yml"

variables:
  TESTO_CYCLE: "smoke"
```

Variables: `TESTO_CONFIG_PATH` (empty = discovery), `TESTO_CYCLE` (empty = the only cycle), `TESTO_PERSIST` (`true` default). Artifacts: `testo-output.ndjson` and `testo-summary.json` (the `plan_finished` line).

## Runner image

`Dockerfile.testo-runner` builds an image whose entrypoint is `testo`. Use it as the CI job image when you want a pinned toolchain; stages run as subprocesses inside that job container. See [Publishing Docker Images](Publishing%20Docker%20Images.md).

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
- Compatibility rule: `testo-runner:v1.x.y` must embed a `testo-core` `1.x.y` compatible CLI contract (`testo run --ci` NDJSON and exit semantics).

## Official documentation

| Topic | Reference |
|-------|-----------|
| Docker Engine | https://docs.docker.com/engine/ |
| Docker Compose | https://docs.docker.com/compose/ |
| Compose file spec | https://docs.docker.com/compose/compose-file/ |

---
**Context & Links:**
- [QA Strategies § CI and streaming output](../Testing%20Workflows/QA%20Strategies.md#ci-and-streaming-output), [Command Reference](../CLI%20Commands/Command%20Reference.md), [Architecture Overview](../Architecture/Architecture%20Overview.md), [Deep Dive - Execution Logic](../Architecture/Deep%20Dive%20-%20Execution%20Logic.md)
- Gates (v1.0, historical): [Release Checklist - Phase 2 CI Integrations](../Archive/Release%20Checklist%20-%20Phase%202%20CI%20Integrations.md), [Release Checklist - Phase 2 Ghost Mode](../Archive/Release%20Checklist%20-%20Phase%202%20Ghost%20Mode.md)
