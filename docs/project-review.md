---
type: reference
status: current
created: 2026-10-24
updated: 2026-10-24
---

# Project review: scorecard and verdict

[Index](Index.md)

Two passes over the whole repo with the tech-debt, code-review, security-review and architecture checklists (the first pass also used testing-strategy). The **second pass** is `main` at `3aeb3b3` (2026-10-24), after the fixes from the first; the first pass was `f1e3521` the same morning, and its findings are kept below with their status. Open items that should outlive this note move to the [Technical Debt Tracker](Testing%20Workflows/Technical%20Debt%20Tracker.md).

## Verdict

**Overall: 8.5 / 10 (was 8).** Every Medium and Low finding from the first pass that needed code is fixed and merged: open reads no longer load arbitrary files, a public bind without a token refuses to start, the team server can protect reads behind a `/login` cookie, actions are pinned, CI tests Python 3.11 to 3.13, the frontend has ESLint and is on Vite 8 with zero `npm audit` advisories, dead code and the mascot are out of the wheel, and coverage went from 79% to 84%. v1.2.0 is released on GitHub. The architecture did not need to change, which is the best evidence for it: the security and auth work went in as one module and one middleware, with no second path.

What keeps it from a 9 is no longer correctness or security but scale and housekeeping: the API runs each execution on its own thread with in-memory state (A1), stages run one at a time (A2), a few 500+ line modules, the Allure and Behave reporting paths are still under 50% covered, and a queue of nine Dependabot pull requests plus a contributor's PR (#124) wait for review. None of that blocks using or showing the project.

## Scorecard

| Area | Score | Was | In one line |
|------|:-----:|:---:|-------------|
| Architecture | **8.5** | 8.5 | One engine, one service entry point, plugins, a read-side `history/`; auth added as a module and a middleware without a second path. Thread-per-run API and sequential stages are the limits |
| Code quality | **8.5** | 8 | `ruff`, `ruff format` and `mypy` clean in CI, ESLint on the frontend, no dead Streamlit code, no `TODO`s; four modules over 500 lines |
| Tests | **8** | 7 | 865 fast tests at 84% coverage on Python 3.11, 3.12 and 3.13, 58 frontend tests including the Compare and Run Detail states; Allure, Behave and `testo watch` paths are thin |
| Security | **8.5** | 7 | Config file allow-list on reads, fail-closed public bind, optional protected reads with an HttpOnly `SameSite=Strict` cookie, pinned actions and least-privilege tokens; a few Low items left |
| Docs | **9** | 9 | Linted vault, ADRs, a security model that matches the code, guides updated in the same pull request as each change |
| CI / DX | **9** | 8 | Python matrix, ESLint, OpenAPI and schema drift checks, image scan, team server smoke that exercises the login flow, 0 `npm audit` and `pip-audit` findings |
| Tech debt | **8** | 7 | Release cut, dead code and mascot gone, frontend toolchain current; a Dependabot backlog and TypeScript 7 (blocked upstream) remain |

## What was checked (second pass)

