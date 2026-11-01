---
type: reference
status: current
created: 2026-06-25
updated: 2026-11-01
---

# Command Reference

Entry point: **`testo`** (`pyproject.toml` → `testo_core.cli.app:main`).

Parent index: [Index](../Index.md). Architecture: [Architecture Overview](../Architecture/Architecture%20Overview.md). Run lifecycle: [QA Strategies](../Testing%20Workflows/QA%20Strategies.md).

```bash
testo --help
```

Help is grouped into panels: **Run and report**, **Config**, **Diagnostics**, **Maintenance**, **About**.

Extras: `pip install testo-core` is the CLI with pytest, Playwright, `command` and `junit` stages. Add `[bdd]` for `behave` and `behavex` stages (Behave, BehaveX and Allure-Behave), `[api]` for the REST API and UI backend, `[db]` for Postgres or MySQL, `[metrics]` for InfluxDB, `[otel]` for [OpenTelemetry export](#testo-otel). A `behave` stage without the extra fails with exit `3` and `executable not found: behave (... pip install 'testo-core[bdd]')`.

---

## `testo run`

Execute one cycle or all cycles from `testosterone.yaml`.

```bash
testo run --cycle sample-pytests
testo run --cycle sample-pytests --ci
testo run --cycle sample-pytests --stream
testo run --cycle sample-pytests --workers 8 --force
```

### Options

| Flag | Short | Description |
|------|-------|-------------|
| `--cycle` | | Cycle name from `cycles:`; use `all` for every cycle (sorted), each trigger evaluated separately |
| `--plan` | `-p` | Deprecated alias for `--cycle` (hidden) |
| `--config` | `-c` | Path to `testosterone.yaml` (default: discovery) |
| `--stream` | | Tail each stage stdout live (vs post-mortem Rich panel) |
| `--ci` | | NDJSON events on stdout instead of Rich UI |
| `--no-persist` | | Skip optional run-history DB writes |
| `--no-report-db` | | Skip archiving cycle artifacts to report DB after run |
| `--async-report-db` | | Archive in background thread with join timeout; **ignored when `--ci` is set** |
| `--workers` | `-w` | Override parallel workers (e.g. BehaveX); 1 or more |
| `--force` | `-f` | Run even when trigger would skip the cycle |
| `--coverage` | | Code coverage report the tests write (repeatable): Cobertura or JaCoCo XML, LCOV, or a Go cover profile. Read when the stages finish; its line coverage is stored with the run and shown on the run page, the [PR comment](#testo-report) and the [digest](#testo-notify). A missing file only logs a warning. Not with `--cycle all` |

> [!warning] Roadmap flags — not implemented yet
> `--tag`, `--fail-fast`, `--dry-run` and `--reporter` were previously listed here but are **not present in `testo_core/cli/commands/run.py`**. The API layer already accepts `fail_fast` and `reporter_override` on `POST /api/v1/cycles/{cycle}/executions` (surfaced in the React Run panel); the CLI flags remain roadmap items. (Doc corrected 2026-07-04 during the Phase 5 UI redesign.)

Only one run of a cycle uses its artifacts folder at a time. A second `testo run` of the same cycle (another terminal, another CI job on the runner, the API) waits and says `another run of cycle 'x' is using ... (pid N); waiting for it to finish`; see [Engine Fixes - 2026-11-01](../Specs%20&%20ADRs/Engine%20Fixes%20-%202026-11-01.md).

### Expected terminal output

**Interactive (default):** Rich panels for plan start, each stage, and finish. On success:

```text
Run finished successfully.
```

On failure:

```text
Run exited with code 1.
```

**`--ci`:** One NDJSON object per line (`plan_started`, `stage_started`, `stage_finished`, `plan_finished`, etc.), no Rich styling.

### Exit codes

See [Architecture Overview § Exit code contract](../Architecture/Architecture%20Overview.md#exit-code-contract). `testo run` returns the engine exit code directly.

---

## `testo ingest`

Record test results that another step already wrote (any runner, any language) as a run of a cycle. Nothing is executed: the files are parsed into the same run history as `testo run`, so Compare, trends, `testo flaky`, reporters and the PR comment work on them.

```bash
testo ingest 'reports/**/*.xml' --cycle web-unit          # record locally
testo ingest junit.xml --cycle api --tier integration --ci
testo ingest test-results/results.json --cycle web-e2e --stage e2e --tier e2e   # Playwright JSON
testo ingest allure-results --cycle api                    # a folder: the files in it
testo ingest                                               # find the result files, cycle = folder name
testo ingest 'reports/*.xml' --cycle web-unit \
  --server https://testo.example.com --token "$TESTO_API_TOKEN"   # team server
```

| Flag | Default | Meaning |
|------|---------|---------|
| `REPORTS...` | found | Files, folders (their files) or quoted globs, relative to `--repo` (absolute paths must be inside it). Each file is recognised by its content; see the table below. None given: every result file under `--repo` that git doesn't track (fixtures are tracked) and isn't in a dependency folder (`node_modules`, `.venv`, ...); exit `2` when there is none |
| `--cycle` | folder name | Cycle name the run is recorded under: letters, digits, `.`, `_`, `-`. Reuse it so runs build a history. Default: the `--repo` folder's name, as `testo init` and `pytest --testo` use |
| `--stage` | `junit` | Stage name the tests are grouped under |
| `--tier` | `unit` | Test-pyramid tier: `unit`, `integration`, `e2e` |
| `--repo` | `.` | Directory the report paths are relative to |
| `--config` / `-c` | discovered | `testosterone.yaml` for `reporters:` and paths; not required |
| `--ci` | off | NDJSON events on stdout, as `testo run --ci` (with `--server`: one `ingest_uploaded` event) |
| `--no-persist` | off | Parse only, record nothing |
| `--server` | `$TESTO_SERVER_URL` | Upload to a [team server](../Processes%20&%20Guides/Team%20Server.md) instead of recording locally |
| `--token` | `$TESTO_API_TOKEN` | The server's API token |
| `--coverage` | none | Code coverage report to store with the run (repeatable, relative to `--repo`), as `testo run --coverage`. Checked first: no match or an unknown format is exit `2`. With `--server` only the totals are sent (the server recomputes the percentage) |

Files it reads, with the command that writes each one (no extra package needed except where noted):

| Runner | Write results with | Read as |
|--------|--------------------|---------|
| pytest | `pytest --junitxml=junit.xml` (or [`pytest --testo`](#pytest---testo)) | JUnit XML |
| Jest | `npx jest --json --outputFile=jest.json` (or `equipment: jest`) | Jest JSON: `describe` blocks, retried tests flagged flaky, test files that failed to load. Prefer it to `jest-junit`, which drops a test file that fails to compile |
| Vitest | `npx vitest run --reporter=json --outputFile=vitest.json` (or `equipment: vitest`) | Jest-style JSON, labelled `vitest` |
| Playwright | `npx playwright test --reporter=json` (`PLAYWRIGHT_JSON_OUTPUT_FILE=results.json`) | Playwright JSON: retries, flaky tests, traces |
| Cypress | `npx cypress run --reporter junit` (or `equipment: cypress`) | JUnit XML |
| Mocha, WebdriverIO | their `junit` reporter | JUnit XML |
| JUnit 4/5, TestNG, Kotest (Maven, Gradle) | built in: `target/surefire-reports/*.xml`, `build/test-results/**/*.xml` | JUnit XML |
| .NET (xUnit, NUnit, MSTest) | `dotnet test --logger trx` | TRX: data rows one result each |
| Go | `go test -json ./... > go-test.json` | `go test -json`: subtests, build failures as broken |
| Rust | `cargo nextest run --profile ci` with JUnit output configured | JUnit XML |
| PHPUnit, Pest | `--log-junit junit.xml` | JUnit XML |
| RSpec | `rspec --format progress --format json --out rspec.json` | RSpec JSON: failure class and backtrace, pending examples as skipped, load errors as broken |
| Minitest | `minitest-reporters` | JUnit XML |
| XCTest, Swift Testing (Xcode 16+) | `xcrun xcresulttool get test-results tests --path Tests.xcresult > xcresult.json` after `xcodebuild test -resultBundlePath Tests.xcresult` | `xcresulttool` JSON: failure messages, retries flagged flaky |
| Android instrumentation (Espresso, UI Automator, Compose) | built in: `./gradlew connectedAndroidTest` writes `app/build/outputs/androidTest-results/connected/**/*.xml` | JUnit XML, labelled `android` with the device it ran on |
| k6 | `k6 run --summary-export=k6-summary.json script.js` (or `JSON.stringify(data)` from `handleSummary`) | k6 summary: each check and each threshold is one result |
| Robot Framework | `robot` (writes `output.xml`) | Robot `output.xml`: tags, failure messages |
| GoogleTest, Catch2 | `--gtest_output=xml:gtest.xml`, `-r junit` | JUnit XML |
| Anything with an Allure adapter | its `allure-results/` folder | Allure results, with their attachments |

A file that is none of these is skipped with a note in the stage log. See [Runner Coverage - 2026-10-26](../Specs%20&%20ADRs/Runner%20Coverage%20-%202026-10-26.md).

Exit codes follow `testo run`: **0** every test passed or was skipped, **1** a test failed or broke, or every matching file was unreadable (truncated, empty, not a report), **2** bad arguments or no file matched, **3** the server could not be reached or refused the upload (wrong token). With `--server`, the job's CI provenance (provider, pipeline, job, commit, branch, repository) is sent with the files. Under the hood this is a one-stage cycle with `equipment: junit` run through `CycleRunService`; see [Ingest and Team Server - 2026-10-22](../Specs%20&%20ADRs/Ingest%20and%20Team%20Server%20-%202026-10-22.md). For Playwright JSON (each retry as a step, flaky tests flagged, traces and screenshots copied from inside `--repo` as Allure attachments) see [Playwright JSON Import - 2026-10-22](../Specs%20&%20ADRs/Playwright%20JSON%20Import%20-%202026-10-22.md).

---

## `testo report`

Build unified Allure reports from artifacts; subcommands for archives and native framework HTML.

```bash
# Default: generate + local Allure dashboard (opens browser unless --no-open)
testo report --cycle sample-pytests

testo report --generate-only --out artifacts/report
testo report --format json --summary-out summary.json
testo report list
testo report open --id <uuid>
testo report compare
testo report native
testo report native flow-tests --no-open
testo report pyramid <run-id>
```

### Default callback options

| Flag | Short | Default | Description |
|------|-------|---------|-------------|
| `--artifacts` | `-a` | `artifacts` | Artifacts root |
| `--cycle` | | latest | Restrict to one cycle |
| `--generate-only` | | false | Write HTML only; no HTTP server |
| `--host` | | `127.0.0.1` | Allure dashboard host |
| `--port` | | `8080` | Port (auto-picks free port if busy; `0` = always free) |
| `--out` | `-o` | `artifacts/report` | Generated HTML output dir |
| `--format` | `-f` | `html` | `html`, `json`, or `junit` |
| `--summary-out` | | | Path for json/junit summary file |
| `--no-history` | | false | Skip injecting prior Allure history |
| `--open` / `--no-open` | | open | Start dashboard after generate |
| `--trend` | | `1` | Merge history from N prior archived runs |

**Typical success output:** messages about collecting results, running `allure generate`, and a local URL such as `http://127.0.0.1:8080/...`.

### Subcommands

| Command | Purpose |
|---------|---------|
| `testo report list` | Table of archived runs (needs DB); columns: id, cycle, created, exit, tests, pass, fail |
| `testo report open --id <uuid>` | Extract archive and regenerate/serve Allure |
| `testo report compare` | Rich diff + Allure comparison (optional baseline/current UUIDs) |
| `testo report native [ROUTINE]` | List or open BehaveX/pytest native HTML under stage dirs |
| `testo report markdown [--cycle NAME \| --run-id ID] [--out FILE] [--run-url URL] [--baseline-branch BRANCH]` | The cycle's latest run (or one run) as GitHub-flavored Markdown: headline counts, per-stage table, failing tests, and per-test changes since its baseline: the latest run on `--baseline-branch`, else on the pull request's recorded target branch (`ci_base_ref`), else the cycle's previous run. When the run stored [coverage](#options), the headline adds it and its change against the same baseline (`coverage 81.2% (▼ 0.4)`). The first line is a hidden `<!-- testo-summary:<cycle> -->` marker. Exit `2` when no run is recorded. The GitHub Action uses it for the job summary and the PR comment |
| `testo report annotations [--cycle NAME \| --run-id ID] [--workspace DIR] [--limit N] [-c CONFIG]` | The run's failing tests as GitHub Actions `::error file=…,line=…` workflow commands, so each failure shows on its line in the pull request's "Files changed". The location is the first stack-trace frame inside `--workspace` (default `.`), tried relative to the workspace, each stage's `target_repo` from the config, and the run's target repo. At most `--limit` (default `10`, GitHub's per-step cap) lines, then a `::notice` with the rest. Exit `2` when no run is recorded. The GitHub Action prints it by default. See [Alerts Where Developers Look - 2026-10-22](../Specs%20&%20ADRs/Alerts%20Where%20Developers%20Look%20-%202026-10-22.md) |
| `testo report pyramid RUN_ID [-c CONFIG]` | ASCII unit/integration/e2e test pyramid for a completed run (`run_id`, not the archive UUID); stage→tier is the stage's `tier:` (default inferred from `equipment`: pytest→unit, behave→integration, behavex→e2e, playwright→e2e, jest→unit, vitest→unit, cypress→e2e) as recorded in the run when it executed; `-c` is only read for older runs that predate recorded tiers. See [Architecture Overview § Test pyramid](../Architecture/Architecture%20Overview.md#test-pyramid). |

---

## `testo cycles` (alias: `testo plans`)

Inspect cycles in config (hidden alias `plans` for backward compatibility).

```bash
testo cycles list
testo cycles show sample-pytests
testo cycles show sample-pytests -c ./testosterone.yaml
```

**`list`:** Rich table — Name, Description, stage count.

**`show`:** Cycle title plus table of stages (equipment, target repo, args, timeout).

Config errors print `[fail]config error: …` and exit **2**.

---

## `testo config`

| Subcommand | Description |
|------------|-------------|
| `testo config validate` | Load YAML; optional `--check-executables` for pytest/behave/behavex (and `npx` for playwright, jest, vitest and cypress) on PATH. Warns about keys nothing reads (`unknown key 'cycles.web.stages[0].timout_s' is ignored; did you mean 'timeout_s'?`); `--strict` makes them an error (exit 2) |
| `testo config init` | Write starter `testosterone.yaml` with one active `smoke-test` cycle running `pytest -q tests` and commented-out marker/BehaveX examples (`--path`, `--force`) |
| `testo config db` | Set `database.url` (PostgreSQL prompts or `--url`) |

```bash
testo config validate
testo config validate --no-check-executables
testo config validate --strict   # unknown keys fail, for CI
testo config init --path testosterone.yaml --force
testo config db --url sqlite:////tmp/testo-reports.db
```

**Validate success:**

```text
ok — version=1 cycles=6 reporters=4 defaults_target=.
```

**Deprecated:** `testo config-db` → use `testo config db`.

### Editor autocomplete

`schema/testosterone.schema.json` is a JSON Schema for `testosterone.yaml`. Editors with a YAML language server (VS Code with the Red Hat YAML extension, JetBrains IDEs, Neovim) then suggest keys and built-in equipment, and underline typos as you type. `testo config init` and `testo init` add this line at the top of the file; add it yourself to an existing config:

```yaml
# yaml-language-server: $schema=https://raw.githubusercontent.com/taltal-beep/testosterone/main/schema/testosterone.schema.json
```

`testo config validate` is still the final word. The schema describes the `cycles:` layout only, and accepts plugin equipment and reporter names. Why and how it is generated: [Config JSON Schema](../Specs%20&%20ADRs/Config%20JSON%20Schema%20-%202026-10-22.md).

---

## `testo diff` / `testo summary`

Compare two archived report runs by UUID (from `testo report list`).

```bash
testo diff <BASELINE_ID> <CURRENT_ID>
testo summary   # same family; see help for metrics-only variants
```

Rich terminal diff of metrics and (for full diff) extracted Allure deltas. Reads the run history database (SQLite by default; `testo-core[db]` for Postgres).

Prefer **`testo report compare`** for Rich diff plus Allure visual comparison pipeline.

Note: this operates on `ReportArchive` UUIDs (`testo report list`), a separate id space from run-history `run_id`s — see [Architecture Overview § Persistence](../Architecture/Architecture%20Overview.md#persistence). The React Compare page (`GET /api/v1/analytics/delta` + `/analytics/delta/cases`) reaches equivalent per-stage and per-test detail by `run_id` instead, per [Delta Comparison Policy](../Specs%20&%20ADRs/Delta%20Comparison%20Policy.md).

---

## `testo flaky`

Tests whose outcome keeps flipping across a cycle's recent runs.

```bash
testo flaky --cycle fake-api               # last 20 runs
testo flaky --cycle fake-api --window 50 --json
testo flaky --cycle nightly --fail-on-flaky  # exit 1 when any test is flaky and not quarantined (CI gate)
testo flaky --cycle nightly --new --json     # only tests the latest run made flaky
```

| Flag | Default | Meaning |
|------|---------|---------|
| `--cycle` | required | Cycle whose run history to read |
| `--window` | `20` | How many of the cycle's most recent runs to look at (min 2) |
| `--new` | off | Only tests the cycle's latest run made flaky: flaky in the window ending at that run, not in the window ending at the run before. Used for alerts and the action's `flaky-issues` |
| `--json` | off | Print the report as JSON |
| `--fail-on-flaky` | off | Exit `1` when any flaky test that isn't quarantined is found |
| `--config` | discovery | `testosterone.yaml` whose `quarantine:` rules mark tests; without a config found, nothing is marked. Exit `2` if the given file is missing or invalid |

A test is flaky when, within the window, it both passed and failed and its outcome changed at least twice (skipped runs are ignored). One change is a regression or a fix, which `testo summary` shows. Exit `2` when fewer than two runs with per-test results exist. Reads run-history records (`run_id`s) and each run's artifact snapshot, the same data as `GET /api/v1/analytics/flaky?cycle=<name>` and the Flaky tests card on the cycle page. See [Open Source Features - 2026-10-19](../Specs%20&%20ADRs/Open%20Source%20Features%20-%202026-10-19.md).

The table's Quarantined column (and `"quarantined"` in `--json`) shows which flaky tests match the cycle's [`quarantine:` rules](../Testing%20Workflows/QA%20Strategies.md#defining-work-in-testosteroneyaml); for the others it prints a `quarantine:` snippet to paste. A quarantined test's failures don't fail `testo run`; see [Flaky Test Quarantine - 2026-10-22](../Specs%20&%20ADRs/Flaky%20Test%20Quarantine%20-%202026-10-22.md).

---

## `testo ui`

Open the web UI (Dashboard, Cycles, Runs, Compare, AI settings) on this machine's run history: the same database and `./.testo/` data the CLI uses.

```bash
pip install 'testo-core[api]'
testo ui                     # http://127.0.0.1:8000, opens the browser
testo ui --port 9000 --no-open
```

| Flag | Default | Meaning |
|------|---------|---------|
| `--port`, `-p` | `8000` | Port on 127.0.0.1 |
| `--open` / `--no-open` | `--open` | Open the default browser once the server is up |

It starts `testo-api` bound to `127.0.0.1` only (for a shared server use the [Team Server](../Processes%20&%20Guides/Team%20Server.md)) and serves the UI that ships inside the wheel, or the build `TESTO_UI_DIR` points at. The UI's own origin (`http://127.0.0.1:<port>`, `http://localhost:<port>`) is added to `TESTO_CORS_ORIGINS` for this process so it can start runs; every other origin is still refused. Exit `2` when the `[api]` extra is missing or no built UI is found (a source checkout builds one with `scripts/build_ui_bundle.sh`, which needs Node 22).

---

## `testo demo`

See the UI with something in it before you have results of your own. Writes eight JUnit XML files for a small made-up shop app into a new folder, records them with `testo ingest` as eight runs of the `demo-shop` cycle, then starts [`testo ui`](#testo-ui) on that history.

```bash
pip install 'testo-core[api]'
testo demo                          # temporary folder, opens http://127.0.0.1:8000
testo demo --dir ./testo-demo --no-ui
```

| Flag | Default | Meaning |
|------|---------|---------|
| `--dir` | a new temporary folder | Where the demo history goes; must be new or empty |
| `--ui` / `--no-ui` | `--ui` | Start the UI once the runs are recorded |
| `--port`, `-p` | `8000` | Port for the UI |
| `--open` / `--no-open` | `--open` | Open the default browser |

The runs show a flaky test (`test_apply_coupon`), a new failure in the latest run (`test_redirect_after_login`), a test that got slower (`test_results_are_ranked`) and one that was fixed (`test_badge_count`). The demo has its own SQLite file and `.testo/` folder inside `--dir` (it sets `DATABASE_URL` and `TESTO_HOME` for the commands it starts), so your real history is never touched. Exit `2` when `--dir` is not empty; otherwise the exit code of the failing `testo ingest` or `testo ui`.

---

## `testo try`

See the pull request comment your latest results would get, before you add anything to CI. It records the result files as a run in a throwaway copy of your history and prints what [`testo report markdown`](#subcommands) (the job summary and the GitHub Action's comment) says about them. The command-line partner of the `/try` page.

```bash
pytest --junitxml=test-results/junit.xml; testo try    # the files your last run left here
testo try reports/junit.xml --cycle api                # these files, compared with cycle `api`
testo try --from-github                                # the latest GitHub Actions run's artifacts
testo try --from-github --run-id 123456 --out comment.md
```

| Flag | Default | Meaning |
|------|---------|---------|
| `REPORTS...` | found | Result files, folders or globs; none = every result file in `--repo` that git doesn't track, as [`testo ingest`](#testo-ingest) finds them |
| `--repo` | `.` | The project |
| `--cycle` | folder name | The cycle to compare with |
| `--from-github` | off | Download the artifacts of the latest finished workflow run with the [GitHub CLI](https://cli.github.com) (`gh run download`) and preview the result files in them. The workflow must upload them (`actions/upload-artifact`) |
| `--run-id` | latest | With `--from-github`: this run |
| `--baseline-branch` | default branch | Compare with this branch's latest run, as a pull request into it would |
| `--out`, `-o` | stdout | Write the comment to a file |

Nothing is recorded: the run goes into a new temporary folder with its own SQLite file and `.testo/` (deleted afterwards). When your history is a local SQLite file (`DATABASE_URL` or `database.url`, else `./testo_history.db`), it is copied in first, so the preview shows what changed since your earlier runs; otherwise it is a first run's comment. No config is read, so reporters and alerts don't fire. Exit `0` with a preview, even when tests failed; `2` when there are no result files or `--from-github` can't download them.

---

## `testo notify`

Send a recorded run to Slack and/or Microsoft Teams: pass/fail counts, then new regressions, newly flaky tests, failing tests and fixed tests (10 names per list).

```bash
export TESTO_SLACK_WEBHOOK_URL=...         # from a secret, never on the command line
testo notify --to slack --cycle nightly                      # only when it needs attention
testo notify --to slack --to teams --cycle nightly --when change --run-url "$CI_JOB_URL"
testo notify --to teams --cycle nightly --dry-run            # print the payload, send nothing
testo notify --to slack --digest week --run-url https://testo.example.com   # weekly digest (cron)
```

| Flag | Default | Meaning |
|------|---------|---------|
| `--to` | required | `slack` or `teams`; repeat for both. URLs come from `TESTO_SLACK_WEBHOOK_URL` and `TESTO_TEAMS_WEBHOOK_URL` |
| `--cycle` / `--run-id` | latest run | Which recorded run to send |
| `--when` | `failure` | `failure`: the run failed or made a test flaky. `change`: the run's result flipped, or a test regressed, got fixed or became flaky. `always`: every run |
| `--title` | cycle name | Name in the message |
| `--run-url` | none | "View run" link |
| `--dry-run` | off | Print the JSON payloads instead of posting |
| `--digest` | none | `week` or `day`: instead of one run, a digest of every cycle (or `--cycle`) over that period against the one before: runs, green builds, test pass rate, line coverage, tests that turned flaky, still fail, got fixed or got slower. `--run-url` becomes the "Open Testosterone" link; `--when` and `--run-id` don't apply. Run it from cron or a scheduled CI job; a period with no runs sends nothing |

Exit `0` when sent or when there is nothing to report, `2` for a bad flag, a missing webhook variable or no recorded run, `3` when a webhook rejects the message or can't be reached (the error never includes the URL). The `slack` and `teams` [reporters](#reporter-types-reporters----reporter) send the same message right after `testo run`. See [Alerts Where Developers Look - 2026-10-22](../Specs%20&%20ADRs/Alerts%20Where%20Developers%20Look%20-%202026-10-22.md).

---

## `testo otel`

Send a recorded run to an OpenTelemetry collector as one trace: a span for the run, one per stage and one per test, with the tests' real start and stop times. Failed tests, red stages and red runs are error spans. Datadog, Grafana Tempo, Honeycomb, Jaeger and any other OTLP backend show it. Needs `pip install 'testo-core[otel]'`.

```bash
export OTEL_EXPORTER_OTLP_ENDPOINT=https://otlp.example:4318
export OTEL_EXPORTER_OTLP_HEADERS="api-key=$OTLP_KEY"   # from a secret, never on the command line
testo otel --cycle nightly                               # the cycle's latest run
testo otel --run-id 3f2c... --service-name shop-tests
testo otel --cycle nightly --dry-run                     # print the spans as JSON, send nothing
```

| Flag | Default | Meaning |
|------|---------|---------|
| `--cycle` / `--run-id` | latest run | Which recorded run to send |
| `--endpoint` | `$OTEL_EXPORTER_OTLP_ENDPOINT`, else `localhost` | OTLP endpoint; a base URL gets `/v1/traces` added for HTTP |
| `--protocol` | `$OTEL_EXPORTER_OTLP_PROTOCOL`, else `http/protobuf` | `http/protobuf` or `grpc` (`grpc` needs `opentelemetry-exporter-otlp-proto-grpc`) |
| `--service-name` | `$OTEL_SERVICE_NAME`, else `testosterone` | The trace's `service.name` |
| `--dry-run` | off | Print the spans as JSON instead of sending (no extra needed) |

Headers come only from `OTEL_EXPORTER_OTLP_HEADERS` (or `OTEL_EXPORTER_OTLP_TRACES_HEADERS`). Exit `0` when sent, `2` for no recorded run, a bad `--protocol`, an HTTP endpoint without `http://` or `https://`, or a missing `[otel]` extra, `3` when the endpoint refuses the spans or can't be reached. The `otel` [reporter](#reporter-types-reporters----reporter) sends the same trace right after `testo run`. Span names and attributes: [OpenTelemetry Export - 2026-10-30](../Specs%20&%20ADRs/OpenTelemetry%20Export%20-%202026-10-30.md).

---

## `testo badge`

A README badge for a cycle's latest run: **tests | 412 passed · 2 flaky**. Green when everything passed, yellow when the cycle has flaky tests (`testo flaky`'s window), red when a test failed or broke, grey with no run.

```bash
testo badge --cycle web --out public/testo-badge.svg     # in CI, next to a published report
testo badge --cycle web --format json --out public/testo-badge.json   # a shields.io endpoint badge
```

| Flag | Default | Meaning |
|------|---------|---------|
| `--cycle` | latest run of any cycle | Which cycle's latest run |
| `--out` / `-o` | stdout | File to write (folders are created) |
| `--format` | `svg` | `svg`: the image. `json`: what `https://img.shields.io/endpoint?url=<its URL>` reads, for shields.io's styles and logos |
| `--label` | `tests` | Left-hand text |

Exit `0`, or `2` for a bad `--format`. With no run of `--cycle`, the grey badge is still written and a warning names the closest recorded cycle (`testo flaky` does the same). A [team server](../Processes%20&%20Guides/Team%20Server.md) serves the same badge live at `GET /api/v1/badge.svg?cycle=web` and `GET /api/v1/badge.json?cycle=web` (cached 5 minutes). Those are reads like any other: with `TESTO_PROTECT_READS` on, a public README can't load them, so publish the file `testo badge` writes instead. Put it in a README with:

```markdown
[![tests](https://you.github.io/project/testo-badge.svg)](https://you.github.io/project/)
```

---

## `testo doctor`

Health check: config load, framework CLIs on PATH, Node.js + Allure Report 3 CLI, optional Docker warnings, DB probe if `DATABASE_URL` or config URL is set.

```bash
testo doctor
testo doctor -c testosterone.yaml
```

**Output:** Rich table with Check / Status / Detail rows (`PASS`, `FAIL`, `WARN`, `SKIP`).

Exits **2** on hard failures (config or missing required executables) — see [Troubleshooting and Error Codes § Commands that use exit codes](Troubleshooting%20and%20Error%20Codes.md#commands-that-use-exit-codes).

---

## `testo plugins`

Lists the built-in frameworks and reporters, then every installed [plugin](#plugins) with the package that registered it.

```bash
testo plugins            # table
testo plugins --check    # also import each plugin and verify its interface
testo plugins --json
```

Exits **1** when `--check` finds a plugin that fails to import or does not implement its interface; otherwise **0**.

---

## `testo clean`

Remove `artifacts/` (from config or `./artifacts`) and `./temp`; optional Docker prune.

```bash
testo clean --yes
testo clean -y --docker
```

Without `--yes` / `-y`: refuses with exit **2**. It also refuses (exit **2**, nothing deleted) when the artifacts root or `--temp-dir` is the filesystem root, your home folder, the current folder, the config's folder, a parent of any of them, or a folder holding `.git`, `testosterone.yaml` or `pyproject.toml`, so `artifacts_root: .` can't delete the project.

### `testo clean --history`

Deletes expired run history instead of artifacts: each expired run's row, its `test_result` rows and its report copy under `static/history/<run_id>/`, oldest first. Runs still `RUNNING` are never touched; report archives (`testo report list`) are separate and stay.

```bash
testo clean --history --dry-run          # list what would go, delete nothing
testo clean --history --yes              # apply history.retention from testosterone.yaml
testo clean --history -y --keep-days 30  # override (or set) the limits for this call
testo clean --history -y --keep-runs 200
```

The limits come from the top-level `history:` section (either or both; a run goes when it breaks any):

```yaml
history:
  retention:
    days: 90            # runs that started more than 90 days ago
    runs_per_cycle: 200 # beyond each cycle's newest 200 runs
```

`--keep-days` / `--keep-runs` override the file's values. Without any limit (no `history:` section and no flag) it exits **2** and says so; without `--yes` (and not `--dry-run`) it exits **2**. A report copy that cannot be removed is listed and the command exits **5**; the rows are already gone. The API server applies the same section on its own every 6 hours while it runs ([Team Server § How it works](../Processes%20&%20Guides/Team%20Server.md#how-it-works)). Without a `history:` section nothing is ever deleted.

---

## `testo watch`

Filesystem watcher (watchdog) re-runs a cycle after debounced changes.

```bash
testo watch --cycle sample-pytests
testo watch --cycle sample-pytests --path sample_target_repo --debounce-ms 750
```

Ignores `.git`, `artifacts`, `venv`, `__pycache__`, etc. Each batch invokes `testo run` with the same cycle.

---

## `testo init`

Sets a project up in one command: detects its test runners, writes `testosterone.yaml` and the CI workflow, adds Testosterone's local files to `.gitignore` and records a first run. Nothing has to be edited by hand for the runners it knows.

```bash
testo init                      # detect, write, record a first run
testo init --dry-run            # print the files it would write; write and run nothing
testo init --stack jest --stack go --cycle web --no-run
testo init --interactive        # the older wizard: asks for each value, writes only the config
```

| Detected from | Stack (`--stack`) | Stage it writes |
|---------------|-------------------|-----------------|
| `pytest.ini`, `conftest.py`, `[tool.pytest]`, pytest in `requirements*.txt` / `pyproject.toml`, `tests/test_*.py` | `pytest` | `equipment: pytest` |
| `jest` in `package.json` | `jest` | `equipment: jest` (Jest's JSON report) |
| `vitest` in `package.json` | `vitest` | `equipment: vitest` |
| `@playwright/test` in `package.json` | `playwright` | `equipment: playwright`, `tier: e2e` |
| `go.mod` | `go` | `command`: `go test -json ./...` into `test-results/go-test.json` |
| a `*.csproj` referencing a test SDK (xUnit, NUnit, MSTest) | `dotnet` | `command`: `dotnet test --logger trx` |
| `pom.xml` | `maven` | `command`: `mvn -B test` (or `./mvnw`), Surefire XML |
| `build.gradle(.kts)` | `gradle` | `command`: `gradle test` (or `./gradlew`) |
| `rspec` in `Gemfile`, or `.rspec` | `rspec` | `command`: `bundle exec rspec` with the JSON formatter |
| `phpunit/phpunit` in `composer.json` | `phpunit` | `command`: `vendor/bin/phpunit --log-junit` |

Cypress is found but left out (it needs the app running first); the command says so.

What it writes, in the project folder (`--dir`, default here):

- **`testosterone.yaml`**: one cycle, named after the folder unless `--cycle` (the same default as `pytest --testo`), with a stage per runner.
- **The CI file** (`--ci`; `auto`, the default, picks the CI the project already uses, else GitHub Actions; `none` writes none):
  - `github`: `.github/workflows/testosterone.yml`: checkout, each language's setup and dependency install (from `requirements*.txt` or the `pyproject.toml` test extra, the Node lockfile's package manager and `.nvmrc`, `go.mod`, ...), then the [GitHub Action](../Processes%20&%20Guides/CI-CD%20Pipeline%20Setup.md) running the cycle with `comment-on-pr: "true"`.
  - `gitlab`, `jenkins`, `circleci`: `.gitlab-ci.yml`, `Jenkinsfile` or `.circleci/config.yml` that run the tests and record them with `testo ingest`, as on [Setup Snippets](../Processes%20&%20Guides/Setup%20Snippets.md). When that file exists it is left alone: the new one goes next to it (`.gitlab/testosterone.gitlab-ci.yml`, `Jenkinsfile.testosterone`, `.circleci/testosterone.yml`) and the command says how to wire it in. With several runners, GitLab and CircleCI get a job per runner, each recording its own cycle (`<cycle>-<runner>`).
- **`.gitignore`**: `testo_history.db`, `artifacts/`, `.testo/` and `test-results/`, the ones not ignored yet.

A file that exists is kept unless `--force`; a kept `testosterone.yaml` with one cycle gives the workflow its cycle name.

The first run (`--no-run` skips it): result files a test run already left in the project (JUnit XML, Jest/Vitest/Playwright/RSpec JSON, `.trx`, `go test -json`, Robot `output.xml`, `allure-results`; recognised by content, files git tracks are skipped as fixtures) are recorded like `testo ingest` would. When there are none, the new cycle runs once. Exit code `0` once a run is recorded, even if some of its tests failed; `2` when no runner was found or an option is wrong.

---

## `testo users`

Accounts for a team server that runs with `TESTO_AUTH=accounts` ([Team Server § Accounts](../Processes%20&%20Guides/Team%20Server.md#accounts)). It writes to the database in `DATABASE_URL`, so run it where the server's database is reachable (for the compose file: `docker compose exec server testo users …`).

| Command | Effect |
|---------|--------|
| `testo users add NAME [--role viewer\|runner\|admin] [--password-stdin]` | Create an account (default role `viewer`). Prompts for the password twice unless `--password-stdin`; at least 10 characters |
| `testo users list` | Usernames, roles and creation dates |
| `testo users set-role NAME ROLE` | Change the role |
| `testo users reset-password NAME [--password-stdin]` | Set a new password |
| `testo users sign-out NAME` | Sign the account out of every browser |
| `testo users remove NAME` | Delete the account (its audit log lines stay) |

`set-role`, `reset-password` and `sign-out` all end the account's existing sessions. Exit code `2` for a bad name, password or role, or an unknown account.

---

## `testo lease`

Give each parallel worker its own key from a resource pool (`resources:` in `testosterone.yaml`), so no two workers, on this machine or on other laptops, use the same VM, device or account at once. Guide: [Shared Resource Pools](../Processes%20&%20Guides/Shared%20Resource%20Pools.md).

```bash
testo lease run flow-vms -- pytest tests/flows      # hold a key while the command runs
testo lease run flow-vms -l win11 --wait 10m -- ./run_flow.sh
LEASE=$(testo lease take flow-vms --ttl 2h)          # prints "<key> <lease id>"
testo lease heartbeat "${LEASE#* }"; testo lease release "${LEASE#* }"
testo lease list                                     # who holds what, how many wait
```

| Command | Effect |
|---------|--------|
| `testo lease run POOL [-l LABEL] [--wait 30m] [--note TEXT] -- CMD...` | Wait for a key, run `CMD` with `TESTO_RESOURCE_ID`, `TESTO_RESOURCE_POOL`, `TESTO_RESOURCE_LABELS`, `TESTO_RESOURCE_DATA`, `TESTO_RESOURCE_<NAME>` per data value and `TESTO_LEASE_ID` set, heartbeat while it runs, give the key back when it ends. Exits with `CMD`'s exit code |
| `testo lease take POOL [-l LABEL] [--wait 30m] [--ttl DURATION] [--json]` | Take a key and print `<key> <lease id>` (or JSON with the env vars). Nothing heartbeats it: it lives `--ttl` (default the pool's `lease_ttl`) unless you call `heartbeat` |
| `testo lease heartbeat LEASE_ID` | Keep a lease alive for another TTL. Exit `1` when it is gone |
| `testo lease release LEASE_ID [--clean]` | Give the key back. `--clean`: you reset it yourself, so the next taker gets `TESTO_RESOURCE_CLEAN=1` |
| `testo lease list [POOL] [--json]` | Each pool's keys: free (and whether it was left clean), held (by whom, since when), expired (free again after the pool's `reuse_delay`) or disabled, and how many requests wait |
| `testo lease disable POOL KEY [--reason TEXT]` / `enable POOL KEY` | Take a broken key out of the pool, put it back |
| `testo lease free POOL KEY` | Take a key back from its holder (needs `admin` on a server with accounts) |
| `testo lease demo [--clear]` | Fill this machine's database with made-up pools (`demo-flow-vms`, `demo-phones`, `demo-license-seats`), some keys held by invented people, one disabled and two requests waiting, to try `testo lease list` and the Resources page. Never touches a team server. `--clear` gives the keys back |

| Flag | Default | Meaning |
|------|---------|---------|
| `-l`, `--label` | none | Only keys with this label; repeat for several |
| `--wait` | `30m` | How long to wait for a free key: `90s`, `10m`, `2h`, `0` (try once) or `forever` |
| `--server` | `$TESTO_SERVER_URL` | Team server that keeps the leases (token from `$TESTO_API_TOKEN`). Unset: this machine's run-history database |
| `--config` | discovery | `testosterone.yaml` with the pools |

Exit codes: `2` for an unknown pool, a bad config or no command after `--`; `3` when no key came free within `--wait`, the pool has no usable key (none match the labels, or all are disabled), or the server can't be reached; `1` when `heartbeat` or `disable`/`enable`/`free` finds nothing to act on.

---

## `testo pool`

Compare resource pools with the keys that really exist, and add or remove keys with the pool's own `provider` commands. Testosterone never creates or deletes a key on its own: `add`, `remove` and `sweep` are dry runs unless `--apply`. Guide: [Shared Resource Pools](../Processes%20&%20Guides/Shared%20Resource%20Pools.md#compare-the-pool-with-what-really-exists).

| Command | Effect |
|---------|--------|
| `testo pool status [POOL] [--check] [--json]` | Read-only. For each pool: which keys `provider.list` shows (`yes`, `missing`, or `?` without a list command), which listed keys aren't in the pool, and each key's lease state. `--check` runs `on_check` on every free key that exists |
| `testo pool add POOL [KEY...] [-n N] [--apply] [--yes]` | Make keys with `provider.create`: the names given, or `N` names `<name_prefix><n>`. Stops at `max_items`. Doesn't edit your config |
| `testo pool remove POOL KEY... [--apply] [--yes]` | Remove keys with `provider.destroy`. Skips keys in `items`, held keys, names without `name_prefix` and keys `provider.list` doesn't show |
| `testo pool sweep POOL [--apply] [--yes]` | Remove leftovers: keys `provider.list` shows with `name_prefix` that aren't in the pool or held, 5 at a time |
| `testo pool log [POOL] [--limit 20] [--json]` | Every `create`/`destroy` run with `--apply`: when, which key, who and from where, and how it went |

`add`, `remove` and `sweep` print the commands and run nothing without `--apply`; with it they ask first unless `--yes`. They need the verb under `provider.allow`, take at most 5 keys per command, and are refused when `TESTO_PROVIDER_ACTIONS=0`.

Flags `--server` and `--config` as for `testo lease`. Exit codes: `0` done (or a dry run), or every pool matches for `status`; `1` a key is missing, not in the pool or fails its check (`status`), or a command failed or every key was skipped (`add`/`remove`/`sweep`, also when you answer no); `2` an unknown pool, a bad config, a verb that isn't allowed, too many keys, or `TESTO_PROVIDER_ACTIONS=0`; `3` a `provider.list` command failed, the lease server can't be reached, or a command ran but logging it failed (nothing more runs).

---

## `testo split`

Split a cycle's tests into shards that take about the same time, from each test's median time over the cycle's recent runs (longest test first, each to the shard with the least time so far). For CI matrix jobs, or one shard per key of a pool. Guide: [Shared Resource Pools § Split tests by time](../Processes%20&%20Guides/Shared%20Resource%20Pools.md#split-tests-by-time).

```bash
testo split --cycle flows --shards 4                       # table: tests and time per shard
pytest --collect-only -q | testo split --cycle flows --shards 4 --index 2 --tests -   # shard 2's node ids
testo split --cycle flows --shards 4 --json                # every shard, with its tests
```

| Flag | Default | Meaning |
|------|---------|---------|
| `--cycle` | required | Cycle whose test times to use |
| `--shards` | required | How many shards |
| `--index I` | none | Print only shard I's tests (1 to `--shards`), one per line |
| `--tests FILE` | the cycle's history | Tests to split, one per line (`-` reads stdin). pytest node ids are matched to their recorded names |
| `--stage` | all | Only this stage's tests |
| `--server` | `$TESTO_SERVER_URL` | Read the times from a team server (token from `$TESTO_API_TOKEN`) |
| `--window` | `20` | Recent runs to take the times from |
| `--allow-empty` | off | With `--index`, exit `0` and print nothing when the shard has no tests (fewer tests than shards) |

Tests with no recorded time count as a typical (median) test; with no history at all the split is round robin. The split depends only on which tests there are and their times, not their order, so every shard that sees the same history picks the same tests. Exit codes: `2` for a bad `--index` or unreadable `--tests`, `3` when the server can't be reached, `1` when there is nothing to split or (without `--allow-empty`) the `--index` shard is empty, since an empty `pytest $(testo split ...)` would run every test. A `--server` (or `$TESTO_SERVER_URL`) that isn't an `http(s)://host` URL exits `2` here and in `testo ingest` and `testo lease`.

---

## `testo affected`

Pick the tests a change can affect, and say why each one was picked. Opt-in: nothing runs fewer tests unless you use this command or [`pytest --testo-affected`](#pytest---testo). Design: [Affected Test Selection - 2026-10-30](../Specs%20&%20ADRs/Affected%20Test%20Selection%20-%202026-10-30.md).

```bash
testo affected                                   # tests to run, each with its reasons
testo affected --base origin/develop --json      # the selection, reasons and per-file decisions
npx jest $(testo affected --list)                # nothing printed = run everything
git diff --name-only HEAD~1 | testo affected --changed -
```

| Flag | Default | Meaning |
|------|---------|---------|
| `--base REF` | `affected.base`, else the pull request's target branch in CI, else `origin/main` | Diff the working tree (and untracked files) against the merge base with this |
| `--changed FILE` | git diff | Changed files, one per line, relative to the repo root (`-` reads stdin) |
| `--coverage FILE` | `affected.coverage` | coverage.py JSON with test contexts: `pytest --cov --cov-context=test`, then `coverage json --show-contexts` |
| `--config` | discovery | `testosterone.yaml` with the `affected:` section |
| `--list` | off | Only the tests, one per line; prints nothing when everything should run |
| `--json` | off | `run_all`, `run_all_reasons`, `nothing_to_run`, `tests` (with `reasons`) and `files` (each changed file's outcome) |

Each changed file maps to tests by the first of: `run_all_when` (run everything), `ignore` (no test), a changed test file (it runs), `rules`, the coverage report. Anything else, an unknown base or an empty diff runs everything, with the reason. Exit codes: `0` for any selection, including "run everything"; `2` for a bad config, an unreadable `--changed` or `--coverage`, or both `--list` and `--json`.

```yaml
affected:
  base: origin/main            # optional
  coverage: coverage.json      # optional, relative to this file
  run_all_when: ["src/core/**"]   # added to conftest.py, pyproject.toml, lockfiles, testosterone.yaml
  ignore: ["docs/**", "*.md"]
  test_files: ["test_*.py"]    # replaces the built-in names of test files
  rules:
    - changed: "src/payments/**"
      tests: ["tests/payments/**", "tests/test_api.py::test_checkout"]
```

---

## `testo backup` / `testo restore`

Copy the whole run history (every database table and each run's stored results under `static/history/`) into one `.tar.gz`, and load it back, into the same or another database (SQLite, Postgres, MySQL).

```bash
testo backup                                   # ./testo-backup-<date>-<time>.tar.gz
testo backup --out /backups/testo.tar.gz --no-files
DATABASE_URL=postgresql://... testo restore testo-backup-20261101-090000.tar.gz
testo restore old.tar.gz --replace --yes       # delete the current history first
```

| Flag | Default | Meaning |
|------|---------|---------|
| `backup --out` / `-o` | `testo-backup-<UTC time>.tar.gz` | Where to write it (written as `.partial`, then renamed) |
| `backup --no-files` | off | Tables only, without the per-run result snapshots (Compare, flaky and the test page need those for old runs) |
| `restore PATH` | required | A file `testo backup` wrote |
| `restore --replace` | off | Empty the tables first. Without it, a database that already has runs is refused |
| `restore --yes` / `-y` | off | Don't ask before `--replace` |

Only columns today's tables have are written, so an older backup restores into a newer version. The AI settings file (it holds API keys) is never included; the `user_account` table holds password hashes, so keep backups as private as the database. Exit `0` on success, `2` for a file that isn't a backup or a database that already has runs, `3` when the database can't be reached.

---

## `testo version`

```bash
testo version
# testo 0.1.0

# Equivalent top-level eager flag (works before/instead of a subcommand):
testo --version
testo -v
```

---

## `pytest --testo`

testo-core installs a pytest plugin (entry point `pytest11`, `testo_core/pytest_plugin.py`). The `pytest-testo` package ([`integrations/pytest-testo/`](https://github.com/taltal-beep/testosterone/tree/main/integrations/pytest-testo)) installs the same thing under a `pytest-*` name. It does nothing unless asked:

| Option | Effect |
|--------|--------|
| `--testo` | Record this session as a run (also `TESTO_RECORD=1`) |
| `--testo-cycle NAME` | Cycle to record under; implies `--testo`. Default: the rootdir's name |
| `--testo-tier unit\|integration\|e2e` | Pyramid tier of the tests (default `unit`) |
| `--testo-server URL` | Upload to a [team server](../Processes%20&%20Guides/Team%20Server.md) instead (default `$TESTO_SERVER_URL`, token from `$TESTO_API_TOKEN`) |
| `--testo-resource POOL` | Give each worker its own key from this [resource pool](../Processes%20&%20Guides/Shared%20Resource%20Pools.md#use-a-pool-in-a-cycle) (from `testosterone.yaml`, or `$TESTO_RESOURCE_SPEC` set by a stage's `resources:`). Tests read it from the variables or the `testo_resource` fixture |
| `--testo-resource-per worker\|test` | One key per worker (default) or a fresh one per test |
| `--testo-resource-label LABEL` | Only keys with this label (repeat for more) |
| `--testo-resource-wait DURATION` | How long to wait for a key (default `30m`); then the test fails |
| `--testo-shard I/N` | Run only shard I of N, split by time like [`testo split`](#testo-split) (also `$TESTO_SHARD`). Bad value or unreachable server: usage error (exit `4`), never a guess |
| `--testo-affected` | Run only the tests the changes since the baseline branch can affect, like [`testo affected`](#testo-affected) (also `$TESTO_AFFECTED=1`); deselects the rest before `--testo-shard` splits. The summary lists what was picked and why, or why everything ran. A picked Python test that isn't collected runs everything; when only ignored files changed, no test runs and pytest exits `0` |
| `--testo-affected-base REF` | Branch or commit `--testo-affected` diffs against (default as `testo affected --base`) |
| `--testo-failed-first` | Run the tests that failed last time first, then flaky ones, then ones that failed in the last 20 runs, then the rest in pytest's order (also `$TESTO_FAILED_FIRST=1`). History comes from the same cycle as `--testo-timings` (local, or `--testo-server`). Applies after `--testo-affected` and `--testo-shard`; works with pytest-xdist. The summary says how many moved; when no history can be read, pytest's order is kept |
| `--testo-timings CYCLE` | Cycle whose test times `--testo-shard` uses (default `$TESTO_CYCLE`, which `testo run` sets, else the rootdir's name; from `--testo-server` / `$TESTO_SERVER_URL` when set) |

The session's JUnit XML (yours if `--junitxml` is set, else a temporary file in a `.testo-*` folder of the rootdir, removed afterwards) is recorded through the same path as `testo ingest`, into a `pytest` stage, and the run writes `artifacts/` like `testo ingest` does. One line in pytest's summary says where it went. Recording never changes pytest's exit code: a problem is reported on that line instead. Nothing is recorded when no tests ran, or on a pytest-xdist worker (the controller records).

---

## Other entry points (not `testo` Typer tree)

| Command | Package | Role |
|---------|---------|------|
| `testo-api` | `testo_api` | FastAPI server (React UI backend) |

The v1.0 `uqo` command (including its `uqo run --config` headless format with `--ghost`, `--json`, `--stream-json`) and the `testo-ui` Streamlit app were removed in v1.1; use `testo run --cycle … --ci` and the React frontend.

---

## Environment variables (common)

| Variable | Effect |
|----------|--------|
| `DATABASE_URL` | Overrides `database.url` in YAML for archives / list |
| `TESTO_HOME` | Where per-run report copies (`static/`, `static_reports/`) are written. Default: `./.testo` for a `pip install`, the repository root for a source checkout ([Architecture Overview § Artifact layout](../Architecture/Architecture%20Overview.md#artifact-layout)) |
| `INFLUXDB_URL`, `INFLUXDB_TOKEN`, `INFLUXDB_ORG`, `INFLUXDB_BUCKET` | Push run KPIs to InfluxDB after each run |
| `PROMETHEUS_PUSHGATEWAY_URL`, `PROMETHEUS_JOB_NAME` | Push run KPIs to a Prometheus Pushgateway after each run |
| `TESTO_SLACK_WEBHOOK_URL`, `TESTO_TEAMS_WEBHOOK_URL` | Webhooks for `testo notify` and the `slack` / `teams` reporters |
| `OTEL_EXPORTER_OTLP_ENDPOINT`, `OTEL_EXPORTER_OTLP_HEADERS`, `OTEL_EXPORTER_OTLP_PROTOCOL`, `OTEL_SERVICE_NAME` | Where `testo otel` and the `otel` reporter send traces (the standard OpenTelemetry variables, `*_TRACES_*` forms too) |
| `TESTO_SERVER_URL`, `TESTO_API_TOKEN` | Team server for `testo lease` (and `pytest --testo-server`) |
| `TESTO_LEASE_DB_URL` | Database for local leases when it isn't the run-history one |
| `TESTO_SHARD` | `I/N`: run only that shard of a pytest session ([`--testo-shard`](#pytest---testo)) |
| `TESTO_REDACT` | `0` turns off hiding secrets in a run's stored results and logs (on by default: API keys, tokens, passwords, credentials in URLs, private keys) |
| `TESTO_REDACT_PATTERNS` | Your own regular expressions to hide, one per line |
| `TESTO_FAILED_FIRST` | `1`: same as [`--testo-failed-first`](#pytest---testo) |
| `TESTO_CYCLE`, `TESTO_STAGE` | Set by `testo run` for each stage's process: which cycle and stage it is |
| Reporter tokens | e.g. `REPORTPORTAL_TOKEN`, `SLACK_WEBHOOK` via `${env:…}` in YAML |

---

## Reporter types (`reporters:` / `--reporter`)

Supported: `allure`, `extent`, `otel`, `reportportal`, `slack`, `teams`, `testbeats`, plus any installed [reporter plugin](#plugins). Configured in root `testosterone.yaml`; outputs often under `reports/` (see repo `testosterone.yaml` for examples).

`slack` and `teams` post the [`testo notify`](#testo-notify) message for the run that just finished. They need a recorded run (not `--no-persist`):

```yaml
reporters:
  - type: slack
    webhook: ${env:SLACK_WEBHOOK_URL}   # default: $TESTO_SLACK_WEBHOOK_URL
    when: failure                        # failure | change | always
    title: Nightly API tests             # default: the cycle name
    report_url: ${env:CI_JOB_URL}        # optional "View run" link
```

`otel` sends the [`testo otel`](#testo-otel) trace for the run that just finished (recorded runs only, `[otel]` extra). Options left out fall back to the `OTEL_*` variables:

```yaml
reporters:
  - type: otel
    endpoint: https://otlp.example:4318   # default: $OTEL_EXPORTER_OTLP_ENDPOINT
    headers: ${env:OTLP_HEADERS}          # "key=value,..."; default: $OTEL_EXPORTER_OTLP_HEADERS
    protocol: http/protobuf               # or grpc
    service_name: shop-tests              # default: $OTEL_SERVICE_NAME or testosterone
```

`testbeats` posts counts only, to the `slack_webhook` / `teams_webhook` options.

After `testo run`, terminal hints may point to `./reports/allure`, `./reports/extent`, etc.

### Official documentation

| Reporter | Reference |
|----------|-----------|
| Allure Report 3 | https://allurereport.org/docs/v3/ |
| ReportPortal | https://reportportal.io/docs/api-development/ |
| ReportPortal agents | https://reportportal.io/docs/log-data-in-reportportal/test-framework-integration/ |

## Plugins

A Python package can add a test runner (`equipment:`) or a reporter (`reporters:`) without changing Testosterone, through two entry point groups:

```toml
# the plugin's pyproject.toml
[project.entry-points."testo.frameworks"]
unittest = "testo_example_plugin:UnittestAdapter"

[project.entry-points."testo.reporters"]
json-summary = "testo_example_plugin:JsonSummaryReporter"
```

After `pip install`, the names work in `testosterone.yaml` and `--reporter`, and `testo plugins` lists them.

| Group | Value | Interface |
|-------|-------|-----------|
| `testo.frameworks` | A class or factory returning an adapter | `FrameworkAdapter` in [`testo_core/frameworks/base.py`](../../testo_core/frameworks/base.py): `name`, `results_subdir()`, `build_argv(target_repo, results_dir, stage_args, workers)` and `native_report(stage_dir)` |
| `testo.reporters` | A `BaseReporter` subclass | [`testo_core/reporting/reporters/base.py`](../../testo_core/reporting/reporters/base.py): `reporter_type` and `publish(results, context, console)`; YAML keys other than `type` arrive as `self._options` |

- The stage process runs `build_argv`'s command in `target_repo`. Tests are counted from Allure `*-result.json` files written to `results_dir` (also exported as `TESTO_SHARED_ALLURE_RESULTS_DIR`), or from the stage's `junit_xml` globs.
- A plugin stage defaults to `tier: unit` and gets `workers` passed through unchanged.
- Built-in names always win; a plugin that reuses one, or a second plugin with the same name, is ignored with a warning.
- Plugins are imported only when a stage or reporter uses them, or by `testo plugins --check`.
- The API's ad-hoc run endpoint (`POST /api/v1/adhoc-executions`) accepts built-in frameworks only.

[`examples/plugin`](../../examples/plugin/README.md) is a complete plugin with one of each. Design: [Plugin API](../Specs%20&%20ADRs/Plugin%20API%20-%202026-10-19.md).

## Related operational docs

- [CI-CD Pipeline Setup](../Processes%20&%20Guides/CI-CD%20Pipeline%20Setup.md) — `testo run --ci` in CI wrappers
- [Delta Comparison Policy](../Specs%20&%20ADRs/Delta%20Comparison%20Policy.md) — semantics for `testo diff` / `testo summary`
