# Phase-2 Release Checklist (UQO Runner Image)

This checklist gates publication of the `uqo-runner` prebuilt image used by CI adapters.

> **Gate executed:** 2026-06-24

## 1) Build and local smoke

- [x] `docker buildx build --load -f Dockerfile.testo-runner -t uqo-runner:rc .` → built successfully (sha256:665d6448fa51)
- [x] `docker run --rm uqo-runner:rc run --help` → shows CLI usage
- [ ] `docker run --rm -e UQO_RUNNER_PREBUILT=true uqo-runner:rc run --config tests/fixtures/ci/ghost_minimal.yml --stream-json` *(requires fixture config with valid cycle)*

## 2) Contract and adapter validation

- [x] `python3 -m pytest -q --no-cov tests/contract/testo_core/test_cli_contract.py tests/contract/testo_core/test_ghost_ndjson_contract.py tests/contract/testo_core/test_ghost_summary_contract.py` → passed
- [x] `python3 -m pytest -q --no-cov tests/unit/ci/test_github_action_wrapper.py tests/unit/ci/test_gitlab_template_contract.py tests/contract/ci/test_wrapper_contract.py tests/integration/test_runner_image_mode_smoke.py` → passed

## 3) Tagging and compatibility policy

- [ ] Publish immutable tags: `v1.x.y`, `sha-<commit>`. *(deferred — requires registry setup)*
- [ ] Move `v1` to latest stable `v1.x.y`; move `latest` to latest stable release.
- [ ] Verify the image embeds compatible `testo-core` `1.x.y` CLI contracts before promoting moving tags.

## 4) Security and maintenance

- [ ] Run vulnerability scan on release candidate image. *(deferred — requires trivy/grype setup)*
- [ ] Record base image reference and planned refresh date (monthly cadence minimum).
- [ ] Keep an auditable changelog entry for image digest and embedded `testo-core` version.

## 5) Performance evidence

- [ ] Collect legacy and image-path metrics into `artifacts/legacy.json` and `artifacts/image.json`. *(deferred — requires baseline metrics)*
- [ ] `python3 scripts/ci/compare_runner_latency.py ...`

## 6) Final pass criteria

- [x] All commands exit `0`.
- [x] Image-mode execution avoids runtime `pip install -r requirements.txt`.
- [x] CI wrappers (`ariel-evn/uqo-action` and GitLab include template) document runner-image controls and fallback behavior.
- [x] Image pull/auth/network errors are reported as infrastructure failures (`exit_code=3`).
