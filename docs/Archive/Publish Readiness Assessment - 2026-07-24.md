---
last-updated: 2026-07-24
---
# Publish Readiness Assessment — 2026-07-24

[Index](../Index.md) · [Product Roadmap](../Roadmap%20&%20Strategy/Product%20Roadmap.md) · [V1 Release Roadmap](V1%20Release%20Roadmap.md) · [Project Audit - 2026-06-24](Project%20Audit%20-%202026-06-24.md)

> **Purpose:** Point-in-time answer to "what is left to make `testo-core` complete enough to publish?"
> **Scope:** Verified against live repo state on 2026-07-24 (code, workflows, checklists, `pyproject.toml`, git), not against the older [Project Audit - 2026-06-24](Project%20Audit%20-%202026-06-24.md) narrative.
> **Headline:** The project is **feature-complete and release-infrastructure-complete**. It is **not yet released**: version is still `0.1.0`, there is no `v1.0.0` tag, no GitHub Release, and nothing on PyPI. The remaining work is a short, mostly-operational **"pull the trigger"** list plus two optional cleanups.

---

## TL;DR — the short list to publish

| # | Blocker | Type | Effort |
|---|---------|------|--------|
| 1 | Bump `version` `0.1.0` → `1.0.0` in `pyproject.toml` | Code | XS |
| 2 | Finalize the `[Unreleased]` → `[1.0.0]` CHANGELOG section | Docs | XS |
| 3 | Configure PyPI **trusted publisher (OIDC)** + GitHub `test-pypi` / `pypi` environments | Infra/settings | S |
| 4 | Configure GHCR permissions for `docker-publish.yml` | Infra/settings | XS |
| 5 | Create git tag `v1.0.0` + GitHub Release (this **fires** `publish.yml` and `docker-publish.yml`) | Release action | S |
| 6 | Verify `pip install testo-core==1.0.0` and the published runner image work end-to-end | Verification | S |

Everything below the line is either **already done**, **deferred-by-design** (external environments), or **optional and non-blocking** (Streamlit removal, exception-handling hardening).

**Estimate to a published v1.0.0: ~0.5–1 working day** of active work, gated mostly on repo-settings access (PyPI trusted publisher, GitHub environments, GHCR).

---

## What changed since the 2026-06-24 audit

The [Project Audit - 2026-06-24](Project%20Audit%20-%202026-06-24.md) listed the big blockers as: 16 unmerged draft PRs, 0/210 release gates checked, missing persistence module, no CHANGELOG, no publish pipelines. **Most of these are now resolved.**

| Audit blocker | Status on 2026-07-24 | Evidence |
|---------------|----------------------|----------|
| Persistence module missing (`orchestrator.py:228`) | ✅ **Done** | `testo_core/persistence/` exists: `backend.py`, `json_backend.py`, `db_backend.py`, `composite.py`, `health.py` |
| Dual execution stacks / duplicate `EngineExitCode` | ✅ **Done** | `classify_exit_code` consolidated into `engine/exit_codes.py`; contract tests assert cross-stack parity (per CHANGELOG `[Unreleased]`) |
| No CHANGELOG | ✅ **Done** | `CHANGELOG.md` at root, populated `[Unreleased]`, Keep-a-Changelog format, CI-enforced |
| No PyPI publish pipeline | ✅ **Done (not fired)** | `.github/workflows/publish.yml` — release-triggered, OIDC, Test PyPI dry-run → PyPI |
| No Docker image publish pipeline | ✅ **Done (not fired)** | `.github/workflows/docker-publish.yml` — release-triggered, pushes to GHCR (`testo-runner`) |
| Release gates 0/210 | ✅ **Largely done** — 187/210, remainder mostly deferred/release-time (see below) | `grep` of `docs/Release Management/*` |
| 16 draft PRs blocking | ✅ **Cleared** | No open drafts detected; critical fixes reflected in CHANGELOG (`#35` redaction/failure-context, persistence, exit codes) |

The 2026-06-24 audit's "~10–15 working days to v1.0" estimate is **stale**. Nearly all of Sprints 1–4 in the [V1 Release Roadmap](V1%20Release%20Roadmap.md) have landed.

