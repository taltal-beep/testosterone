# Publishing to PyPI

[Index](../Index.md) · [Publishing Docker Images](Publishing%20Docker%20Images.md) · [Publishing to Artifactory](Publishing%20to%20Artifactory.md)

> **Last updated:** 2026-06-25

## Overview

`testo-core` is published to PyPI via GitHub Actions using trusted publishing (OIDC). No API tokens are stored in repository secrets.

## Prerequisites

1. **PyPI account**: Register at https://pypi.org and claim the `testo-core` package name.
2. **Test PyPI account**: Register at https://test.pypi.org for dry-run validation.
3. **Trusted publisher**: Configure OIDC trusted publishing on both PyPI and Test PyPI:
   - PyPI → "Your projects" → `testo-core` → "Publishing" → "Add a new publisher"
   - Owner: `taltal-beep`
   - Repository: `unified-quality-orchestration-reporting-dashboard`
   - Workflow: `publish.yml`
   - Environment: `pypi` (for PyPI) / `test-pypi` (for Test PyPI)
4. **GitHub environments**: Create `pypi` and `test-pypi` environments in the repository settings. Optionally add required reviewers to the `pypi` environment for release approval.

## Publishing flow

1. Create a GitHub Release with a semver tag (e.g. `v1.0.0`).
2. The `publish.yml` workflow triggers automatically:
   - **Test PyPI job**: builds, checks metadata with `twine check`, publishes to Test PyPI, verifies `pip install` from Test PyPI.
   - **PyPI job** (depends on Test PyPI success): builds, checks, publishes to PyPI, verifies `pip install`.
3. Both jobs use `pypa/gh-action-pypi-publish` with OIDC authentication (no API token needed).

## Version management

- Version is set in `pyproject.toml` under `[project] version`.
- Bump version before creating the release tag.
- The release tag should match the version (e.g. `v1.0.0` → `version = "1.0.0"`).

## Verifying a release

```bash
pip install testo-core==1.0.0
testo --version
testo run --help
```

## Troubleshooting

- **OIDC auth failure**: Verify trusted publisher configuration matches the workflow filename and GitHub environment name exactly.
- **`twine check` failure**: Check `pyproject.toml` for missing metadata fields (`description`, `readme`, `requires-python`).
- **Test PyPI install failure**: Test PyPI may lack transitive dependencies. The workflow uses `--extra-index-url https://pypi.org/simple/` as fallback.
- **Version conflict**: PyPI does not allow re-uploading the same version. Bump the version and create a new release.

## Related

- [CI-CD Pipeline Setup](CI-CD%20Pipeline%20Setup.md) — CI workflow overview
- Workflow file: `.github/workflows/publish.yml`
