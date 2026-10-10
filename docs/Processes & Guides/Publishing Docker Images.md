---
type: guide
status: current
created: 2026-07-01
updated: 2026-10-07
---

# Publishing Docker Images

[Index](../Index.md) · [Publishing to PyPI](Publishing%20to%20PyPI.md) · [Publishing to Artifactory](Publishing%20to%20Artifactory.md)

> **Last updated:** 2026-06-25

## Overview

The `testo-runner` Docker image is published to GitHub Container Registry (GHCR) via GitHub Actions. Images are built for `linux/amd64` and `linux/arm64` and scanned with Trivy before publishing.

## Registry

- **Registry**: `ghcr.io`
- **Image**: `ghcr.io/taltal-beep/testo-runner`
- **Auth**: Uses `GITHUB_TOKEN` (automatic for public repos, no additional secrets needed)

## Publishing flow

1. Create a GitHub Release with a semver tag (e.g. `v1.0.0`).
2. The `docker-publish.yml` workflow triggers automatically:
   - Scans `Dockerfile.testo-runner` with Trivy for configuration issues.
   - Builds multi-arch image (`linux/amd64`, `linux/arm64`) via Docker Buildx.
   - Tags with: semver (`1.0.0`), major.minor (`1.0`), major (`1`), commit SHA, and `latest`.
   - Pushes to GHCR.
   - Scans the published image with Trivy for critical vulnerabilities.
   - Verifies the image runs `testo run --help` successfully.

## Tagging strategy

| Tag pattern | Example | When applied |
|-------------|---------|--------------|
| Full semver | `1.0.0` | Every release |
| Major.minor | `1.0` | Every release (floating) |
| Major | `1` | Every release (floating) |
| Commit SHA | `03043a2b` | Every release |
| `latest` | `latest` | Default branch releases only |

## Pulling the image

```bash
docker pull ghcr.io/taltal-beep/testo-runner:latest
docker run --rm ghcr.io/taltal-beep/testo-runner:latest run --help
```

## Using in CI

```yaml
# GitHub Actions
- name: Run tests
  run: |
    docker run --rm \
      -v ${{ github.workspace }}:/workspace \
      ghcr.io/taltal-beep/testo-runner:1.0.0 \
      run --cycle smoke --ci

# docker-compose.yml (override)
services:
  runner:
    image: ghcr.io/taltal-beep/testo-runner:1.0.0
```

## Troubleshooting

- **Trivy blocks the build**: Fix the reported vulnerabilities or update the base image. Critical and high severity issues block Dockerfile scan; only critical issues block the published image scan.
- **Multi-arch build fails**: Ensure QEMU is set up correctly (the workflow handles this with `docker/setup-qemu-action`).
- **Image pull fails**: For private repos, authenticate with `docker login ghcr.io -u <username> --password-stdin` using a PAT with `read:packages` scope.

## Related

- [Publishing to PyPI](Publishing%20to%20PyPI.md) — Python package publishing
- [CI-CD Pipeline Setup](CI-CD%20Pipeline%20Setup.md) — CI workflow overview
- Workflow file: `.github/workflows/docker-publish.yml`
- Dockerfile: `Dockerfile.testo-runner`