---

## Release gate status (live)

Verified by counting `- [x]` vs `- [ ]` across `docs/Release Management/`.

| Checklist | Done | Remaining | Nature of remaining items |
|-----------|------|-----------|---------------------------|
| Phase 1 Foundation | 25 | 2 | Optional MySQL driver install — *"not required in this environment"* |
| Phase 2 CI Integrations | 26 | 10 | External repo/action setup (`ariel-evn/uqo-action`), release-time tag moves (`v1.0.0`/`v1`), Docker-in-test wiring, external nightly gate |
| Phase 2 Ghost Mode | 17 | 1 | Needs a valid fixture cycle config |
| Phase 2 Runner Image | 8 | 9 | Registry setup, tag promotion, trivy/grype scan, baseline latency metrics — mostly deferred infra |
| Phase 3 Delta Engine | 23 | 0 | ✅ Complete |
| Phase 3 Frontend Migration | 24 | 0 | ✅ Complete |
| Phase 3 Unified Dashboard | 34 | 0 | ✅ Complete |
| Phase 4 AI & Failure Analysis | 30 | 1 | Live-provider misconfig/timeout paths — *covered by unit-test mocks* |
| **Total** | **187** | **23** | — |

**Reading of the remaining 23:** none are code-completeness gaps. They split into three buckets:

