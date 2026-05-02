# UQO GitHub Action

This composite action is a thin wrapper around the stable CLI contract:

`uqo run --config <path> --ci [--ghost|--no-ghost]`

## Inputs

- `config-path` (required): path to UQO YAML config
- `ci-mode` (optional, default `true`)
- `ghost-mode` (optional, default `auto`; `true` -> `--ghost`, `false` -> `--no-ghost`)
- `stream-json` (optional, default `false`)
- `persist` (optional, default `true`)
- `runner-image` (optional, default empty; maps to `UQO_RUNNER_IMAGE`)
- `runner-prebuilt` (optional, default `auto`; maps to `UQO_RUNNER_PREBUILT`)
- `python-version` (optional, default `3.11`)

## Outputs

- `exit_code`
- `run_id`
- `summary_json`
- `summary_path`
- `status`

## Usage

```yaml
jobs:
  quality:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: ariel-evn/uqo-action@v1
        with:
          config-path: ./.uqo/load-test.yaml
          runner-image: docker.io/ariel-evn/uqo-runner:v1
          runner-prebuilt: true
```

## Versioning and pinning policy

- Publish immutable tags for every patch release: `v1.0.0`, `v1.0.1`, ...
- Keep moving major tag `v1` pointing to latest stable `v1.x`.
- For strict supply-chain policies, pin consumers to a commit SHA.
