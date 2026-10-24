---
type: reference
status: current
created: 2026-10-24
updated: 2026-10-24
---

# Project review: scorecard and verdict

[Index](Index.md)

A whole-repo review of `main` at `f1e3521` (2026-10-24), done with the tech-debt, code-review, security-review, architecture and testing-strategy checklists. The scores are a snapshot of that commit. Open items that should outlive this note move to the [Technical Debt Tracker](Testing%20Workflows/Technical%20Debt%20Tracker.md).

## Verdict

**Overall: 8 / 10.** Testosterone is a well-built, honestly documented tool that reads like the work of a careful team, not a side project. There is one engine, one way in (`CycleRunService`), clear layers, typed and lint-clean Python, a contract test suite that pins exit codes and CI behaviour, and a docs vault that CI keeps honest. What holds it back from a 9 is a handful of fixable things: one real security gap in the API's open reads, a fail-open default when the server binds publicly, dead Streamlit-era code, thin coverage on the reporters and the frontend, and CI that only tests Python 3.11. None of them is hard; most are an afternoon each.

## Scorecard

| Area | Score | In one line |
|------|:-----:|-------------|
| Architecture | **8.5** | One engine, one service entry point, a read-side `history/` package and plugin entry points; the API's thread-per-run manager is the main scaling limit |
| Code quality | **8** | `ruff` and `ruff format` clean across 425 files, `mypy` blocking in CI, deliberate and commented boundary catches; some dead code and a few long modules |
| Tests | **7** | 817 fast tests in ~16 s at 79% line+branch coverage with a 65% gate; reporters, `report` CLI and the frontend are thin, and a few tests depend on the local environment |
| Security | **7** | Thoughtful origin guard, constant-time token check, upload size caps, safe filenames and attachment confinement; open reads accept an arbitrary file path, and a public bind without a token only warns |
| Docs | **9** | Linted Obsidian vault, ADRs per decision, a getting-started path, an architecture doc with a security model and known limits |
| CI / DX | **8** | Tiered CI, generated OpenAPI types checked for drift, schema export check, image scan, docs build `--strict`; no Python version matrix, no frontend linter |
| Tech debt | **7** | The [tracker](Testing%20Workflows/Technical%20Debt%20Tracker.md) is real and current, but a large unreleased `CHANGELOG` backlog and legacy report-sync code add drag |

## What was checked

| Check | Result |
|-------|--------|
| `ruff check .` and `ruff format --check .` | Clean (425 files) |
| `mypy testo_core testo_api` | Clean, also in a fresh Python 3.13 venv with the latest `sqlmodel` (0.0.48). An earlier run showed 2 errors in `repository/models.py`; that came from stale packages in the review machine's global environment, not from the code |
| `python scripts/docs_vault.py lint` | ok |
| `pytest -m "tier_fast and not quarantined"` | 813 passed, 4 failed, 79.4% coverage. All 4 failures were the review machine: no `build` module, the `bdd` extra failed to install, and one test that expects `pytest` next to `sys.executable` |
| `npm audit` (frontend) | 0 in production dependencies; 6 in dev tooling (Vitest, esbuild, tinypool) |
| `pip-audit` | Nothing in the project's own dependencies |
| `vulture --min-confidence 80` | 2 unused variables; manual check found unused functions in `reporting/report_generator.py` (see D1) |

## Architecture

The design matches [ARCHITECTURE.md](../ARCHITECTURE.md) and the [Architecture Overview](Architecture/Architecture%20Overview.md): `config/loader.py` → `config/resolver.py` → `engine/orchestrator.run_plan()` → `engine/executor.run_stage()`, with both the CLI and the API going through `services/cycle_run.CycleRunService` (the only caller of `run_plan`). Ingest reuses the same service through `equipment: junit`, so uploaded results get the same history, Compare, flaky detection and reporters as real runs. That is the strongest part of the project: features added in October (ingest, team server, quarantine, alerts, Playwright JSON) slotted in without a second path.

Strengths

- Framework adapters behind a small protocol (`frameworks/base.py`), and third-party runners and reporters through entry points (`plugins.py`), so new runners need no core change.
- Storage behind `persistence/` and `repository/`, reads behind `history/`, SQLite by default and Postgres for the team server.
- Exit codes single-sourced in `engine/exit_codes.py` and locked by contract tests.
- The frontend's API types are generated from OpenAPI and CI fails when they drift.

Risks to watch