1. **Release-time actions** — creating/moving `v1.0.0` / `v1` / `latest` tags, publishing image digests. These *are* the release; they get checked off when we ship (blockers #5–#6 above).
2. **External-environment gated** — external action repo access, container registry setup, trivy scanning, Docker-in-test env wiring, baseline latency artifacts. Deferrable past a first public release.
3. **Explicitly marked optional/covered** — MySQL driver, live-provider error paths (mock-covered).

---

## Publish pipeline readiness

Both workflows exist and are well-formed; they simply have **never fired** because there is no GitHub Release yet.

### `publish.yml` (PyPI)
- Trigger: `release: [published]`.
- Uses **OIDC trusted publishing** (`id-token: write`) — no long-lived API token in secrets. ✅ Best practice.
- Two-stage: `test-pypi` environment (dry-run publish + verify install) → then real PyPI.
- **Action required before first run:** register `testo-core` on PyPI, configure the **trusted publisher** for this repo/workflow, and create the GitHub Actions **environments** `test-pypi` and `pypi`. Without these, the first release run fails at the publish step. See [Publishing to PyPI](../Processes%20&%20Guides/Publishing%20to%20PyPI.md).

### `docker-publish.yml` (GHCR)
- Trigger: `release: [published]`.
- Registry: `ghcr.io/<owner>/testo-runner`.
- **Action required:** ensure the repo has `packages: write` / GHCR publishing enabled for the release job. See [Publishing Docker Images](../Processes%20&%20Guides/Publishing%20Docker%20Images.md).

---

## Confirmed done (do not re-do)

- **Engine & adapters** — config → resolver → orchestrator → executor; pytest / Behave / BehaveX adapters. Mature.
- **Persistence module** — `PersistenceBackend` protocol with JSON + DB + composite backends and a health surface. (Was the audit's top "High" architecture gap.)
- **Single-sourced exit codes** — legacy and modern stacks agree; contract-tested.
- **Reporting** — Allure 3, Extent, ReportPortal, TestBeats; test-pyramid wired into `testo report pyramid RUN_ID` (2026-07-23, see [CLI-UI Parity - Pyramid, Graphs, Deep Diff - 2026-07-23](CLI-UI%20Parity%20-%20Pyramid,%20Graphs,%20Deep%20Diff%20-%202026-07-23.md)).
- **Deep diff** — per-stage / per-test `testo diff` gap closed (git log `d006c7ab`).
- **API + Frontend** — FastAPI (SSE, dashboard, analytics/delta, AI) + React (Dashboard, Execution, Runner Console, History, Run Detail, Compare, AI Settings). Phase 3 gates 100%.
- **CI/CD** — `ci.yml` (format/test/deploy), `commitlint.yml`, `changelog-on-main.yml`, `pr-heavy.yml`, `release-gate.yml`, `nightly-external.yml`. Changelog + Conventional Commits enforced. See [Changelog Automation and CI Enforcement Policy](Changelog%20Automation%20and%20CI%20Enforcement%20Policy.md).
- **Repo hygiene** — `CONTRIBUTING.md`, PR/issue templates, `CODEOWNERS`, `LICENSE`, root `CLAUDE.md`, `.pre-commit-config.yaml`, mypy config.

---

## Optional / non-blocking (can ship v1.0 without)

These improve quality but are **not** publish blockers. Track post-tag if time-boxed.

### 1. Streamlit legacy removal — *not done* (Workstream 9)
Still present and shipped: `testo_ui/` directory, `testo-ui = "testo_ui.entry:main"` entrypoint, and `streamlit>=1.36.0` dependency in `pyproject.toml`. React frontend is the official UI (Phase 3 gates all green), so the Streamlit surface is redundant. **Decision needed:** deprecate-and-keep for v1.0, or remove entrypoint + `[ui]` extra before tagging to shrink the install surface. Recommend at least a deprecation warning before v1.0; full removal can follow in v1.1. See [Streamlit to React Migration Guide](Streamlit%20to%20React%20Migration%20Guide.md).

### 2. Exception-handling hardening — *not verified done* (Workstream 5)
Broad `except Exception` in Docker/S3/reporter paths risks silent degradation. Quality hardening, not a correctness blocker for a first release.

### 3. Deferred external-environment gates
External action repo (`ariel-evn/uqo-action`), trivy/grype image scanning, baseline latency comparison, Docker-in-test wiring. Safe to complete after the initial publish.

---

## Recommended path to publish (ordered)

1. **Decide Streamlit** — add deprecation warning (min) or remove entrypoint + `streamlit` extra (clean). Non-blocking either way.
2. **Bump version** to `1.0.0` in `pyproject.toml`.
3. **Roll CHANGELOG** `[Unreleased]` → `## [1.0.0] - 2026-XX-XX`.
4. **Provision publish auth** — PyPI trusted publisher + `test-pypi`/`pypi` GitHub environments; confirm GHCR `packages: write`.
5. **Tag & release** — create `v1.0.0`, publish a GitHub Release with changelog notes. This fires `publish.yml` and `docker-publish.yml`.
6. **Verify end-to-end** — `pip install testo-core==1.0.0` → `testo --version`; pull `ghcr.io/<owner>/testo-runner` → `run --help`.
7. **Check off** the release-time items in Phase 2 CI / Runner Image checklists; move `v1` / `latest` tags.
8. **Announce** — README badge + Release notes.

Corresponds to [V1 Release Roadmap](V1%20Release%20Roadmap.md) Workstreams 6–10; Workstreams 1–4 are effectively complete, 5 & 9 are optional.

---

## Verification method (for reproducibility)

- `grep -c '\- \[x\]' / '\- \[ \]'` across `docs/Release Management/*.md` for gate counts.
- `ls .github/workflows/` and head of `publish.yml` / `docker-publish.yml` for pipeline presence + triggers.
- `grep '^version' pyproject.toml`, `git tag`, `pip3 index versions testo-core` for release state.
- `ls testo_core/persistence/`, `grep streamlit pyproject.toml` for module/cleanup status.
- `git log --oneline` on `main` for recently landed work.

---

## Related notes

- [V1 Release Roadmap](V1%20Release%20Roadmap.md) — full 110-task breakdown (Workstreams 1–4 now largely complete)
- [Project Audit - 2026-06-24](Project%20Audit%20-%202026-06-24.md) — prior snapshot this assessment supersedes
- [Product Roadmap](../Roadmap%20&%20Strategy/Product%20Roadmap.md) — phase delivery narrative
- [Publishing to PyPI](../Processes%20&%20Guides/Publishing%20to%20PyPI.md) · [Publishing Docker Images](../Processes%20&%20Guides/Publishing%20Docker%20Images.md) — release infra guides
- [Release Management](Release%20Management%20Hub.md) — gate hub
- [Technical Debt Tracker](../Testing%20Workflows/Technical%20Debt%20Tracker.md) — remaining hardening items (Workstream 5)
