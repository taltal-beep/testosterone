# Testosterone GitHub Action

This composite action is a thin wrapper around the CLI contract:

`testo run [--config <path>] [--cycle <name>] --ci [--no-persist]`

It runs one cycle on the host runner, echoes the NDJSON event stream to the
job log, and exposes the final `plan_finished` event as step outputs.

## Inputs

- `config-path` (optional, default empty): path to `testosterone.yaml`; empty means discovery
- `cycle` (optional, default empty): cycle name; empty runs the only cycle, `all` runs every cycle
- `ci-mode` (optional, default `true`): NDJSON on stdout
- `persist` (optional, default `true`): write `plan_result.json` and the run history record
- `python-version` (optional, default `3.11`)

## Outputs

- `exit_code` (`0`–`4`, see `docs/CLI Commands/Troubleshooting and Error Codes.md`)
- `status` (`success`, `failure`, `invalid_input`, `infra_failure`, `internal_error`)
- `summary_json`: the final `plan_finished` (or `error`) NDJSON event
- `summary_path`: the same JSON saved under `$RUNNER_TEMP/testo-summary.json`

## Usage

```yaml
jobs:
  quality:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: taltal-beep/testosterone/integrations/github-action@v1
        with:
          cycle: sample-pytests
```

## Migrating from the v1.0 `uqo` action

The v1.0 inputs `ghost-mode`, `stream-json`, `runner-image` and `runner-prebuilt`
drove the removed headless/Docker runner and are gone; `testo run --ci` already
streams NDJSON and runs stages as host subprocesses. Use `Dockerfile.testo-runner`
as the job container if you want a pinned image. The `run_id` output is gone too:
it read the old summary JSON, which `testo run` does not emit.

## Versioning and pinning policy

- Publish immutable tags for every patch release: `v1.0.0`, `v1.0.1`, ...
- Keep moving major tag `v1` pointing to latest stable `v1.x`.
- For strict supply-chain policies, pin consumers to a commit SHA.
