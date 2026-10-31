# Changelog

All notable changes to `testo-core` will be documented in this file.

This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Added
- Python 3.14 is tested in CI and listed in the package classifiers

### Security
- PR comment and job summary: a backtick in a test name (which in a fork's pull request its author controls) ended the code span, so `@user` mentions and HTML after it rendered live. Names are now fenced so nothing inside can close them, and stage, runner and branch cells are plain text. A cycle name with `-->` can no longer end the comment marker

### Fixed
- Result importers no longer crash or silently drop results on odd files. A file with unexpected field types (Jest, Playwright, RSpec, k6) or a JUnit `time="inf"` used to crash the whole import and lose every other file's results; now that one file is skipped and logged. A `<testsuite>` nested in a root `<testsuite>` is read (it counted 0 tests), UTF-16 XML is read, XML that isn't JUnit (an HTML error page) is reported instead of counting 0 tests, a report whose name contains `-attachment` is no longer skipped as an Allure attachment, Maven Surefire reruns (`flakyFailure`, `rerunFailure`) mark the test flaky, and a JUnit failure message is capped like its trace
- Two stages with the same name in one cycle (or names that differ only in case) are a config error: the second stage wiped the first one's results, so a failed test could disappear from the run. Each stage's `run.log` now holds only the latest run instead of growing with every run (it was copied whole into every run's history snapshot)
- Robot Framework: a failed suite teardown fails that suite's passed tests, as `robot` reports them ("Parent suite teardown failed"); `output.xml` keeps their own PASS, so they counted as passed
- The PR comment's baseline is never another branch's run: a push to the default branch compares with the previous run on that branch (it took the newest run on any branch), and a pull request whose target branch has no run yet compares with its own previous run instead of another pull request's
- `timeout_s`, `workers` and `version` in `testosterone.yaml` are checked the way the JSON Schema says: `timeout_s: abc` gives a config error instead of a traceback, `timeout_s: 0` or `-1` (which timed every stage out at once) and `workers: 0` are config errors, and an unknown `version` is refused; `testo run --workers 0` is refused too. A stage whose `target_repo` doesn't exist says so instead of "executable not found"
- The run summary no longer says "No test changed outcome" when the previous run has no stored test results; it says there is nothing to compare with
- GitHub Action: when `testo run` stops before recording a run (bad config, crash), the action no longer publishes the previous job's run (restored from the cache) as this job's summary, PR comment, annotations and alert, and `summary_json` now carries the `error` event's message
- `testo run` without `--cycle` on a config with several cycles says to pick one with `--cycle` instead of "cycle '<unspecified>' not found"
- Plugins: one reporter plugin that fails to import or to start no longer turns off every reporter (Slack, Teams, Allure, ...); it is reported as a failed reporter and the others run. A plugin adapter or reporter whose constructor raises is now a clear `PluginError` instead of a traceback that changed `testo run`'s exit code after the cycle finished
- Affected-test selection: a rule's folder glob (`tests/payments/**`) picks only test files, so `__init__.py` and helpers no longer make `pytest --testo-affected` run everything; test files with non-ASCII names are no longer missed (git quoted their paths)
- `testo users add` checks the name, the role and whether the account already exists before asking for the password (twice), and `testo users reset-password` checks the account exists first. `testo report` with no results no longer shows reStructuredText backticks in its hint
- A red run is no longer recorded as green when the failure is outside any single test. `testo ingest` (and `junit_xml` imports) now record a `broken` result for: a Go 1.24+ build failure (`build-output` events, which made the whole `go test -json` file unreadable before), a Go test that never finished (timeout or crash), a Jest/Vitest file whose `beforeAll`/`afterAll` hook threw while its tests show passed or skipped, a Playwright spec that fails to load or a failing `globalSetup` (top-level `errors`), a TRX run whose test host crashed (`RunInfo outcome="Error"`), and a JUnit `<testsuite>` that claims failures or errors no `<testcase>` carries. `testo ingest` also exits 1 when every matching file was unreadable (truncated, empty, not a report) instead of recording a passing run with 0 tests
- Database engines are closed when the engine cache is reset, and `testo doctor` / `testo config-db` close their connection probe, so no SQLite or Postgres connections are left open (the test suite showed 110 "unclosed database" warnings)
- A mistyped command or option (`testo runn`, `testo run --bogus`), or `testo` with no arguments, printed a Python traceback with newer Typer releases. It now prints the error and a hint (or the help), and exits `2`
- `testo clean --yes` refuses to delete a folder that is the project (`artifacts_root: .`), the current, home or root folder, the config's folder or a parent of any of them, or a folder holding `.git`, `testosterone.yaml` or `pyproject.toml`. Before, `artifacts_root: .` deleted the whole project

### Changed
- UI polish from the design review: Compare and dashboard highlights read as plain sentences ("Wall duration up 6.9 s", "1 more test passed", "Pass rate up 3.8 points"; no duplicate line when the metrics duration moved as much as the wall duration), the breadcrumb names the cycle, test or run on its page and says Testosterone, the Runs list says "96% passed" instead of "health 96%", the Compare filter chips read "Status change", the phone menu is opaque, and the 404 page has a page heading
- Docs: a UI design review (`docs/Specs & ADRs/UI Design Review - 2026-10-31.md`) ranks 14 design and UX findings on the web UI with annotated screenshots and proposes fixes; linked from the Index and the docs site menu
- Docs: an architecture review (`docs/Specs & ADRs/Architecture Review - 2026-10-31.md`) ranks the codebase's structural pressure points and proposes next steps; linked from the docs site menu

## [1.5.0] - 2026-10-31

### Added
- OpenTelemetry export: a run, its stages and its tests as one trace over OTLP, so test runs show up in Datadog, Grafana Tempo, Honeycomb, Jaeger or any other OTLP backend. Tests keep their real start and stop times; failures are error spans with the message. The `otel` reporter sends it after `testo run`, and `testo otel --cycle/--run-id` sends any recorded run (`--dry-run` prints the spans). Configured with the standard `OTEL_EXPORTER_OTLP_*` variables; off unless configured. Needs the new `[otel]` extra (`pip install 'testo-core[otel]'`)
- Affected-test selection, off unless asked: `testo affected` lists the tests the changes since the baseline branch can affect, each with why it was picked (`--json`, or `--list` for any runner's command line), and `pytest --testo-affected` runs only those. Changed files map to tests through `affected.rules` globs in `testosterone.yaml`, changed test files, and a coverage.py report with test contexts; a change nothing maps, a lockfile or `conftest.py`, or a git problem runs everything and says why
- `testo pool add`, `remove` and `sweep` run a pool's own `provider.create` / `provider.destroy` commands, when a person types them: dry run unless `--apply` (which asks unless `--yes`), only verbs listed under `provider.allow`, at most 5 keys per command, `max_items` and `name_prefix` limits, never a key in `items` or one someone holds, and `TESTO_PROVIDER_ACTIONS=0` turns them off. Every command run is logged with who, where and how it went: `testo pool log`, a "Provider commands" card on the Resources page, `GET`/`POST /api/v1/resources/actions`. New table `resource_action`
- `testo pool status`: compare each resource pool with the keys that really exist. A pool's new `provider.list` is your own read-only command that prints them; the report shows keys that are missing, VMs outside the pool (leftovers) and, with `--check`, free keys that fail `on_check`. Exits `1` when something needs a look. Testosterone never creates or deletes a key on its own: only `testo pool`, typed by a person, runs provider commands, and a test checks that runs, leases, stages and the API never reach them

### Changed
- The PyPI page's Documentation link goes to the docs site instead of the GitHub wiki, and README links to guides open the rendered docs site pages

## [1.4.0] - 2026-10-30

### Added
- The GitHub Action at the repository root, ready for the GitHub Marketplace: `uses: taltal-beep/testosterone@v1` (name "Testosterone Test History", with an icon). `taltal-beep/testosterone/integrations/github-action@v1` keeps working; a test keeps the two copies the same
- `testo badge`: a README badge for a cycle's latest run ("tests | 412 passed · 2 flaky", green, yellow or red), as an SVG or a shields.io endpoint JSON. A team server serves it live at `GET /api/v1/badge.svg` and `GET /api/v1/badge.json` (`?cycle=`)
- `testo lease demo` fills the Resources page with made-up pools, holders, a disabled key and a queue, to try it out (`--clear` undoes it); the live demo shows them too.
- `testo ingest`, `junit_xml` globs and `POST /api/v1/ingest` also read RSpec JSON (`rspec --format json`), k6 summaries (`--summary-export` or `handleSummary` JSON: each check and threshold is one result) and Xcode test results exported by `xcrun xcresulttool get test-results tests` (XCTest and Swift Testing, retries flagged flaky). Android instrumentation JUnit XML (Espresso, `connectedAndroidTest`) is labelled `android` with its device. "Rerun these tests" adds `rspec <files> -e` and `./gradlew connectedAndroidTest` with the failing classes and methods
- Resource pools: an `on_check` hook (run after `on_take`; a key that fails it is taken out of the pool and another is tried), `TESTO_RESOURCE_CLEAN=1` when the last holder gave the key back after a successful `on_release` (or `testo lease release --clean`), so `on_take` can skip a reset it doesn't need, and `reuse_delay` (default `lease_ttl / 3`): an expired lease keeps its key out of the pool that much longer, so a frozen holder notices before anyone else gets it. `testo lease list` and the Resources page show such keys as expired. New columns `resource_item.clean` and `resource_lease.reuse_delay_s`, added to existing databases automatically
- "Rerun these tests" covers more runners: Jest and Vitest (`-t` on the `describe` path), `go test -run`, `dotnet test --filter`, `robot --test`, and Maven (`-Dtest=Class#method`) or Gradle (`--tests`) for JUnit XML from a JVM build whose `pom.xml` or Gradle build is in the run's target repo. Dotted JUnit names are only offered as pytest tests when they point at a `test_*.py` or `*_test.py` file
- Equipment `jest`, `vitest` and `cypress`: `args` go to `npx jest`, `npx vitest run` or `npx cypress run`, and the stage adds the report Testosterone reads (Jest's and Vitest's own JSON, Cypress's built-in JUnit reporter) with no extra package. Jest and Vitest take `--maxWorkers` from `workers`
- `testo ingest`, `junit_xml` globs and `POST /api/v1/ingest` read runners' own result files, recognised by content, so these suites need no JUnit reporter package: Jest and Vitest JSON (`jest --json`, `vitest --reporter=json`; `describe` blocks, retried tests flagged flaky, files that failed to load), .NET TRX (`dotnet test --logger trx`), `go test -json` output (subtests, build failures), Robot Framework `output.xml` (tags, messages) and Allure results (`testo ingest allure-results/`, with attachments). A folder argument stands for the files in it
- Shards by time: `pytest --testo-shard I/N` (or `TESTO_SHARD=I/N testo run ...`) runs one of N shards that take about the same time, from the recorded test times; `testo split` prints a shard's tests for other runners. `testo run` sets `TESTO_CYCLE` and `TESTO_STAGE` for each stage.
- Stages can ask for keys: `resources: POOL` on a stage gives each pytest worker (`per: worker`), each test (`per: test`) or the stage (`per: stage`) its own key, and `workers: auto` starts one worker per free key. In plain pytest: `--testo-resource POOL` and the `testo_resource` fixture.
- Resource pools for parallel runs: list keys (VMs, devices, test accounts, seats) under `resources:` in `testosterone.yaml`, and `testo lease run POOL -- CMD` gives each worker its own key in `TESTO_RESOURCE_ID`. Leases are rows with a heartbeat and a TTL, so a crashed worker frees its key; requests wait in a fair queue; failing `on_take`/`on_release` hooks take a key out of the pool. With `TESTO_SERVER_URL` the leases live on the team server, so developers on different laptops share one pool. Also `testo lease take/heartbeat/release/list/disable/enable/free`, `/api/v1/resources` and a Resources page in the UI. New tables `resource_item`, `resource_lease`, `resource_waiter`
- A Project health page (`/health`): a 0-100 test health score for the project you test, from pass rate, green builds, flaky tests, tests that got slower, skipped and quarantined tests and the test pyramid, with what to fix first and a score per cycle. An optional AI review scores the tests with checks you switch on and off (why tests are flaky, related failures, test strategy gaps, test debt, slow tests, test churn, test names), each expandable to what it checks and reads. It uses your AI provider, never reads source code and is labelled an AI estimate. New endpoints `GET /api/v1/project-health`, `GET /api/v1/project-health/skills` and `GET`/`POST /api/v1/project-health/ai-review`. On the read-only demo the checks are listed but the review can't be run
- A cycle's run history: the cycle page has a "Recent runs" card (pass rate, one square per run, the latest three), and Runs filters by cycle (`/runs?cycle=web`, backed by `GET /api/v1/runs?cycle=`) with the same pass-rate line
- Docs: "Compared with other tools", where Testosterone fits next to Allure, ReportPortal, Currents, Trunk and Datadog, and when to pick one of them instead
- Triage memory: on a failed run's page, "Mark the cause" of a failing test (bug in the product, bug in the test, environment, flaky, other, plus a note). Later failures in the same cycle with the same message (numbers, ids and quoted values aside) show that cause too, with where it was marked. New table `failure_triage`, endpoints `GET`/`PUT`/`DELETE /api/v1/triage`, and a `triage` field on each test of `GET /api/v1/runs/{run_id}/failures`
- "Flakiness over time" on the test page: the share of outcome changes over the five runs ending at each run, and how it compares with five runs before. Test-history points add `flip_rate`
- The test page shows what the last failing run kept: screenshots and videos in place, the Playwright trace as a download with the command that opens it. `GET /api/v1/analytics/test-history` adds `last_failure_attachments`
- `pytest --testo` (or `--testo-cycle NAME`): a pytest plugin, installed with testo-core and inert without the flag, that records each session as a run the way `testo ingest` does, with the checkout's branch and commit. `--testo-server` uploads to a team server instead
- The dashboard leads with "Needs attention": red cycles (failing and new-failure counts, red for how many runs), tests that just started flaking and tests that got slower, each linking to its page. New endpoint `GET /api/v1/dashboard/attention`. The rollup and quick-links cards and the KPI icons are gone, and the no-runs page explains `testo ingest`, `testo config init` / `testo run` and the try-it page
- The run page has a "Rerun these tests" command per runner (pytest node ids, `npx playwright test --grep`, `behave --name`) with a Copy button, from the new `rerun_commands` field of `GET /api/v1/runs/{run_id}/failures`
- Compare opens on the latest run against the one before it in its cycle, and each run in the pickers shows its branch (`GET /api/v1/runs` adds `branch`)
- The run page shows the branch, pull request target and commit the run tested (linked on GitHub), and `GET /api/v1/runs/{run_id}` returns them
- Cycles recorded with `testo ingest` (or by another machine) have a cycle page: `GET /api/v1/cycles` lists them after the config's cycles with `source: "history"`, and their page shows the test search, slowest tests and flaky card without a Run panel. `testo ui` in a folder with no `testosterone.yaml` lists recorded cycles instead of an error
- Docs: second pass of the product review ([docs/product-review.md](docs/product-review.md)): 6.5 to 7.5, what a 10 needs in each area, and new findings, chiefly that cycles created by `testo ingest` have no cycle page
- A try-it page (`/try`, "Try a file" under Tools, also on the static demo): drop JUnit XML files, or use the sample, and see the run the way Testosterone shows one (verdict, failing tests with shared causes grouped, slowest tests), read in the browser with nothing uploaded

### Changed
- Claude Code on the web sessions install `.[dev]` into `.venv` at startup (`.claude/hooks/session-start.sh`), since the container's system pip can't build csscompressor
- One health score: the dashboard's Health card now shows the Project health score (same number as `/health`) and opens that page. A run's own pass percentage is labelled "Pass rate" on the run page and in Compare, and "passed" in the dashboard's recent runs
- The test page's duration chart shows its scale (longest run and zero); slowdown percentages read the same on the dashboard and the cycle page; the dashboard says "All 3 cycles are red." when none passed; Runs says "Every recorded run" instead of "archived cycle run"
- Charts have text alternatives: the test page's duration chart reads its values, and the flaky card's outcome strip is announced
- UI accessibility and copy: the skip link is inside a landmark; the demo notice's close button, the demo badge and list links meet the 24 px target size; "Generate AI summary"; trends read "Better than last run" / "Worse than last run" / "No change"; the test pyramid uses plain labels and sentences (also in the API's pyramid `message`); health shows whole-number percentages. The default OpenAI model is `gpt-4.1-mini`. `testo config init --help` and `testo config-db --help` no longer show broken markup
- A failing test is "New" on the run page when it isn't failing on the run's baseline: the latest run on a pull request's target branch, else the run before on the same branch, as in the PR comment. The card says "new since main" and marks tests that also fail on main; streaks follow the run's own branch. `GET /api/v1/runs/{run_id}/failures` adds `new`, `baseline_run_id` and `baseline_branch`

## [1.3.0] - 2026-10-25

### Added
- Flaky tests and the per-test page show the test's owners from CODEOWNERS and an "Open an issue" link (GitHub's new-issue form, prefilled with the test, cycle, last failure and owners). Runs record their `repository` (`owner/name`) from CI variables or a github.com `origin` remote
- A page for each test (`/cycles/<cycle>/test?key=`): pass rate, flaky or not, last failure, duration per run and every run with its branch. The cycle page can search its tests and lists the slowest tests and the ones that got slower. New endpoints `GET /api/v1/analytics/tests` and `GET /api/v1/analytics/test-history`
- Pull request comments and `testo report markdown` compare a PR's run with the latest run on its target branch (new `--baseline-branch` overrides), not with whichever run came before, and say which baseline they used. Runs record the PR's target branch (`ci_base_ref`, also accepted by `testo ingest`), the PR's own branch on GitHub, and the local git branch and commit outside CI
- `testo ui`: the web UI ships inside the wheel, so `pip install 'testo-core[api]' && testo ui` opens the dashboard on this machine's run history (http://127.0.0.1:8000) with no checkout or Node. `testo-api` also serves the bundled UI when `TESTO_UI_DIR` isn't set
- UI accessibility and copy pass: stronger primary-button contrast, a visible keyboard focus ring, a skip link, h1 → h2 headings, a 44px mobile menu button, AI settings fits a phone, load errors say what to check, sentence-case titles, "Advanced" is now "Tools" with a plain Docs link, and the dashboard hides unknown trends and missing reports. `testo --help` has the README's tagline and no RST double backticks
- The run page leads with its failing tests: each with its failure message, stage, "New" or "Failing for N runs", and a flaky badge, and failures that share a message are grouped ("2 tests: ConnectionRefusedError ..."). A one-line verdict sits under the title; the run id, exit code (now explained, e.g. "1 (tests failed)") and duration moved to a Details card. New endpoint `GET /api/v1/runs/{run_id}/failures`
- Compare and the dashboard ignore timing noise: a duration change under 5% of the baseline, or under 100 ms (5 ms for the per-test average), is "Within noise" instead of a red regression or a green improvement
- Docs: a product review ([docs/product-review.md](docs/product-review.md)) scoring positioning, onboarding, the red-build workflow, design, accessibility and copy against Allure, ReportPortal, Currents and Trunk, with a Now / Next / Later roadmap
- Opt-in throwaway containers for runs started on a team server: with `TESTO_RUNNER=container` each stage runs in a fresh container started by a separate runner service (`testo-runner-service`, `Dockerfile.testo-runner-service`, `deploy/server/docker-compose.runner.yml`), with no Linux capabilities, a process limit, fixed mounts and only the stage's own variables. The API never gets the Docker socket. Default `host` (unchanged)
- Sign-in throttling with `TESTO_AUTH=accounts`: after `TESTO_LOGIN_MAX_FAILURES` (default 5) wrong passwords for a name in 15 minutes, or four times that from one address, `/login` answers `429` until the window slides
- `TESTO_REPORTS_ORIGIN` serves report pages from a second hostname, so script in a report can't act with the viewer's session on the API's origin. Off by default
- Per-user accounts for the team server, off by default: with `TESTO_AUTH=accounts` people sign in with their own username and password, roles `viewer` / `runner` / `admin` decide who can start runs or change settings, every write and sign-in is in an audit log (`GET /api/v1/audit`), and `testo users` manages accounts. The UI shows who is signed in. The API token keeps working as an admin for CI
- `TESTO_RUN_QUEUE=db` keeps API runs that are waiting for a worker in the database, and the server queues them again on startup, so a restart or upgrade no longer drops them. Default `memory` (unchanged)
- Opt-in parallel stages: a cycle with `max_parallel_stages: N` runs up to N stages at once (default `1`, unchanged). Events and the renderer stay on one thread, results keep config order, `fail_fast` starts no new stages after a failure, and stage names must be unique in a parallel cycle
- The API runs at most `TESTO_MAX_CONCURRENT_RUNS` executions at once (default `2`) on a fixed worker pool; further runs wait as `queued` instead of each starting its own thread
- Team server sign-in: `TESTO_PROTECT_READS=1` makes every read (API, `/history` report files, the UI, the live run stream) need the API token, and a `/login` page trades the token for an HttpOnly session cookie that also authorizes writes. On in `deploy/server/docker-compose.yml`; the UI it serves redirects to `/login` when the session is missing. Off by default elsewhere, so local use is unchanged
- Frontend lint: ESLint with `typescript-eslint` and the React hook rules (`frontend/eslint.config.js`, `npm --prefix frontend run lint`), blocking in CI's `frontend` job
- Unit tests for the TestBeats and ReportPortal reporter payloads, the Anthropic provider, and the `testo config` and `testo report` commands (coverage 80% to 83%)
- Frontend tests for the loading, error and empty states of the run detail and Compare pages

- Unit tests for the Allure report wrapper, the local report server, the Behave adapter's argument building, the BehaveX-to-Allure export and `testo watch`'s debounced re-runs (each module now at 92% or more; total coverage 84% to 86%)
### Changed
- Internal split of the three largest modules: run event streaming moved to `testo_api/execution_events.py`, config section parsing to `testo_core/config/sections.py`, and `testo report list` / `open` to `testo_core/cli/commands/report_archive.py`. No behaviour change
- The release workflow's "Verify install from PyPI" step retries for up to five minutes instead of one 30-second wait, so a slow PyPI index no longer marks a published release as failed
- The `testo-server` image sets `TESTO_PROTECT_READS=1`, so a plain `docker run` protects reads too, not only `deploy/server/docker-compose.yml`. Set it to `0` to open reads on a trusted network
- Frontend on React 19 (`react`, `react-dom` and their types together), `@testing-library/jest-dom` 7 and the latest TanStack Query and PostCSS patches; replaces Dependabot #132, #133 and #135, which bumped `react` without `react-dom`
- The pixel mascot's frame source moved from `testo_core/mascot/` to `scripts/mascot/`, so it no longer ships in the wheel; the UI animations are unchanged. Play it with `python -m scripts.mascot flex`, regenerate the frontend frames with `python -m scripts.mascot.export_ts`
- Frontend toolchain: Vite 8 (Rolldown) and Vitest 5, replacing Vite 5 and Vitest 2; clears the six dev-only `npm audit` advisories (esbuild dev server, Vitest mocker, tinypool). `vite.config.ts` takes `defineConfig` from `vitest/config`, and the `EventSource` test mocks are constructor functions, which Vitest 4+ requires

### Fixed
- An API run that raised `SystemExit` (say, a reporter plugin calling `sys.exit()`) took its worker thread down for good, shrinking the pool until queued runs never started; the worker now survives it and dead workers are replaced
- The API sends `X-Content-Type-Options: nosniff` and `frame-ancestors 'self'` on every response, and serves report attachments under `/history` with `Content-Security-Policy: sandbox`, so an uploaded HTML attachment can no longer run script on the team server's origin
- `test_python_build_module_available` skips when `build` is not installed, and the pytest rootdir test runs `python -P -m pytest` with the suite's own interpreter, so a contributor's first local run is green
- `testo config init` generates a `smoke-test` cycle that runs ordinary pytest tests in `tests/` without a marker filter. Marker-based pytest and BehaveX configurations remain as commented-out examples, so a new pytest project does not require smoke markers or BDD features (#100, thanks @evidentart)

## [1.2.0] - 2026-10-24

### Added
- `testo ingest`: record JUnit XML that any runner already wrote (Jest, Vitest, `go test`, JUnit5, ...) as a run of a cycle, with no `testosterone.yaml` needed. Ingested runs get the same history, Compare, `testo flaky`, reporters and PR comment as `testo run`. Backed by a new `equipment: junit` that runs no process and fails the stage when a test failed or no report matched
- Team server: `POST /api/v1/ingest` records uploaded JUnit XML, and `testo ingest --server URL --token` uploads with the CI job's provenance (provider, pipeline, job, commit, branch, repository). The API serves the built web UI when `TESTO_UI_DIR` is set. New `testo-server` Docker image (`Dockerfile.testo-server`, published with `testo-runner`) and `deploy/server/docker-compose.yml` with Postgres. Guide: `docs/Processes & Guides/Team Server.md`
- Playwright JSON reports: `testo ingest results.json` (and any `junit_xml` glob that matches a `.json` file) reads Playwright's `json` reporter output, keeping what JUnit loses: every retry as a step with its own error, flaky tests (passed on retry) flagged, and traces, screenshots, videos and `testInfo.attach()` files copied as Allure attachments. `testo ingest --server` uploads `.json` reports too. See `docs/Specs & ADRs/Playwright JSON Import - 2026-10-22.md`
- Unit tests for the Extent, ReportPortal and TestBeats reporters, the reporter factory, reporter config parsing and Docker results collection (recovered from an old branch)
- AI failure summaries without a paid key: an `openai_compatible` provider with a base URL, so Gemini, Groq, OpenRouter (free keys) or a local Ollama (no key) work. The settings page offers presets for them
- Flaky test detection: `testo flaky --cycle <name>` (`--window`, `--json`, `--fail-on-flaky`), `GET /api/v1/analytics/flaky` and a Flaky tests card on the cycle page (also in the Pages demo). A test is flaky when it both passed and failed and flipped at least twice in the cycle's last runs (`testo_core/services/flaky_service.py`)
- GitHub Action run summary: after a persisted run the action writes the results, failing tests and per-test changes since the previous run to the job summary, and with `comment-on-pr: "true"` keeps one comment per cycle on the pull request (edited in place). New inputs `job-summary`, `comment-on-pr`, `github-token` and `package`. The text comes from the new `testo report markdown` command. This repository's CI runs the action on its own checkout and comments on its own pull requests
- Plugin API: a package can add a test runner or a reporter through the `testo.frameworks` and `testo.reporters` entry point groups (`testo_core/plugins.py`), with no change to Testosterone. `testo plugins` lists built-ins and installed plugins (`--check` imports and verifies them, `--json`), and `examples/plugin/` is a complete plugin with a `unittest` adapter and a `json-summary` reporter
- `equipment: playwright`: runs `npx playwright test` with its JUnit and HTML reporters wired in, so Playwright tests count in summaries, diffs and the UI with no `junit_xml` setup, the HTML report is kept per run as the native report, and `workers` becomes `--workers`. Also offered on the Quick Run page
- Docs site: the `docs/` vault built with MkDocs Material (`mkdocs.yml`, `scripts/mkdocs_hooks.py`, `[docs]` extra) and published at <https://taltal-beep.github.io/testosterone/docs/> by the Pages demo workflow. A new `docs_site` CI job builds it with `--strict`
- JSON Schema for `testosterone.yaml` (`schema/testosterone.schema.json`, generated by `scripts/export_config_schema.py` and checked in CI) so VS Code and other editors autocomplete and validate the config. `testo config init` and `testo init` add the `# yaml-language-server: $schema=...` line
- Flaky test quarantine: a `quarantine:` list in `testosterone.yaml` (top-level and per cycle; test name globs, optional `reason` and `owner`). A stage that exits `1` passes when every failed test is quarantined; the failures are still reported everywhere and recorded per stage as `quarantined` (CLI summary, `--ci` NDJSON, run record, `testo report markdown`). `testo flaky` marks quarantined tests, prints a snippet for the rest, and `--fail-on-flaky` ignores quarantined ones (`testo_core/engine/quarantine.py`)
- `docs/project-review.md`: a whole-repo review scorecard (architecture, code quality, tests, security, docs, CI) with findings and a remediation plan, linked from the docs index and site nav
- `docs/Getting Started.md`: from `pip install testo-core` to a regression in `testo summary` and the GitHub Action, with the same project in `examples/getting-started/`. A new `getting_started` CI job runs that example through the GitHub Action

- Alerts where developers look: `slack` and `teams` reporters and a `testo notify --to slack|teams` command post a run's failing tests, new regressions, newly flaky tests and fixes to an incoming webhook (URL from `TESTO_SLACK_WEBHOOK_URL` / `TESTO_TEAMS_WEBHOOK_URL` or a `${env:…}` option; `--when failure|change|always`). `testo report annotations` prints failing tests as GitHub `::error` annotations on their file and line, and `testo flaky --new` lists tests the latest run made flaky. The GitHub Action gains `annotations` (on by default), `slack-webhook`, `teams-webhook`, `notify-when` and `flaky-issues` (opens one issue per newly flaky test)

### Changed
- `testo-api` refuses to start on a non-loopback host without `TESTO_API_TOKEN` (exit 2) instead of only warning; set `TESTO_ALLOW_UNAUTHENTICATED=1` to start anyway on a trusted network
- The `?config_path=` on read routes (`GET /api/v1/cycles`, `/cycles/{cycle}`, `/runs/{run_id}/pyramid`) only loads files named `testosterone.yaml`, `testosterone.yml` or `pyproject.toml` and returns `400` for anything else. Reads need no token, so an arbitrary path let anyone probe the server's files and read fragments of them in parse errors
- The API reports the installed package version instead of a hard-coded one
- CI: a `test (python 3.12)` / `test (python 3.13)` job runs the fast suite on the other Python versions `pyproject.toml` lists; BehaveX tests skip without the `bdd` extra
- CI: `trivy-action` and `claude-code-base-action` pinned to commit SHAs instead of `@master` / `@beta`; `commitlint`, `pr-heavy` and `release-gate` workflows get a read-only `permissions:` block
- AI settings (never the key) are saved to `artifacts/ai_settings.json` and survive an API restart (`TESTO_AI_SETTINGS_PATH` moves it; empty keeps them in memory). The settings page resets the model when the provider changes, names the missing environment variable and refuses a key pasted as a variable name. The summary prompt asks for a short plain-text `What failed` / `Likely cause` / `Next steps` reply, and the Run Details card shows provider errors in words
- `equipment: playwright` uses Playwright's `json` reporter instead of `junit` (`--reporter=list,json,html`, written to `test-results/testo-results.json`), so `testo run` gets the same retries, flaky flags and traces. A stage that sets its own `--reporter=junit` is still imported from `test-results/testo-junit.xml`
- **Behave and BehaveX are now an extra.** `pip install testo-core` no longer installs `behave`, `behavex` and `allure-behave` (35 packages instead of 47). **Migration:** if a cycle has `behave` or `behavex` stages, install `testo-core[bdd]`; in the GitHub Action pass `package: "testo-core[bdd]"`, and in the GitLab template set `TESTO_PACKAGE: "testo-core[bdd]"` (new variable). The `testo-runner` image and the `dev` extra include it. Without it a Behave stage fails with exit 3 and the stage error names the extra, which the CLI stage panel now shows (the `--ci` stream keeps it in the artifact event mirror, as before)
- README and PyPI description lead with what the project answers on every run (what broke, what's flaky, what got slower) and with `testo ingest` for any runner, next to running cycles; new PyPI keywords
- Web UI restyled after the Vision UI dashboard look: navy palette, glass cards over a blue glow, Plus Jakarta Sans, a desktop sidebar with icon tiles and a docs card, and icon tiles on the Dashboard KPI cards. Faint line art of the testosterone molecule and of vials with a syringe sits behind the pages. Phones keep the top bar and menu. See `docs/Specs & ADRs/UI Restyle - 2026-10-19.md`
- `publish.yml` publishes straight to PyPI (the Test PyPI step is gone; the build, metadata and clean-install checks still run before the upload) and can be run by hand for an existing release tag
- Runner image: `Dockerfile.testo-runner` uses the floating `python:3.11-slim-bookworm` base (the `3.11.9` pin carried 9 fixable CRITICAL Debian CVEs that failed the v1.1.1 image scan), and `docker-publish.yml` scans and smoke-runs the image before pushing it and can be run by hand for an existing release tag
- Setup prompts install `testo-core` from PyPI instead of the GitHub zip
- `move-major-tag.yml` keeps the moving `v1` tag on the latest stable release (and can be run by hand for an existing tag)
- README: a "What's new" section for the changes since 1.1.1, new screenshots and UI walkthrough of the restyled UI on real self-test and fake-api runs (including the flaky tests card), a terminal recording of `testo flaky`, `testo report markdown` and `testo plugins`, and the Playwright equipment, plugins, `testo report markdown`, `testo summary` and PR comments in the reference sections

### Fixed
- BehaveX stages get BehaveX's own HTML report again. The adapter passed BehaveX's Allure `--formatter`, and BehaveX skips `report.html` whenever a formatter is set, so the report Testo showed was re-rendered afterwards without scenario logs. BehaveX now runs plain and the executor converts its `report.json` to Allure results after the stage (`testo_core/reporting/behavex_allure.py`). A `--formatter` in a stage's `args` is still passed through
- New run-history records include the repository used by a run when its attempted stages have one resolved target; runs using multiple repositories leave it unknown.

### Removed
- Unused report helpers left from the Streamlit UI (removed in v1.1): `start_report_server`, `start_static_server`, `ReportServer`, `url_for`, `sync_all_reports_to_static` and `collect_behavex_native_report` in `testo_core/reporting/report_generator.py`, and a stray `actionlint_py` tarball at the repo root

## [1.1.1] - 2026-10-19

First release meant for PyPI (`pip install testo-core`).

### Added
- Open-source community files: `SECURITY.md` (private vulnerability reporting), `CODE_OF_CONDUCT.md` (Contributor Covenant 2.1), `CITATION.cff`, issue forms (`.github/ISSUE_TEMPLATE/*.yml`, blank issues off, links to Discussions and the security form) and `.github/dependabot.yml` (weekly grouped updates for pip, npm and GitHub Actions, `chore(deps)` commits with the `no-changelog` label; `commitlint.config.js` skips Dependabot's long commit bodies). `CONTRIBUTING.md` gains "Finding something to work on" and a note on the AI-agent files, and its Quickstart link is fixed
- README: animated walkthroughs of the web UI and of the CLI (`docs/assets/demo/`)
- `docs/Prompts & Snippets/Setup Prompts.md`: copy-paste prompts for an AI coding assistant to install Testosterone in another project, write its `testosterone.yaml`, run it in GitHub Actions or GitLab CI, open the web UI and troubleshoot. They install from GitHub until `testo-core` is on PyPI. Command Reference no longer calls `doctor`, `clean`, `watch` and `init` unimplemented

### Fixed
- A `pip install`ed `testo-core` no longer writes run data (`static/history/`, `static_reports/`) into `site-packages`: it goes to `./.testo/` in the working directory, or `$TESTO_HOME`. Source checkouts keep the repository root. The `package` CI job now fails if anything lands in `site-packages`
- `pip install testo-core` followed by `testo run` crashed with `ModuleNotFoundError: No module named 'sqlalchemy'`: run history is always saved (SQLite by default) but `sqlmodel` was only in the `[db]` extra. It is now a core dependency; `[db]` keeps the Postgres driver and `tomli-w`. A new `package` CI job (`scripts/package_smoke.sh`) installs the built wheel with no extras and runs a cycle, and the publish workflow runs the same check before uploading
- Compare showed "n/a" / "Unknown" for "Test time (sum)" and "Avg per test" on every run because nothing stored them. Both persistence backends now write `metrics_duration_ms` (sum of per-test Allure durations) and `avg_case_ms` (that sum over the test count, `null` with no tests), plus `test_time_ms` per stage. Runs saved earlier still show "n/a". A new contract test fails when `history/views.py` reads a run metadata key that persistence never writes

### Changed
- Package metadata for PyPI: description, MIT license expression, author, keywords, classifiers and project links (homepage, docs, demo, issues, changelog). The README shown on PyPI has its relative images and links rewritten to GitHub URLs at build time (`hatch-fancy-pypi-readme`), and the sdist now carries only the Python package, its tests and the top-level docs (about 260 KB instead of 3.5 MB)
- `publish.yml` fails before uploading when the release tag does not match `pyproject.toml`'s version, and runs `twine check --strict`
- README: PyPI badge and a `pip install testo-core` quickstart
- Pages demo: the read-only notice is now a dismissible alert with a × button, remembered across reloads, and a "Read-only demo" badge in the header reopens it
- Detailed architecture diagram (`docs/assets/testosterone-architecture-detailed-{dark,light}.png`, drawn by `scripts/render_architecture_diagram.js`) showing `CycleRunService`, the `history/` read side and the repository; it replaces the six-box picture in the README and leads `docs/Architecture/System Diagram.md`
- Docs vault: the architecture diagram now has its own note (`docs/Architecture/System Diagram.md`) so it shows in Obsidian and the GitHub wiki, not only the README; Architecture Overview's text sketch is a Mermaid flowchart. New decision note for the vault and wiki sync, the second wave of the 2026-10-07 interview fixes, and this repo's workflows in CI-CD Pipeline Setup. `scripts/docs_vault.py lint --base` accepts a second edit to a note already dated today

## [1.1.0] - 2026-10-07

One engine behind every surface. The Docker-based second execution stack, the Streamlit UI, MinIO and the `uqo` command are gone; the CLI, the API and CI all run cycles through `CycleRunService`. The release also adds an API security model, a type-checked API, same-cycle run comparison and a read-only demo on GitHub Pages. Upgrading from 1.0: see "Migrating from v1.0" in the README.

### Added
- Docs vault rules: `docs/CLAUDE.md` (schema), `docs/log.md`, frontmatter on every note, and `scripts/docs_vault.py lint` (frontmatter, broken links, wikilinks, orphans, `updated` date on edited notes) as a `docs_vault` CI job and a contract test. `.github/workflows/wiki-sync.yml` regenerates the GitHub wiki from `docs/` on every push to `main` that touches the vault. The root `CLAUDE.md` gains the six second-brain rules, and `docs/Specs & ADRs/` gains decision notes for the 2026-10-06 architecture consolidation and the 2026-10-07 interview fixes
- Pages demo on GitHub and GitLab: `.github/workflows/pages-demo.yml` (GitHub Pages, `https://<owner>.github.io/<repo>/`) and `.gitlab-ci.yml` (GitLab Pages) each run testosterone's own suite (`self-test` cycle) and the deliberately broken [fake-api](https://github.com/taltal-beep/fake-api) app (`fake-api` cycle), then publishes the React UI as a read-only snapshot of those runs (`scripts/export_static_site.py` freezes the API's own responses; `frontend/src/lib/static-backend.ts` serves them to the unchanged pages). Run history is cached between pipelines. `.github/workflows/mirror-to-gitlab.yml` mirrors `main` to GitLab, inert until configured
- `frontend` CI job in `ci.yml`: runs the React dashboard's typecheck, vitest suite and production build on every PR (the frontend had no CI coverage)
- `POST /api/v1/adhoc-executions`: run one framework (`pytest`, `behave`, `behavex`, `command`) against a repo without defining a cycle. It runs as a one-stage `adhoc` cycle through `CycleRunService`, with status and SSE events under `/api/v1/cycle-executions/{id}`
- Quick Run page in the React frontend (`/quick-run`, under Advanced) built on that endpoint; it replaces the Legacy Execution page
- Engine run records now store failure evidence for failed runs (failing cases, first traceback, log tail, timeout flag; all redacted) for the AI failure summary, and CI provenance (`ci_provider`, `ci_pipeline_id`, `ci_job_id`, `ci_commit_sha`, `ci_ref_name`) when run in CI
- After every cycle run, test KPIs are pushed to InfluxDB and/or a Prometheus Pushgateway when `INFLUXDB_*` / `PROMETHEUS_PUSHGATEWAY_URL` are set

### Changed
- Loose `testo_core` root modules moved into their subpackages (no compatibility shims): `db.py` → `repository/db.py`, `db_config.py` → `repository/db_config.py`, `report_generator.py` / `metrics.py` / `metrics_extractor.py` / `integrations.py` → `reporting/`, `triggers.py` → `config/triggers.py`. Only the cross-cutting `paths.py` stays at the root
- CI type-checks `testo_api` as well as `testo_core` (`mypy testo_core testo_api`, blocking). The AI config routes validate their status payload through Pydantic, and report diffs type the change kind as a `Literal`
- Pages demo explains itself: the banner says it shows testosterone's self-test and fake-api (whose red is deliberate), only cycles that ran are exported and their Run buttons are disabled with the local `testo run` command, the read-only message no longer names GitLab, and with an optional `ANTHROPIC_API_KEY` the export freezes an AI failure summary per failed run (otherwise the card says summaries are generated live)
- API access control: CORS now allows only the Vite dev/preview servers by default (`TESTO_CORS_ORIGINS`; credentials only for an explicit origin list, never with `*`) and mutating requests from other browser origins get `403`, optional `TESTO_API_TOKEN` requires a bearer token on mutating requests (the frontend sends `VITE_TESTO_API_TOKEN`), and `testo-api` warns when bound beyond loopback without a token. `ARCHITECTURE.md` gains "Security model" and "Trade-offs and known limits" sections
- Running a cycle (trigger gate, engine, reporters, native report snapshot, report archive, trigger snapshot) now lives in one application service, `testo_core/services/cycle_run.py` (`CycleRunService`). `testo run` and `POST /api/v1/cycles/{cycle}/executions` both call it, so the API no longer imports private helpers from `testo_core/cli/runner.py`
- API cycle executions now save the trigger snapshot after a successful triggered run, as `testo run` already did; before, a cycle with `trigger:` started from the dashboard never advanced its snapshot
- Frontend API types are now generated from FastAPI's OpenAPI schema (`frontend/openapi.json` → `frontend/src/lib/api-schema.ts`) instead of being hand-written; CI's `frontend` job runs `tsc` and fails on a stale schema or generated file
- `ARCHITECTURE.md` and `README.md` now describe the single execution engine (config → `CycleRunService` → engine → framework adapters → reporting/persistence) with a system diagram, layer table and the typed Pydantic-to-React contract
- `testo_core/run_history.py` is replaced by the `testo_core/history/` package: `views` (typed run views), `read_model` (queries), `report_links`, `snapshots` and `maintenance`. All of it goes through the run repository, which gains `merge_run_metadata()`; `STATIC_HISTORY_ROOT` moves to `testo_core.paths`
- GitHub Action and GitLab template now run `testo run --ci` (they called `uqo run --config … --ghost`, which v1.0's `uqo` alias no longer accepted). Action inputs are `config-path`, `cycle`, `ci-mode`, `persist`, `python-version`; `ghost-mode`, `stream-json`, `runner-image`, `runner-prebuilt` and the `run_id` output are gone. GitLab variables are now `TESTO_CONFIG_PATH`, `TESTO_CYCLE`, `TESTO_PERSIST`
- The React UI names runs by cycle and start time (`fake-api · Oct 7 03:21`) with the short run id as secondary text, on the Dashboard, Runs, Run detail and Compare pages; `GET /api/v1/dashboard/runs/recent` items now include `cycle`. Compare shows Reliability/Performance as tables with coloured deltas and state badges instead of raw `key=value` strings, and its run pickers are grouped and filterable by cycle
- CI's `format` job now blocks on `mypy testo_core` and `ruff format --check` (both were advisory); the codebase was reformatted once with `ruff format`, and a `ruff-format` pre-commit hook was added
- A stage's `workers` now does what it says, or says it doesn't: pytest stages get `-n <workers>` when pytest-xdist is installed for the `pytest` on PATH (otherwise one warning and a serial run), `workers:` on a behave or command stage logs a warning, and the API/UI only show workers for frameworks that use them
- CI's `test` job now enforces coverage (it ran `--no-cov`): `pytest.ini` measures `testo_core` and `testo_api` with branch coverage and fails below 65% (was 50%, `testo_core` only), and `coverage.xml` is uploaded as an artifact. `nightly-external`, `release-gate` and `pr-heavy` pass `--no-cov`: their few marker-selected tests could never meet that project-wide gate, which is why `nightly-external` failed every night. `nightly-external` also reads `TESTO_E2E_*` secrets instead of `UQO_E2E_*` and skips with a notice when none are set
- Renamed the remaining UQO names in code and UI to Testosterone: tab title, OpenAPI title (`Testosterone API`), and env vars `UQO_*` → `TESTO_*` (`TESTO_SHARED_ALLURE_RESULTS_DIR`, `TESTO_ARTIFACTS_ROOT`, `TESTO_LAST_TEST_TYPE`, `TESTO_RUN_ID`, `TESTO_E2E_*`, runner image build args) with no aliases for the old names. Defaults changed too: `PROMETHEUS_JOB_NAME` is `testo`, metrics are `testo_*` / `testo_test_run`, the default SQLite history file is `testo_history.db`, and the compose Postgres is `testo-postgres` / `testo_admin` / `testo_history`

### Removed
- MinIO support: the `s3` readiness check (`/api/v1/health/ready` reported "degraded" without MinIO credentials), `testo_core/s3_client.py`, `history/s3_snapshots.py` (pre-v1.1 snapshot reads), the pre-v1.1 record shape in `history/views.py`, the `boto3` dependency, and the `minio`, `minio-init`, `allure-sync` and `allure` compose services. `docker-compose.yml` now only provides Postgres
- The second, Docker-based execution stack: `HeadlessEngineService`, `testo_core/runners.py`, `command_builders.py`, `multi_run.py`, `event_drain.py`, `config_loader.py`, `audit_service.py`, `ghost_policy.py`, `result_management.py`, and the pluggy `orchestrator.py` / `specs.py` / `plugins_builtin.py`. Every run now goes through the cycle engine
- The v1.0 `uqo run --config <runs.yaml>` contract (`--ghost`, `--no-ghost`, `--json`, `--stream-json`, summary JSON); use `testo run --cycle <name> --ci`
- The `uqo` console script (`testo_core/cli/deprecated.py`) and the frontend's legacy route redirects (`/history`, `/runner`, `/execution`, `/advanced/execution`); use `testo` and the current routes. Unknown frontend paths now show a not-found page
- `POST /api/v1/executions`, `GET /api/v1/executions/{id}` and `GET /api/v1/executions/{id}/events`; use `POST /api/v1/adhoc-executions` or `POST /api/v1/cycles/{cycle}/executions`
- The Streamlit UI (`testo_ui/`, `testo-ui` script, `ui` extra), as scheduled in 1.0.0
- The `docker` extra and the `pluggy` runtime dependency
- Run-history writer functions in `run_history.py` (`create_run`, `record_completed_run`, MinIO uploads), the unused `compare_latest_two()` and the `db_path` arguments on history queries
- Generated run output that was committed by mistake (`artifacts/allure-report*`, `artifacts/allure-results-archive/`, `artifacts/metrics.json`); these paths are now ignored
- `testo_core/reporting/allure_delta_transform.py`, `allure_history_serve.py` and `allure_summary_widgets.py`: unreferenced modules that could not be imported (they depended on functions no longer in `services/report_archive_diff.py`)
- Dead code and test-failure injection: `.streamlit/`, `drop_in_hooks/`, `requirements.txt`, `deploy/nginx/`, `examples/gitlab/`, the unused GitLab tier templates, `sample_target_repo/random_fail.py` and the `sample-all-frameworks-stochastic` cycle, and the `UQO_FLAKY_DEMO` / `SANDBOX_API_FLAKY_P` switches in testosterone's own suite. `testo_core/sandbox_api.py` (a uvicorn launcher for the sample mock API, used only by one black-box test on a fixed port) is gone with that test, so it no longer ships in the wheel

### Fixed
- Dashboard and Compare badges say "1 improvement" / "1 regression" instead of "1 improvements"
- `release-gate.yml` reads the `TESTO_E2E_*` repository secrets, matching the nightly job, instead of the old `UQO_E2E_*` names
- Errors in I/O and reporting paths are no longer swallowed silently: `except Exception: pass` sites in `testo_core/` and `testo_api/` now catch the specific exceptions they expect and log with the module logger, and the deliberate catch-alls (orchestrator, reporter factory, API routes) log with a traceback. A failed BehaveX HTML report now sets the stage's `error` and is written to `run.log`, and a failed Git trigger evaluation logs a warning and says so in the trigger `reason` (exit codes unchanged)
- The frontend's top nav overflowed the page at phone width. Below 640px the nav links and the Advanced menu now collapse into a menu button (`aria-expanded`, closes on navigation and Escape), and page gutters shrink to 16px; no page of the demo scrolls sideways at 390px any more
- Dashboard trends and "Compare latest two" (dashboard and Runs page) compared the latest run with whatever ran before it, even another cycle; the baseline is now the previous run of the same cycle, and the dashboard names it. A cycle whose stage crashed without producing results no longer reports the other stages' pass rate (often 100%) as its health
- The API's execution registry kept every execution in memory forever and each SSE viewer held a worker thread while polling `events.ndjson` every 0.2 s. Finished executions beyond `TESTO_MAX_FINISHED_EXECUTIONS` (default 200) are now evicted (their status/events endpoints return 404 pointing to `/api/v1/runs`); the SSE tail is an async generator with poll backoff (0.1 s to 2 s) that closes right after the run's own last event (not the next run's, which shares `events.ndjson`) or when the client disconnects, and no longer drops a line caught mid-write
- The test pyramid (`testo report pyramid`, `/api/v1/runs/{id}/pyramid`) bucketed a run by the tiers in the *current* `testosterone.yaml`, so renaming a stage re-counted old runs as "unit". Run records now store each stage's `tier`; only older records without one fall back to the YAML
- A `command` stage's `junit_xml:` reports were never imported by `testo run` or the API, so the stage showed 0 tests and PASS. Cycle resolution and the `--workers` override rebuilt each stage without its `junit_xml` and `tier`; they now copy the stage with `dataclasses.replace`
- Pytest stages ignored the target repo's own pytest config (`pythonpath`, markers) when the target sat inside another pytest project, such as a repo cloned into the testosterone checkout in CI, so tests failed to import the target's code. The adapter passed `--alluredir <path>` as two tokens, and pytest counted the results path when choosing its rootdir; it now passes `--alluredir=<path>`
- Compare's test-level changes were always empty for two runs of the same cycle, and a run's artifact download returned whichever run of that cycle came last. Run records pointed `snapshot_dir` at the shared `artifacts/<cycle>/` tree, which every run overwrites; each run now keeps its own copy at `static/history/<run_id>/artifacts/`
- Frontend typecheck errors surfaced by the generated types: `/health/ready` is typed `"ready" | "degraded"` as the API returns, and `StatusPill` handles a `null` status
- `mypy testo_core` reports 0 errors, down from 59: reporters take a typed Rich `Console`, `testo report` narrows its optional open path before use, and the persistence, repository and CLI UI code is fully annotated
- `equipment: behavex`: every BehaveX stage failed at startup with `OSError: AF_UNIX path too long`, because BehaveX points `TEMP` at its output folder and the multiprocessing socket landed there; the adapter now pins `TMPDIR` to the system temp dir
- API errors surfaced in the UI as `API error <status>`; the client now shows the message the API returned, and the Run detail page reports a failed AI-summary request instead of swallowing it
- Run detail, dashboard and compare showed a wall duration of 0 ms for every cycle run; engine-sourced records store `duration_s`, which the history view now falls back to

---

## [1.0.0] - 2026-09-27

First public release. Published to PyPI (`testo-core`), GHCR (`testo-runner`), and JFrog Artifactory.

### Deprecated
- `testo-ui` / Streamlit interface: prints a deprecation notice on stderr and is scheduled for removal in v1.1. The React frontend (`frontend/`) is the official UI.
- `uqo` CLI alias: continues to forward to `testo`; removal in a future release.

### Added
- `.pre-commit-config.yaml`: local `ruff`, changelog-format, and whitespace/YAML/TOML hooks (`pre-commit install` to enable)
- `mypy` type-check tooling: `[tool.mypy]` config in `pyproject.toml`, advisory step in `ci.yml`'s `format` job
- Extended `[tool.ruff.lint]` selection (added `UP`, `B`) and made `ruff check` blocking in `ci.yml` now that the tree is clean
- `changelog_required` CI gate in `ci.yml`: fails PRs with non-doc changes that don't touch `CHANGELOG.md` (escape hatch: `no-changelog` label)
- `commitlint` CI check (`.github/workflows/commitlint.yml`, `commitlint.config.js`) enforcing Conventional Commits on PR commit messages
- `changelog-on-main.yml`: AI-drafted `CHANGELOG.md [Unreleased]` entries on push to `main`, gated by `scripts/check_changelog_format.py` — see `docs/changelog_automation_policy.md` for the review-step tradeoff and required secrets/branch-protection setup
- `CONTRIBUTING.md`, `.github/PULL_REQUEST_TEMPLATE.md`, `.github/ISSUE_TEMPLATE/` (bug report, feature request), and `CODEOWNERS`
- Root-level `CLAUDE.md` pointing any directly-invoked AI agent at `docs/Index.md` and the Agent Context Guide
- Persistence module with `PersistenceBackend` protocol, JSON and DB backends
- Single-sourced `EngineExitCode` across modern and legacy execution stacks
- Contract tests asserting exit code consistency between stacks
- Execution stack boundary documentation in Architecture Overview
- `_SENSITIVE_KEY_PATTERN` in `redaction.py` to detect sensitive mapping keys (#35)
- `_redacted_context_text()` in `failure_context_builder.py` for structured metadata redaction (#35)
- Allure failure context wiring in `record_completed_run()` for run recording (#35)
- `equipment: command`: run any test runner (Jest, Playwright, Maestro, `go test`, ...) as a stage. `args` is the full argv
- Stage key `junit_xml` (glob or list, relative to `target_repo`): JUnit XML written by the stage is converted into Allure results after it exits, so non-Allure runners count in summaries, health % and every reporter (`testo_core/reporting/junit_import.py`)
- `artifactory-publish.yml`: mirrors the release to JFrog Artifactory (PyPI + Docker repos), inert until `ARTIFACTORY_URL` is set — see `docs/Processes & Guides/Publishing to Artifactory.md`

### Changed
- `--no-persist` / `--persist` CLI flags with clarified semantics
- `classify_exit_code` consolidated into `engine/exit_codes.py`
- Literal exit code constants in CLI replaced with `EngineExitCode` enum

### Fixed
- Sprint 2 release gate execution across all 4 phases
- Contract test assertion mismatch (`--plan` vs `--cycle`)
- Allure CLI unit test mock for `resolve_allure_command`
- `publish.yml`: post-publish verification installed `testo-core==v1.0.0` from the raw git tag, which is not a valid version specifier; the leading `v` is now stripped
- `docker-publish.yml`: Trivy scan and verify steps referenced an image tag that never existed (`docker/metadata-action` strips the `v`); both now use the resolved metadata version
- `docker-publish.yml`: the `latest` tag was gated on `is_default_branch`, which is never true for a release event, so `latest` would never have been published
- `.gitattributes`: GitHub reported the repository as HTML because the generated 3.2 MB `artifacts/allure-report/index.html` outweighed all authored Python and TypeScript; generated and vendored paths are now excluded from language statistics
- `Dockerfile.testo-runner`: the image ran as root, which fails the release workflow's blocking Trivy config scan (DS002, HIGH); it now runs as an unprivileged `testo` user, and the entrypoint is `testo` instead of the deprecated `uqo` alias

---

## [0.1.0] — Phase 1–4 Feature Complete

### Phase 4: BYOK AI Failure Summaries

*AI-powered test failure analysis with bring-your-own-key provider support.*

#### Added
- `testo_core/services/failure_analysis_service.py` — context-aware AI failure summary generation
- `PUT /api/v1/ai/config` — runtime AI provider/model configuration (memory-only key storage)
- `GET /api/v1/runs/{run_id}/ai-summary` — cached AI summary retrieval
- `POST /api/v1/runs/{run_id}/ai-summary:generate` — on-demand summary generation for failed runs
- `GET /api/v1/ai/config/status` — non-secret AI configuration status endpoint
- React AI Settings page (`/settings/ai`) — provider config, key management, model selection
- AI summary display on Run Detail page (`/runs/:runId`)
- AI summary caching — generate once, retrieve cached on refresh
- AI failure context capture tests
- Passing-run AI summary skip regression test

#### Security
- Raw API keys never returned by backend responses
- Runtime key input memory-only by default (not persisted to DB/files)
- Token-like values redacted from internal error surfaces before transport
- AI integration explicit opt-in (`enabled=false` by default)

#### Fixed
- AI summary refresh data loss on forced refresh failure (#32)
- AI failure summary and context builder regression coverage (#33, #34)

---

### Phase 3: Unified Dashboard, Delta Engine, Frontend Migration

*React frontend, run comparison analytics, and unified dashboard.*

#### Added
- FastAPI backend (`testo_api/`) — thin adapter over `HeadlessEngineService`
- React frontend (`frontend/`) — Vite + React + Tailwind dashboard
- Dashboard overview page (`/`) — KPI cards, trend badges, drill-down links
- Delta comparison engine (`testo_core/services/delta_service.py`) — regression/improvement classification
- Compare page (`/compare`) — run selection and delta visualization
- SSE client (`frontend/src/lib/sse-client.ts`) — real-time execution log streaming
- `GET /api/v1/dashboard/overview` — unified dashboard payload endpoint
- `GET /api/v1/analytics/delta` — core-owned run delta comparison endpoint
- `POST /api/v1/executions` — create run execution job endpoint
- `GET /api/v1/executions/{id}/events` — SSE stream for log/result/summary events
- Health probes: `GET /api/v1/health/live`, `GET /api/v1/health/ready`
- Degraded-data behavior (n/a display, degraded banner, missing report links)
- Report DB archives, diff CLI, Allure history, hybrid cycles
- Report archive extraction path hardening (#28, #30)
- Report archive diff regression tests (#27, #29)
- Execution accepted-status regression test (#26)
- Frontend unit tests (Vitest) and E2E test harness

#### Fixed
- Race condition in 202 Accepted response status for `/executions`

---

### Phase 2: CI Integrations, Ghost Mode, Runner Image

*CI wrappers, headless ghost execution, and prebuilt Docker runner.*

#### Added
- GitHub Action wrapper (`ariel-evn/uqo-action@v1`) with typed inputs/outputs
- GitLab CI template (`ci/gitlab/testo.gitlab-ci.yml`)
- Ghost mode — CI auto-detection for GitHub, GitLab, Buildkite, CircleCI, Jenkins, Azure Pipelines
- `--ghost` / `--no-ghost` / `--ci` CLI flags with precedence rules
- `Dockerfile.testo-runner` — prebuilt runner image for CI execution
- Configurable runner image path (`UQO_RUNNER_IMAGE`)
- NDJSON event streaming (`--stream-json`) for CI log consumption
- Ghost summary and NDJSON contract tests
- CI provenance unit tests
- GitHub Action and GitLab wrapper contract tests

#### Changed
- Renamed `uqo`-prefixed CI files to `testo`-prefixed

---

### Phase 1: Foundation

*Core engine, CLI, packaging, database adapters, Allure reporting.*

#### Added
- `testo_core/` — config-driven orchestration engine reading `testosterone.yaml`
- `testo` CLI entrypoint (via Typer) with `run`, `report`, `cycles`, `config` subcommands
- `uqo` legacy CLI alias (deprecated)
- Framework adapters: `PytestAdapter`, `BehaveAdapter`, `BehaveXAdapter`
- Repository pattern (`testo_core/repository/`) — SQLite default, Postgres/MySQL optional
- Allure reporting pipeline with per-framework isolation and unified reports
- MinIO S3 artifact storage (`testo_core/s3_client.py`)
- Docker-based ephemeral test execution (`testo_core/runners.py`)
- Dockerless local fallback when Docker is unavailable
- Streamlit UI (`testo_ui/`) for interactive execution and history
- Pluggy-based plugin system for drop-in runner extensions
- Shared headless engine service (`testo_core/services/headless_engine.py`)
- Hatchling-based packaging (`pyproject.toml`) with extras: `ui`, `api`, `db`, `docker`, `metrics`, `dev`
- Stable exit codes: 0 (success), 1 (test failure), 2 (invalid input), 3 (infra failure), 4 (internal error)
- Crash recovery: orphaned `RUNNING` rows auto-marked `FAILED` on startup
- Container timeout safety net (`UQO_CONTAINER_TIMEOUT_S`)
- Docker Compose infrastructure: Postgres, MinIO, Allure static host, Allure sync

#### Fixed
- Docker runner path mapping
- Mock API and built-in Pluggy hooks restoration
- Multi-run batch locking until complete
- Multi-run polling active until batch ends

---

[Unreleased]: https://github.com/taltal-beep/testosterone/compare/v1.5.0...HEAD
[1.5.0]: https://github.com/taltal-beep/testosterone/compare/v1.4.0...v1.5.0
[1.4.0]: https://github.com/taltal-beep/testosterone/compare/v1.3.0...v1.4.0
[1.3.0]: https://github.com/taltal-beep/testosterone/compare/v1.2.0...v1.3.0
[1.2.0]: https://github.com/taltal-beep/testosterone/compare/v1.1.1...v1.2.0
[1.1.1]: https://github.com/taltal-beep/testosterone/compare/v1.1.0...v1.1.1
[1.1.0]: https://github.com/taltal-beep/testosterone/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/taltal-beep/testosterone/compare/v0.1.0...v1.0.0
[0.1.0]: https://github.com/taltal-beep/testosterone/releases/tag/v0.1.0
