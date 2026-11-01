---
type: roadmap
status: current
created: 2026-11-01
updated: 2026-11-01
---

# New user journey audit (2026-11-01)

[Index](../Index.md) · [Product Roadmap](Product%20Roadmap.md) · [Getting Started](../Getting%20Started.md) · [Easy Setup - 2026-11-01](../Specs%20&%20ADRs/Easy%20Setup%20-%202026-11-01.md) · [Feature Gaps and Quick Wins](Feature%20Gaps%20and%20Quick%20Wins%20-%202026-10-31.md)

Every step a new user takes, from finding Testosterone to running it for a team, checked against the code on `main` at `04246b5` (after #273). For each step: what the user still does by hand, what the tool already does for them, where it hurts, and what could be automated. **Nothing here is built.** The proposals wait on the maintainer's pick.

How it was checked: reading the CLI commands, the Action, the API routes, the UI's empty states and the docs, plus a run of the pytest path in a fresh folder (`testo init`, `testo try`, `testo doctor`). Work still in open pull requests is named where it changes the answer: #249 (stricter flaky detection, quarantine from the UI, flaky-test issues, `testo mcp`), #248 (`testo backup` / `testo restore` and other paid-tier copies) and `testo init --scan` (in progress in another thread).

Effort, as in [Feature Gaps and Quick Wins](Feature%20Gaps%20and%20Quick%20Wins%20-%202026-10-31.md): **S** under a day, **M** one to three days, **L** one to two weeks. Impact: **High** most new users hit it, **Med** many do, **Low** a few.

## The top five gaps

| # | Gap | Step | Impact | Effort |
|:-:|---|:-:|:-:|:-:|
| 1 | **`testo init` is the easiest way in, but almost nothing points at it.** The README's "Try it in a minute" and Quickstart, the UI's first-run guide (which says `testo config init`), the `/try` page and the Setup Prompts all lead with older paths. `testo init` first shows up at README line 201 | 1, 3 | High | S |
| 2 | **After `testo init` the user still commits, pushes, opens a pull request and waits for a first run on `main`**, and the pull request comment only has a baseline once `main` has run. A `testo init --pr` that does those steps with `gh` turns setup into one command | 3, 6 | High | M |
| 3 | **CI history is only visible inside CI.** The Action keeps history in the Actions cache; to look at it in the UI a user needs a team server. `testo ui --from-github` (download the cached history and open it) would close the loop without a server | 7 | High | M |
| 4 | **A team server starts from a checkout and hand-made secrets.** The compose file lives in `deploy/server/`, the token is made with `openssl`, HTTPS needs your own reverse proxy, the first account is made with `docker compose exec`, and there's no backup on `main`. `testo server init` could write all of it | 10 | Med | M |
| 5 | **The same test can look "new" and "removed" at once.** After `testo init` recorded the pytest stage, `testo try` on pytest's own JUnit file said `test_a` was new *and* removed: a `testo run` stage and an ingested file don't line up, so mixing the paths (init, `pytest --testo`, `testo ingest`, the Action) splits history | 4, 5 | Med | S–M |

Two small bugs found on the way, worth fixing whatever is picked: the header that `testo init` writes into `testosterone.yaml` links to `docs/CLI%20Commands/Command%20Reference/`, but the docs site slugs page paths (`scripts/mkdocs_hooks.py`), so the page is at `docs/cli-commands/command-reference/` (from `testo_core/services/project_setup.py:551`); and the [Team Server](../Processes%20&%20Guides/Team%20Server.md) note still says upload-only cycles aren't on the Cycles page, which #176 fixed.

## Step by step

### 1. Discover (README, `/try`, live demo)

- **By hand:** read the README, find the right path for their runner, decide between `pytest --testo`, `testo ingest`, `testo run` and `testo init`.
- **Already automated:** the [`/try`](https://taltal-beep.github.io/testosterone/try) page reads a JUnit file in the browser; the live demo; `testo demo` records eight sample runs and opens the UI.
- **Friction:** four ways in, and the one that does the most for you (`testo init`) isn't among the first three the README shows. The UI's first-run guide (`frontend/src/features/dashboard/DashboardPage.tsx`) says `testo config init` and greets with "Welcome to Testo" (the name stays Testosterone). The `/try` page ends with an ingest snippet, not "set this up for my repository". [Setup Prompts](../Prompts%20&%20Snippets/Setup%20Prompts.md) don't mention `testo init`.
- **Proposals:**
  - **D1 (High, S).** Make `testo init` the headline everywhere: README hero and Quickstart, Getting Started step 1, the first-run guide, Setup Prompts (the prompt becomes "run `testo init --dry-run`, check it, then `testo init`").
  - **D2 (Med, S).** On `/try`, after a file is read: a "Get this on every pull request" card with `pipx run --spec testo-core testo init` (or the `pip install` pair) and the workflow `testo init` would write.

### 2. Install (pip, Docker, Action, `testo ui`)

- **By hand:** a Python 3.11+ environment; pick extras (`[api]` for the UI, `[bdd]` for Behave, `[db]`, `[otel]`, `[mcp]` in #249).
- **Already automated:** the Action installs `testo-core` itself; the runner image has it; `testo ui` says which extra is missing and exits `2`; the wheel carries the built UI.
- **Friction:** JavaScript, Go and .NET teams may not have a Python they want to touch. `testo ui` without `[api]` stops instead of offering to install. A stale environment (an editable install from before `alembic` became a dependency) fails with a raw `ModuleNotFoundError` traceback on the first recorded run.
- **Proposals:**
  - **I1 (Med, S).** Document a no-venv path: `uvx --from 'testo-core[api]' testo ui` / `pipx run`, and use it in the non-Python Setup Snippets (the GitLab, Jenkins and CircleCI templates already install with uv).
  - **I2 (Low, S).** A top-level handler for `ModuleNotFoundError` of a declared dependency or extra: one line saying which `pip install` fixes it, no traceback.
  - **I3 (Low, S).** `testo ui` offers to `pip install 'testo-core[api]'` into the current environment when run in a terminal.

### 3. Set up (`testo init`)

- **By hand:** run `testo init`, read the output, commit the three files, push, open a pull request; fix the install line for projects that install test dependencies some other way; add Cypress by hand (detected, not added); in a monorepo, run it per folder (`--scan` is in progress).
- **Already automated:** stack detection for ten runners, `testosterone.yaml` with the schema line, `.github/workflows/testosterone.yml` (or `--ci gitlab|jenkins|circleci`), `.gitignore` lines, a first recorded run, `--dry-run`, never overwriting an existing pipeline.
- **Friction:** setup ends at "Next: git add ... && git commit", so the real goal (a comment on a pull request) is still four manual steps away. The docs link in the generated YAML header is broken (above).
- **Proposals:**
  - **S1 (High, M).** `testo init --pr`: create a branch, commit the files, push, open a pull request with `gh`, and trigger the workflow on the default branch (`gh workflow run`) so the first pull request has a baseline. Falls back to printing the commands without `gh`.
  - **S2 (Med, S).** Fix the header link; add a test that every URL `project_setup.py` and `ci_templates.py` write matches a page the docs build produces.
  - **S3 (Low, S).** Add Dependabot entries for `pip` and `github-actions` to what `init` writes when `.github/dependabot.yml` is missing (helps step 11).

### 4. Verify (`testo try`)

- **By hand:** run the tests so they leave result files, then `testo try` (or `--from-github`, which needs `gh` signed in).
- **Already automated:** a real ingest and markdown render in a throwaway history, with the local SQLite history copied in so the comparison is real.
- **Friction:** in the fresh-folder run, after `testo init` recorded the `pytest` stage, `pytest --junitxml` then `testo try` showed `test_a` as both "new" and "removed". The stored key for the run was `tests.test_a#test_a` in stage `pytest`; the preview's run was a `junit` stage, so the comparison likely keys tests per stage. The preview then shows a confusing first comment exactly when a user is deciding whether to adopt. `testo try` with no result files says to run the tests; it could offer to.
- **Proposals:**
  - **V1 (Med, S–M).** Compare tests across stage names when one side is a generic `junit` stage (or record ingested pytest files with stage `pytest`), so `testo run`, `pytest --testo` and `testo ingest` of the same suite line up. Fixes step 5 too.
  - **V2 (Low, S).** `testo try --run`: run the cycle (or the detected test command with its result-file flag) first, then preview.

### 5. First run or import

- **By hand:** choose `pytest --testo`, `testo ingest`, or `testo run`; pick a cycle name and keep it the same everywhere.
- **Already automated:** `testo ingest` with no arguments finds result files by content and names the cycle after the folder; `pytest --testo` records branch and commit; `testo init` records a first run and treats a failing test as recorded.
- **Friction:** the paths name stages differently (see V1), and a user who starts with `pytest --testo` locally and `testo init`'s cycle in CI ends up with two histories under one name. Nothing tells them.
- **Proposals:** V1 above; **F1 (Low, S)** a one-line warning in `testo summary` and the run page when the previous run of the cycle has a different set of stages.

### 6. Wire CI (Action, snippets, secrets, baseline branch)

- **By hand:** commit the workflow; add secrets (`SLACK_WEBHOOK_URL`, `TESTO_API_TOKEN`, a server URL); grant `pull-requests: write` (and `issues: write` for `flaky-issues`) in hand-written workflows; for a team server, write a separate `testo ingest --server` step.
- **Already automated:** zero-config mode (finds results, `comment-on-pr: auto`, history in the Actions cache); the baseline branch comes from `GITHUB_BASE_REF`; generated GitLab, Jenkins and CircleCI files with history caching; inputs are passed as environment variables.
- **Friction:** the Action has no `server-url` / `server-token` inputs. `testo ingest` reads `TESTO_SERVER_URL` from the environment so zero-config mode can upload, but that isn't one of the Action's documented inputs, and a cycle run by the Action (`testo run --ci`) never reaches a server. Pull requests from forks get a read-only token, so the comment is skipped with a warning. The first pull request after setup compares with nothing until `main` has run once (S1 covers it).
- **Proposals:**
  - **C1 (Med, S).** `server-url` and `server-token` inputs on the Action, for both modes (upload the recorded run after `testo run`).
  - **C2 (Med, S–M).** `testo init --server URL` writes those inputs and, with `gh`, sets the token secret (`gh secret set TESTO_API_TOKEN`), so secrets aren't a separate trip to the settings page.
  - **C3 (Low, M).** A fork-safe template: the test workflow uploads results as an artifact and a `workflow_run` workflow posts the comment, written by `testo init --ci github --forks`.

### 7. Read results

- **By hand:** open the job summary or the comment; locally, `testo summary`, `testo flaky`, `testo ui`.
- **Already automated:** job summary, one updated comment per cycle, inline annotations, failing tests first in the UI, per-test pages, Compare, Project health.
- **Friction:** a CI-only user (most zero-config users) has history in the Actions cache and no way to browse it. The cache is also evicted by GitHub after a week without use, and a run that starts with an empty history looks like a first run without saying so.
- **Proposals:**
  - **R1 (High, M).** `testo ui --from-github [--repo owner/name]`: download the latest cached history (as an artifact the Action also uploads) and open the UI on it. Reuses `testo try --from-github`'s `gh` plumbing.
  - **R2 (Med, S).** When the Action's history restore misses, say so in the job summary ("no earlier history found: first run, or the cache expired") instead of a silent first run.
  - **R3 (Low, M).** Optional static report on GitHub Pages from the Action, the way this repository's demo is built.

### 8. Flaky handling (quarantine, issues)

- **By hand on `main`:** read `testo flaky`, paste a `quarantine:` rule into `testosterone.yaml` (which `pytest --testo` and ingest-only users don't have); open issues by hand, or turn on the Action's `flaky-issues` input.
- **Already automated on `main`:** flip-based detection with retries in one run counted as flaky (Playwright, Jest, Xcode, Surefire, Gradle retries); `quarantine:` rules keep a red test from failing `testo run`; the Action's `flaky-issues` opens one issue per newly flaky test.
- **In #249 (open):** stricter detection (flaky vs broken, same commit, same branch), quarantine from the UI and `testo quarantine` with no config file, `TESTO_ISSUES=github` opening and closing issues with CODEOWNERS owners.
- **Friction that stays after #249:** in Actions-cache mode the quarantine list lives in each workflow's cache, so a `testo quarantine add` on a laptop doesn't reach CI without a server or the YAML; and nothing quarantines or releases a test on its own.
- **Proposals:**
  - **Q1 (High, S).** Merge #249 first; it closes most of this step.
  - **Q2 (Med, M).** An opt-in policy, `quarantine: {auto: {flip_rate: 0.3, release_after_green_runs: 10}}`, applied after each recorded run, with the change listed in the pull request comment.
  - **Q3 (Low, S).** `testo quarantine add` prints the YAML line too when no server or persistent database is configured, so CI-cache users know the laptop list won't reach CI.

### 9. Pull request review comment

- **By hand:** set `comment-on-pr: "true"` and `pull-requests: write` when a cycle is configured (only zero-config mode turns it on by itself).
- **Already automated:** one comment per cycle, edited on later pushes; baseline is the target branch; "New" vs baseline; flaky and slower tests; rerun commands; CODEOWNERS owners and a prefilled issue link.
- **Friction:** the AI failure summary exists only in the UI. Forks (C3).
- **Proposals:** **P1 (Med, M)** an opt-in `ai-summary` Action input that adds the summary to the comment, using a provider key from a secret (the free OpenAI-compatible Gemini route keeps it free). **P2 (Low, S)** `testo init` already turns comments on; make the README's hand-written workflow example do the same.

### 10. Team use (server image, accounts, runner service, TLS, backups)

- **By hand:** clone the repository for `deploy/server/docker-compose.yml`; make a token with `openssl rand -hex 32`; `docker compose up -d`; put HTTPS in front with your own proxy and set `FORWARDED_ALLOW_IPS`; `docker compose exec server testo users add ...` for each person; a second compose file for the runner service; backups of the Postgres volume by hand (`testo backup` arrives with #248); add `--server` and the token to every CI job.
- **Already automated:** the server image with the UI built in, schema migrations at startup, history retention, a protected-reads default, login throttling, a queued-run table, the runner service, a CI smoke test of the whole compose file.
- **Friction:** every item in "by hand" is a separate page section; a small team without an ops person stops at HTTPS.
- **Proposals:**
  - **T1 (Med, M).** `testo server init [--domain testo.example.com]`: writes `docker-compose.yml` and `.env` with a generated token, an optional Caddy service that gets a certificate on its own, the first admin from `TESTO_ADMIN_USER` / `TESTO_ADMIN_PASSWORD` on first start, and prints the CI lines to paste (or sets them with `gh`, C2).
  - **T2 (Med, S, after #248).** A backup service in the compose file running `testo backup` nightly with a kept count.
  - **T3 (Low, S).** Fix the stale "Limits today" bullet in [Team Server](../Processes%20&%20Guides/Team%20Server.md).

### 11. Upgrade and maintain

- **By hand:** notice a new release, `pip install -U testo-core`, pull the new image, read the CHANGELOG.
- **Already automated:** `@v1` in workflows moves on each stable release; image tag `1`; SQLite and Postgres schemas migrate on first use; history retention prunes old runs.
- **Friction:** nothing tells a laptop or server user that a release exists; a broken environment after an upgrade shows a traceback (I2).
- **Proposals:** **U1 (Med, S)** `testo doctor` and the UI's footer show "testo-core X is out" from PyPI's JSON API, cached a day, off with `TESTO_NO_UPDATE_CHECK=1` and never in CI. **U2 (Low, S)** Dependabot lines from `testo init` (S3). **U3 (Low, S)** an "Upgrading" section in the CHANGELOG for releases that need an action.

### 12. Go further (plugins, MCP, AI)

- **By hand:** plugins: copy `examples/plugin`, write the entry points, `testo plugins` to check. MCP (#249): `pip install 'testo-core[mcp]'`, then `claude mcp add testosterone -- testo mcp --config ...` or edit `.mcp.json`. AI: open Settings in the UI and paste a key, or switch on the Claude Code provider that uses the local `claude` login.
- **Already automated:** plugin discovery and listing; MCP read tools over the local history; three AI providers with the claude-code one needing no key.
- **Friction:** no CLI for AI settings, so a CI or server setup has to go through the browser; MCP and plugins are copy-from-docs.
- **Proposals:** **G1 (Med, S)** `testo mcp install [--client claude-code|claude-desktop|cursor]` writes the right config file with this project's path. **G2 (Low, S)** `testo ai setup` finds `claude` on PATH or an `OPENAI_API_KEY`/`ANTHROPIC_API_KEY`/Gemini key in the environment and writes the settings the UI writes. **G3 (Low, S)** `testo plugins new <name>` writes a package from the example with both entry points and a test.

## All proposals, ranked

Ordered by impact, then by effort.

| Rank | Id | Proposal | Impact | Effort |
|:-:|:-:|---|:-:|:-:|
| 1 | D1 | `testo init` as the headline path in the README, Getting Started, the UI's first-run guide and Setup Prompts | High | S |
| 2 | Q1 | Merge #249 (quarantine without config, flaky issues, MCP) | High | S |
| 3 | S1 | `testo init --pr`: branch, commit, push, pull request, first run on `main` | High | M |
| 4 | R1 | `testo ui --from-github`: browse the CI history without a server | High | M |
| 5 | S2 | Fix the broken docs link `testo init` writes, and test every generated URL | Med | S |
| 6 | C1 | `server-url` / `server-token` Action inputs for both modes | Med | S |
| 7 | U1 | Update notice in `testo doctor` and the UI | Med | S |
| 8 | R2 | Say when the Action starts with no history | Med | S |
| 9 | G1 | `testo mcp install` | Med | S |
| 10 | I1 | `uvx` / `pipx` path for non-Python teams | Med | S |
| 11 | D2 | "Get this on every pull request" card on `/try` | Med | S |
| 12 | V1 | One test identity across `testo run`, `pytest --testo` and `testo ingest` stages | Med | S–M |
| 13 | C2 | `testo init --server` sets the CI secret with `gh` | Med | S–M |
| 14 | T2 | Nightly backup service in the compose file (after #248) | Med | S |
| 15 | T1 | `testo server init` with automatic HTTPS and a first admin | Med | M |
| 16 | Q2 | Automatic quarantine and release policy | Med | M |
| 17 | P1 | AI summary in the pull request comment | Med | M |
| 18 | I2, I3, S3, V2, F1, Q3, P2, T3, U3, G2, G3 | Small polish items from the steps above | Low | S each |
| 19 | C3, R3 | Fork-safe comment template; static report on Pages | Low | M |
