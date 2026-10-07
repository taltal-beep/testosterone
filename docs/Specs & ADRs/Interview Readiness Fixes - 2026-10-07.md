---
type: spec
status: current
created: 2026-10-07
updated: 2026-10-07
---

# Interview Readiness Fixes - 2026-10-07

## Context

A review of the repo and the live Pages demo, done as a reader would see them in an interview, found a list of bugs and rough edges: the resolver dropped `junit_xml` and `tier`, the dashboard showed "Degraded" because of a MinIO health check, leftover "UQO" names, Compare was hard to read, the nav broke on phones, and the nightly job was always red. All of it was fixed as one batch of parallel pull requests, each kept independent.

## Decision

| Area | Change | Pull request |
|------|--------|--------------|
| Engine | Keep `junit_xml` and `tier` when resolving cycle stages | [#73](https://github.com/taltal-beep/testosterone/pull/73) |
| Engine | Pyramid buckets a run by the tiers it ran with | [#71](https://github.com/taltal-beep/testosterone/pull/71) |
| Engine | Stage workers are honest per framework | [#77](https://github.com/taltal-beep/testosterone/pull/77) |
| Pytest | Keep the target repo's own rootdir | [#69](https://github.com/taltal-beep/testosterone/pull/69) |
| Storage | Drop MinIO and pre-v1.1 run-history compatibility | [#75](https://github.com/taltal-beep/testosterone/pull/75) |
| Storage | Each run gets its own copy of its artifacts | [#68](https://github.com/taltal-beep/testosterone/pull/68) |
| API | Optional token, strict CORS and origin check | [#76](https://github.com/taltal-beep/testosterone/pull/76) |
| API | Bounded execution registry; async SSE tail | [#81](https://github.com/taltal-beep/testosterone/pull/81) |
| CLI | `uqo` alias and legacy frontend redirects removed | [#72](https://github.com/taltal-beep/testosterone/pull/72) |
| Naming | UQO → Testosterone rename finished in code and UI (env vars `TESTO_*`) | [#78](https://github.com/taltal-beep/testosterone/pull/78) |
| Frontend | Same-cycle compare; honest health for crashed stages | [#82](https://github.com/taltal-beep/testosterone/pull/82) |
| Frontend | Runs named by cycle and time; Compare as tables | [#85](https://github.com/taltal-beep/testosterone/pull/85) |
| Frontend | Top nav collapses into a menu on phones | [#83](https://github.com/taltal-beep/testosterone/pull/83) |
| Demo | Self-hosting CI publishes the UI to GitHub and GitLab Pages | [#67](https://github.com/taltal-beep/testosterone/pull/67) |
| Demo | The read-only Pages demo explains itself | [#84](https://github.com/taltal-beep/testosterone/pull/84) |
| CI | Coverage enforced on the fast suite; nightly fixed | [#79](https://github.com/taltal-beep/testosterone/pull/79) |
| Repo | Dead code and failure injection deleted; root tidied | [#80](https://github.com/taltal-beep/testosterone/pull/80) |
| Docs | Vault readable on GitHub; work log archived | [#74](https://github.com/taltal-beep/testosterone/pull/74) |
| Docs | README top section with demo link and architecture diagram | [#70](https://github.com/taltal-beep/testosterone/pull/70) |

Defaults chosen: the next version is v1.1.0, with a moving `v1` tag for the GitHub Action; no backward-compatibility shims, since there are no external users.

## Consequences

- Breaking for anyone on 1.0: the `uqo` command, `UQO_*` env vars, MinIO storage and pre-v1.1 history are gone. See [CHANGELOG.md](../../CHANGELOG.md).
- A second wave follows: mypy for `testo_api`, a silent-`except` audit, root-module regrouping, the v1.1.0 release and fresh screenshots.