| Check | Result |
|-------|--------|
| `ruff check .` and `ruff format --check .` | Clean (431 files) |
| `mypy testo_core testo_api` | Clean in CI on all three Python versions |
| `pytest -m "tier_fast and not quarantined"` | 865 passed, 84.3% coverage (gate 65%). The 2 local failures are the review machine (no `build` module, `pytest` not on `PATH`); the same tests pass in CI |
| Frontend | `tsc`, ESLint, 58 Vitest tests and the Vite 8 build pass; `npm audit` 0 (was 6) |
| `pip-audit` | Nothing in the project's dependencies |
| `vulture --min-confidence 80` | Nothing (was 2 unused variables and the dead report helpers) |
| Team server login | `TESTO_PROTECT_READS=1` checked end to end: 401 without a session, redirect to `/login`, bearer and cookie reads, health open; open-redirect attempts (`//host`, `/\host`, tab-prefixed) stay on the server |
| Open pull requests | 9 from Dependabot (#132 to #140) and #106 (TypeScript 7, blocked by `typescript-eslint`), plus #124 from a contributor |

## Second-pass findings

New since the first pass, all Low, most severe first. None is a blocker.

| # | Severity | Finding | Fix |
|---|----------|---------|-----|
| S6 | Low | **Protected reads are only on in the compose file.** The `testo-server` image itself does not set `TESTO_PROTECT_READS`, so `docker run -e TESTO_API_TOKEN=... testo-server` serves runs, logs and reports to anyone who can reach it | Set `TESTO_PROTECT_READS=1` in `Dockerfile.testo-server` so the image is safe by default, as the compose file already is |
| S7 | Low | **Sessions are stateless.** The cookie is an HMAC of the token, so sign-out only clears the browser's copy; a copied cookie works until the token changes, for up to 30 days | Acceptable with one shared token; document "rotate the token to sign everyone out", or add a server-side session list if per-user accounts arrive |
| S8 | Info | **No rate limit on `/login`.** A guessed token is the only way in, and the guides tell people to use `openssl rand -hex 32`, so online guessing is not practical | Nothing now; a reverse proxy can rate-limit if needed |
| S5 | Low | **AI `base_url` is free-form** (open from the first pass). A write token can point the provider at any URL, and the key goes there | One sentence in the security model |
| T5 | Test | Lowest-covered modules: `reporting/allure.py` 32%, `reporting/server.py` 37%, `frameworks/behave_adapter.py` 45%, `reporting/behavex_allure.py` 48%, `cli/commands/watch.py` 48% | Tests for the Allure CLI fallbacks and the Behave adapter's argument building |
| D8 | Dependency | Nine Dependabot pull requests (#132 to #140) are open, including `actions/setup-python` 7 and `@testing-library/jest-dom` 7 (a major bump), and #105 is superseded by the merged Vite 8 upgrade | Review and merge the green ones; close #105 |
| D9 | Process | Contributor PR #124 has waited since 2026-10-21 for a merge from `main` | Nudge or take it over with credit |

## First pass (f1e3521): findings and status

### What was checked (first pass)

| Check | Result |
|-------|--------|
| `ruff check .` and `ruff format --check .` | Clean (425 files) |
| `mypy testo_core testo_api` | Clean, also in a fresh Python 3.13 venv with the latest `sqlmodel` (0.0.48). An earlier run showed 2 errors in `repository/models.py`; that came from stale packages in the review machine's global environment, not from the code |
| `python scripts/docs_vault.py lint` | ok |
| `pytest -m "tier_fast and not quarantined"` | 813 passed, 4 failed, 79.4% coverage. All 4 failures were the review machine: no `build` module, the `bdd` extra failed to install, and one test that expects `pytest` next to `sys.executable` |
| `npm audit` (frontend) | 0 in production dependencies; 6 in dev tooling (Vitest, esbuild, tinypool) |
| `pip-audit` | Nothing in the project's own dependencies |
| `vulture --min-confidence 80` | 2 unused variables; manual check found unused functions in `reporting/report_generator.py` (see D1) |

### Architecture

The design matches [ARCHITECTURE.md](../ARCHITECTURE.md) and the [Architecture Overview](Architecture/Architecture%20Overview.md): `config/loader.py` → `config/resolver.py` → `engine/orchestrator.run_plan()` → `engine/executor.run_stage()`, with both the CLI and the API going through `services/cycle_run.CycleRunService` (the only caller of `run_plan`). Ingest reuses the same service through `equipment: junit`, so uploaded results get the same history, Compare, flaky detection and reporters as real runs. That is the strongest part of the project: features added in October (ingest, team server, quarantine, alerts, Playwright JSON) slotted in without a second path.

Strengths

- Framework adapters behind a small protocol (`frameworks/base.py`), and third-party runners and reporters through entry points (`plugins.py`), so new runners need no core change.
- Storage behind `persistence/` and `repository/`, reads behind `history/`, SQLite by default and Postgres for the team server.
- Exit codes single-sourced in `engine/exit_codes.py` and locked by contract tests.
- The frontend's API types are generated from OpenAPI and CI fails when they drift.

Risks to watch

- **A1. Thread-per-run API.** *Still open.* `testo_api/cycle_execution_manager.py` starts a daemon thread per execution and keeps state in memory. One run per cycle is enforced, which is right, but there is no global cap on concurrent runs and a restart loses live state (orphans are cleaned up on startup). Fine for a local tool and a small team server; a queue would be the next step if the server grows.
- **A2. Sequential stages.** *Still open.* Already tracked as item 3 in the [Technical Debt Tracker](Testing%20Workflows/Technical%20Debt%20Tracker.md).
- **A3. Version hard-coded twice.** *Fixed (#141).* `testo_api/main.py` sets `version="1.1.1"` by hand next to `pyproject.toml`. Read it from `importlib.metadata` so a release can't leave the API reporting an old version.

### Security

The model in [ARCHITECTURE.md § Security model](../ARCHITECTURE.md#security-model) is sound and the code follows it: loopback by default, foreign-origin writes refused even without a token (which stops simple cross-site POSTs and DNS rebinding), `hmac.compare_digest` for the token, upload size limits, sanitised upload filenames, Playwright attachments confined to the report root, secret redaction before AI calls, and the team server's compose file refuses to start without `TESTO_API_TOKEN`. No workflow uses `pull_request_target`, and 10 of 13 set explicit `permissions:` (see S4).

Findings, most severe first

| # | Severity | Finding | Fix | Status |
|---|----------|---------|-----|--------|
| S1 | Medium | **Open reads take an arbitrary file path.** `GET /api/v1/cycles`, `GET /api/v1/cycles/{cycle}` and `GET /api/v1/runs/{run_id}/pyramid` accept `?config_path=` and load it. Reads need no token even when `TESTO_API_TOKEN` is set, so anyone who can reach a team server can probe whether any file exists and see fragments of non-YAML files in the error message (checked: `config_path=/root/.bashrc` returns a line of the file in the YAML parse error) | Drop `config_path` from GET routes, or restrict it to files under the configured project root, and return a generic error message | Fixed (#141) |
| S2 | Medium | **Public bind without a token only warns.** `testo-api` on a non-loopback host with no `TESTO_API_TOKEN` logs a warning and starts, and the `testo-server` image binds `0.0.0.0`. A plain `docker run -p 8000:8000 testo-server` exposes "start a run", which runs commands, to the network | Refuse to start in that case unless an explicit `TESTO_ALLOW_UNAUTHENTICATED=1` is set | Fixed (#141) |
| S3 | Low | **Reads and `/history` are open on the team server.** Run logs and report files can carry secrets printed by tests. Documented in the [Team Server](Processes%20&%20Guides/Team%20Server.md) guide, but there is no switch to protect them | Add an opt-in `TESTO_API_READ_TOKEN` (or require the token for reads when set) | Fixed (#147) |
| S4 | Low | **Floating action refs and default token scope.** `aquasecurity/trivy-action@master` and `anthropics/claude-code-base-action@beta` run in the Docker publish and changelog-on-main workflows, and `commitlint.yml`, `pr-heavy.yml` and `release-gate.yml` have no `permissions:` block, so they get the repository's default token scope. A compromised upstream branch would run with those jobs' secrets | Pin the two actions to a release tag or commit SHA (Dependabot already watches `github-actions`) and add `permissions: contents: read` to the three workflows | Fixed (#141) |
| S5 | Low | **AI `base_url` is free-form.** With a write token, the AI settings page can point the provider at any URL and the server will send the key there. Acceptable for a self-hosted tool; worth a sentence in the security model | Document it, optionally allow-list schemes and hosts | Open |

XML from uploads is parsed with the standard library's `ElementTree`, which on Python 3.11+ does not resolve external entities and has expat's entity-expansion limits, and uploads are size-capped, so XXE and billion-laughs are not a concern.

### Code quality and tech debt

Prioritised with the tech-debt formula, priority = (impact + risk) × (6 − effort), each scored 1 to 5.

| # | Item | Type | Impact | Risk | Effort | Priority | Status |
|---|------|------|:------:|:----:|:------:|:--------:|--------|
| S1 | `config_path` on open GET routes | Security | 2 | 4 | 1 | **30** | Fixed (#141) |
| S2 | Public bind without token is fail-open | Security | 2 | 4 | 1 | **30** | Fixed (#141) |
| D2 | Large unreleased backlog: `CHANGELOG.md [Unreleased]` holds ingest, the team server, Playwright JSON, quarantine, alerts, the config schema, the plugin API and a breaking extras change. PyPI users are on 1.1.1 | Release | 4 | 3 | 2 | **28** | Released as v1.2.0 (PyPI upload awaiting approval) |
| D1 | Streamlit-era dead code in `reporting/report_generator.py`: `sync_all_reports_to_static`, `start_report_server`, `start_static_server`, `collect_behavex_native_report` and `url_for` have no caller in `testo_core/` or `testo_api/`, and six comments still mention Streamlit, which was removed in v1.1 | Code | 3 | 2 | 1 | **25** | Fixed (#141) |
| D3 | No Python version matrix: classifiers claim 3.12 and 3.13, CI runs only 3.11 | Infrastructure | 2 | 3 | 1 | **25** | Fixed (#141) |
| T1 | Thin coverage where users plug in: TestBeats reporter 18%, `cli/commands/config.py` 19%, ReportPortal reporter 26%, Anthropic provider 30%, `cli/commands/report.py` 39% | Test | 3 | 3 | 3 | **18** | Fixed (#143) |
| D4 | No Python lock or constraints file, only lower bounds, so CI resolves the newest dependencies on every run and an upstream release can turn `main` red with no change here. Normal for a library; checked that today's latest versions pass `mypy` and the suite on 3.12 and 3.13 | Dependency | 1 | 2 | 2 | **12** | Accepted |
| D5 | Frontend dependency debt: Dependabot PRs for Vite 8 (#105) and TypeScript 7 (#106) break the build; dev tooling has 6 `npm audit` advisories | Dependency | 2 | 2 | 3 | **12** | Vite 8 done (#146); TypeScript 7 blocked upstream |
| D6 | `testo_core/mascot/` (422 lines, 0% coverage) ships inside the core package for a UI animation | Code | 1 | 1 | 2 | **8** | Fixed (#148) |
| D7 | No frontend linter (ESLint or Biome); `tsc` is the only static check | Infrastructure | 1 | 2 | 2 | **12** | Fixed (#144) |

Good habits worth keeping: no `TODO` or `FIXME` markers in the Python packages, every broad `except Exception` has a comment saying why, 14 `type: ignore`s across ~20k lines, and functions are small with a few exceptions (`config/loader.py`, `reporting/report_generator.py`, `cli/commands/report.py` and `testo_api/cycle_execution_manager.py` are each 500+ lines).

### Tests

The suite is a pyramid in the right shape: 102 unit files, 19 contract files (exit codes, CI tiers, packaging, OpenAPI), 7 integration and 3 end-to-end, with tiers and a quarantine marker. The fast tier runs in about 16 seconds, which keeps it on every pull request, and coverage is 79% against a 65% gate. The project also tests itself through its own GitHub Action and the fake-api demo, which is a strong signal.

Gaps

- **T1** above: reporters and CLI report commands are where outside users integrate, and they are the least covered.
- **T2.** *Fixed (#145).* The frontend has 17 test files for ~8k lines of TypeScript. The Compare and Run Detail pages carry the product's main story and deserve component tests for their empty, error and loading states.
- **T3.** *Fixed (#141).* A few tests assume the machine: `test_target_inside_another_pytest_project_keeps_its_own_rootdir` expects `pytest` next to `sys.executable`, and the packaging contract needs `build`. Skip them with a clear reason when the tool is missing, so a contributor's first local run is green.
- **T4.** *Fixed (#141).* With no 3.12/3.13 job (D3), the version claims in `pyproject.toml` are untested.

### Docs and developer experience

The vault is the project's best interview asset: a linted entry point, ADRs per decision, an architecture document with a security model and known limits, a getting-started guide that CI runs end to end, and a docs site. `CONTRIBUTING.md`, issue and PR templates, `SECURITY.md`, a code of conduct and `CITATION.cff` are all present.

Small gaps: `actionlint_py-1.7.12.25.tar.gz` was committed (*removed in #141*) at the repo root and looks like a stray download, and the README is 333 lines, so a newcomer has to scroll past a lot before the first command.

## What's left

1. **Now (an hour).** S6 (`TESTO_PROTECT_READS=1` in the server image), S5 and S7 (two sentences in the security model), close Dependabot #105, approve the v1.2.0 PyPI upload.
2. **Soon.** D8 (merge the green Dependabot pull requests), D9 (contributor PR #124), T5 (Allure and Behave coverage).
3. **When the team server grows.** A1 (a run queue with a concurrency cap and persistent state), A2 (opt-in parallel stages, tracker item 3), TypeScript 7 once `typescript-eslint` supports it.

The first pass's three-phase plan is done; its steps are in the Progress log below.

## Progress

- 2026-10-24, step 1 done in the same pull request as this note: S1 (read routes only load config file names), S2 (public bind without a token refuses to start), S4 (actions pinned to SHAs, read-only `permissions:`), A3 (API version from package metadata), D1 (dead report helpers and the stray tarball removed).
- 2026-10-24, step 2 in the same pull request: D3 (a `test (python 3.12/3.13)` CI job, suite green on both in clean venvs) and T3 (the rootdir test finds `pytest` on `PATH` when it is not next to the interpreter; BehaveX tests skip without the `bdd` extra). D4 re-scored after a clean-venv check. The release (D2) waits on Taltal.
- 2026-10-24, step 3 as separate pull requests: T1 reporter, provider and CLI tests (#143), D7 frontend ESLint (#144), T2 frontend state tests (#145), D5 Vite 8 and Vitest 5 (#146; TypeScript 7 waits on `typescript-eslint`). S3: Taltal chose a cookie login over a read token, so `TESTO_PROTECT_READS=1` makes every read need the token or the `/login` session cookie (the team server compose file turns it on); see the [Team Server](Processes%20&%20Guides/Team%20Server.md) guide.
- 2026-10-24: D6 done, the mascot moved to `scripts/mascot/` and out of the wheel.
- 2026-10-24, second pass at `3aeb3b3`: overall 8 → 8.5; new findings S6 to S8, T5, D8 and D9.
- 2026-10-24: S6 fixed (the server image sets `TESTO_PROTECT_READS=1`), S5 and S7 documented in the ARCHITECTURE security model.
