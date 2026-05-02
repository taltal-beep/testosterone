# Phase-2 Release Checklist (UQO Runner Image)

This checklist gates publication of the `uqo-runner` prebuilt image used by CI adapters.

## 1) Build and local smoke

- `docker buildx build --load -f Dockerfile.uqo-runner -t uqo-runner:rc .`
- `docker run --rm uqo-runner:rc run --help`
- `docker run --rm -e UQO_RUNNER_PREBUILT=true uqo-runner:rc run --config tests/fixtures/ci/ghost_minimal.yml --stream-json`

## 2) Contract and adapter validation

- `python3 -m pytest -q --no-cov tests/contract/uqo_core/test_cli_contract.py tests/contract/uqo_core/test_ghost_ndjson_contract.py tests/contract/uqo_core/test_ghost_summary_contract.py`
- `python3 -m pytest -q --no-cov tests/unit/ci/test_github_action_wrapper.py tests/unit/ci/test_gitlab_template_contract.py tests/contract/ci/test_wrapper_contract.py tests/integration/test_runner_image_mode_smoke.py`

## 3) Tagging and compatibility policy

- Publish immutable tags: `v1.x.y`, `sha-<commit>`.
- Move `v1` to latest stable `v1.x.y`; move `latest` to latest stable release.
- Verify the image embeds compatible `uqo-core` `1.x.y` CLI contracts before promoting moving tags.

## 4) Security and maintenance

- Run vulnerability scan on release candidate image; block release on critical vulnerabilities unless exception is approved.
- Record base image reference and planned refresh date (monthly cadence minimum).
- Keep an auditable changelog entry for image digest and embedded `uqo-core` version.

## 5) Performance evidence

- Collect legacy and image-path metrics into `artifacts/legacy.json` and `artifacts/image.json`.
- `python3 scripts/ci/compare_runner_latency.py --baseline artifacts/legacy.json --candidate artifacts/image.json --max-startup-regression 0 --min-e2e-improvement-pct 20`

## 6) Final pass criteria

- All commands exit `0`.
- Image-mode execution avoids runtime `pip install -r requirements.txt`.
- CI wrappers (`ariel-evn/uqo-action` and GitLab include template) document runner-image controls and fallback behavior.
- Image pull/auth/network errors are reported as infrastructure failures (`exit_code=3`).