- **A1. Thread-per-run API.** `testo_api/cycle_execution_manager.py` starts a daemon thread per execution and keeps state in memory. One run per cycle is enforced, which is right, but there is no global cap on concurrent runs and a restart loses live state (orphans are cleaned up on startup). Fine for a local tool and a small team server; a queue would be the next step if the server grows.
- **A2. Sequential stages.** Already tracked as item 3 in the [Technical Debt Tracker](Testing%20Workflows/Technical%20Debt%20Tracker.md).
- **A3. Version hard-coded twice.** `testo_api/main.py` sets `version="1.1.1"` by hand next to `pyproject.toml`. Read it from `importlib.metadata` so a release can't leave the API reporting an old version.

## Security

The model in [ARCHITECTURE.md § Security model](../ARCHITECTURE.md#security-model) is sound and the code follows it: loopback by default, foreign-origin writes refused even without a token (which stops simple cross-site POSTs and DNS rebinding), `hmac.compare_digest` for the token, upload size limits, sanitised upload filenames, Playwright attachments confined to the report root, secret redaction before AI calls, and the team server's compose file refuses to start without `TESTO_API_TOKEN`. No workflow uses `pull_request_target`, and 10 of 13 set explicit `permissions:` (see S4).

Findings, most severe first

| # | Severity | Finding | Fix |
|---|----------|---------|-----|
| S1 | Medium | **Open reads take an arbitrary file path.** `GET /api/v1/cycles`, `GET /api/v1/cycles/{cycle}` and `GET /api/v1/runs/{run_id}/pyramid` accept `?config_path=` and load it. Reads need no token even when `TESTO_API_TOKEN` is set, so anyone who can reach a team server can probe whether any file exists and see fragments of non-YAML files in the error message (checked: `config_path=/root/.bashrc` returns a line of the file in the YAML parse error) | Drop `config_path` from GET routes, or restrict it to files under the configured project root, and return a generic error message |
| S2 | Medium | **Public bind without a token only warns.** `testo-api` on a non-loopback host with no `TESTO_API_TOKEN` logs a warning and starts, and the `testo-server` image binds `0.0.0.0`. A plain `docker run -p 8000:8000 testo-server` exposes "start a run", which runs commands, to the network | Refuse to start in that case unless an explicit `TESTO_ALLOW_UNAUTHENTICATED=1` is set |
| S3 | Low | **Reads and `/history` are open on the team server.** Run logs and report files can carry secrets printed by tests. Documented in the [Team Server](Processes%20&%20Guides/Team%20Server.md) guide, but there is no switch to protect them | Add an opt-in `TESTO_API_READ_TOKEN` (or require the token for reads when set) |
| S4 | Low | **Floating action refs and default token scope.** `aquasecurity/trivy-action@master` and `anthropics/claude-code-base-action@beta` run in the Docker publish and changelog-on-main workflows, and `commitlint.yml`, `pr-heavy.yml` and `release-gate.yml` have no `permissions:` block, so they get the repository's default token scope. A compromised upstream branch would run with those jobs' secrets | Pin the two actions to a release tag or commit SHA (Dependabot already watches `github-actions`) and add `permissions: contents: read` to the three workflows |
| S5 | Low | **AI `base_url` is free-form.** With a write token, the AI settings page can point the provider at any URL and the server will send the key there. Acceptable for a self-hosted tool; worth a sentence in the security model | Document it, optionally allow-list schemes and hosts |

XML from uploads is parsed with the standard library's `ElementTree`, which on Python 3.11+ does not resolve external entities and has expat's entity-expansion limits, and uploads are size-capped, so XXE and billion-laughs are not a concern.

## Code quality and tech debt

Prioritised with the tech-debt formula, priority = (impact + risk) × (6 − effort), each scored 1 to 5.

| # | Item | Type | Impact | Risk | Effort | Priority |
|---|------|------|:------:|:----:|:------:|:--------:|
| S1 | `config_path` on open GET routes | Security | 2 | 4 | 1 | **30** |
| S2 | Public bind without token is fail-open | Security | 2 | 4 | 1 | **30** |
| D2 | Large unreleased backlog: `CHANGELOG.md [Unreleased]` holds ingest, the team server, Playwright JSON, quarantine, alerts, the config schema, the plugin API and a breaking extras change. PyPI users are on 1.1.1 | Release | 4 | 3 | 2 | **28** |
| D1 | Streamlit-era dead code in `reporting/report_generator.py`: `sync_all_reports_to_static`, `start_report_server`, `start_static_server`, `collect_behavex_native_report` and `url_for` have no caller in `testo_core/` or `testo_api/`, and six comments still mention Streamlit, which was removed in v1.1 | Code | 3 | 2 | 1 | **25** |
| D3 | No Python version matrix: classifiers claim 3.12 and 3.13, CI runs only 3.11 | Infrastructure | 2 | 3 | 1 | **25** |
| T1 | Thin coverage where users plug in: TestBeats reporter 18%, `cli/commands/config.py` 19%, ReportPortal reporter 26%, Anthropic provider 30%, `cli/commands/report.py` 39% | Test | 3 | 3 | 3 | **18** |
| D4 | No Python lock or constraints file, only lower bounds, so CI resolves the newest dependencies on every run and an upstream release can turn `main` red with no change here. Normal for a library; checked that today's latest versions pass `mypy` and the suite on 3.12 and 3.13 | Dependency | 1 | 2 | 2 | **12** |
| D5 | Frontend dependency debt: Dependabot PRs for Vite 8 (#105) and TypeScript 7 (#106) break the build; dev tooling has 6 `npm audit` advisories | Dependency | 2 | 2 | 3 | **12** |
| D6 | `testo_core/mascot/` (422 lines, 0% coverage) ships inside the core package for a UI animation | Code | 1 | 1 | 2 | **8** |
| D7 | No frontend linter (ESLint or Biome); `tsc` is the only static check | Infrastructure | 1 | 2 | 2 | **12** |

Good habits worth keeping: no `TODO` or `FIXME` markers in the Python packages, every broad `except Exception` has a comment saying why, 14 `type: ignore`s across ~20k lines, and functions are small with a few exceptions (`config/loader.py`, `reporting/report_generator.py`, `cli/commands/report.py` and `testo_api/cycle_execution_manager.py` are each 500+ lines).

## Tests

The suite is a pyramid in the right shape: 102 unit files, 19 contract files (exit codes, CI tiers, packaging, OpenAPI), 7 integration and 3 end-to-end, with tiers and a quarantine marker. The fast tier runs in about 16 seconds, which keeps it on every pull request, and coverage is 79% against a 65% gate. The project also tests itself through its own GitHub Action and the fake-api demo, which is a strong signal.

Gaps

- **T1** above: reporters and CLI report commands are where outside users integrate, and they are the least covered.
- **T2.** The frontend has 17 test files for ~8k lines of TypeScript. The Compare and Run Detail pages carry the product's main story and deserve component tests for their empty, error and loading states.
- **T3.** A few tests assume the machine: `test_target_inside_another_pytest_project_keeps_its_own_rootdir` expects `pytest` next to `sys.executable`, and the packaging contract needs `build`. Skip them with a clear reason when the tool is missing, so a contributor's first local run is green.
- **T4.** With no 3.12/3.13 job (D3), the version claims in `pyproject.toml` are untested.

## Docs and developer experience

The vault is the project's best interview asset: a linted entry point, ADRs per decision, an architecture document with a security model and known limits, a getting-started guide that CI runs end to end, and a docs site. `CONTRIBUTING.md`, issue and PR templates, `SECURITY.md`, a code of conduct and `CITATION.cff` are all present.

Small gaps: `actionlint_py-1.7.12.25.tar.gz` is committed at the repo root and looks like a stray download, and the README is 333 lines, so a newcomer has to scroll past a lot before the first command.

## Remediation plan

Each phase fits next to feature work.

1. **This week (security and hygiene, ~1 day).** S1, S2, S4, A3, D1, and delete the stray tarball.
2. **Next release (~1 day).** D3 (add 3.12 and 3.13 to the test matrix), T3, then cut the release in D2 so PyPI users get the October features.
3. **Following month.** T1 and T2 coverage, D7 frontend linter, D5 Vite 8 and TypeScript 7, S3 read token, decide whether `mascot/` belongs in the core wheel (D6), and revisit D4 only if an upstream release breaks `main`.

## Progress

- 2026-10-24, step 1 done in the same pull request as this note: S1 (read routes only load config file names), S2 (public bind without a token refuses to start), S4 (actions pinned to SHAs, read-only `permissions:`), A3 (API version from package metadata), D1 (dead report helpers and the stray tarball removed).
- 2026-10-24, step 2 in the same pull request: D3 (a `test (python 3.12/3.13)` CI job, suite green on both in clean venvs) and T3 (the rootdir test finds `pytest` on `PATH` when it is not next to the interpreter; BehaveX tests skip without the `bdd` extra). D4 re-scored after a clean-venv check. The release (D2) waits on Taltal.
- 2026-10-24: D6 done, the mascot moved to `scripts/mascot/` and out of the wheel.
