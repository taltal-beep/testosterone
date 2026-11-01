# Testosterone GitHub Action

This composite action is a thin wrapper around the CLI contract:

`testo run [--config <path>] [--cycle <name>] --ci [--no-persist]`, or, with no
`testosterone.yaml` in the workspace (or with `results`),
`testo ingest [<results>...] [--cycle <name>] --ci`

It runs one cycle on the host runner (or records the results an earlier step
wrote), echoes the NDJSON event stream to the job log, and exposes the final
`plan_finished` event as step outputs.

## No config file

Keep your test step as it is, make it write results (JUnit XML, Jest/Vitest
`--json`, Playwright JSON, `go test -json`, `.trx`, ...), and add the action
after it. It finds the result files itself (by content; files git tracks are
skipped), records them under a cycle named after the repository, and comments
on the pull request:

```yaml
permissions:
  contents: read
  pull-requests: write
steps:
  - uses: actions/checkout@v4
  - run: npm ci && npx jest --ci --json --outputFile=test-results/jest.json
  - uses: taltal-beep/testosterone@v1
    if: ${{ !cancelled() }}   # record failing runs too
```

## Inputs

- `results` (optional, default empty): result files to record instead of running a cycle
  (globs, space or newline separated). Empty with no config = find them
- `history` (optional, default `auto`): keep the run history (SQLite) in the Actions cache
  between runs, so each run is compared with the ones before it. Skipped when `DATABASE_URL`
  or the config's `database.url` is set; `off` never caches
- `config-path` (optional, default empty): path to `testosterone.yaml`; empty means discovery
- `cycle` (optional, default empty): cycle name; empty runs the only cycle, `all` runs every
  cycle and publishes a summary, comment, annotations and alert for each
- `ci-mode` (optional, default `true`): NDJSON on stdout
- `persist` (optional, default `true`): write `plan_result.json` and the run history record
- `python-version` (optional, default `3.11`)
- `package` (optional, default `testo-core`): what to pip install, e.g. `testo-core==1.2.0`,
  `testo-core[bdd]` when the cycle has `behave` or `behavex` stages, or several requirements
  separated by spaces (`testo-core pytest-xdist`)
- `job-summary` (optional, default `true`): write the run to the job summary
- `comment-on-pr` (optional, default `auto`: on when recording results with no config, off
  when running a configured cycle): on `pull_request` events, keep one comment per
  cycle on the pull request with the same summary (edited on later pushes, not re-posted).
  Needs `permissions: pull-requests: write`; with a read-only token (fork PRs) it warns and moves on
- `annotations` (optional, default `true`): print failing tests as `::error` annotations
  (`testo report annotations`), shown on the failing line in the pull request's "Files changed".
  Needs no permission
- `slack-webhook`, `teams-webhook` (optional, default empty): incoming-webhook URLs for a chat
  alert (`testo notify`). Pass secrets, e.g. `${{ secrets.SLACK_WEBHOOK_URL }}`; empty sends nothing
- `notify-when` (optional, default `failure`): `failure` (red run or a newly flaky test),
  `change` (differs from the previous run) or `always`
- `flaky-issues` (optional, default `false`): open one issue (label `flaky-test`) for each test
  this run made flaky, unless an open issue already has its title. Needs `permissions: issues: write`
- `coverage` (optional): coverage report(s) your tests write, space-separated (Cobertura or
  JaCoCo XML, LCOV, Go cover profile). Line coverage is stored with the run, and the summary and
  PR comment show it and how much it moved against the baseline
- `github-token` (optional, default `${{ github.token }}`): token for the comment and issues

The summary is `testo report markdown`: pass/fail counts, a per-stage table, failing tests and
the tests that changed outcome since the cycle's previous run (for a pull request, the latest
run on its target branch). That history comes from the Actions cache (`history: auto`), or from
a `database.url` / team server shared between jobs.

## Outputs

- `exit_code` (`0`–`4`, see `docs/CLI Commands/Troubleshooting and Error Codes.md`)
- `status` (`success`, `failure`, `invalid_input`, `infra_failure`, `internal_error`)
- `summary_json`: the final `plan_finished` (or `error`) NDJSON event
- `summary_path`: the same JSON saved under `$RUNNER_TEMP/testo-summary.json`

## Usage

```yaml
jobs:
  quality:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: taltal-beep/testosterone@v1
        with:
          cycle: sample-pytests
          comment-on-pr: "true"
          slack-webhook: ${{ secrets.SLACK_WEBHOOK_URL }}
```

with `permissions: { contents: read, pull-requests: write }` on the job for the comment
(add `issues: write` for `flaky-issues`).

## Migrating from the v1.0 `uqo` action

The v1.0 inputs `ghost-mode`, `stream-json`, `runner-image` and `runner-prebuilt`
drove the removed headless/Docker runner and are gone; `testo run --ci` already
streams NDJSON and runs stages as host subprocesses. Use `Dockerfile.testo-runner`
as the job container if you want a pinned image. The `run_id` output is gone too:
it read the old summary JSON, which `testo run` does not emit.

## Versioning and pinning policy

- Publish immutable tags for every patch release: `v1.0.0`, `v1.0.1`, ...
- Keep moving major tag `v1` pointing to latest stable `v1.x`.
- For strict supply-chain policies, pin consumers to a commit SHA.

Inputs reach the action's shell steps as environment variables, never pasted into the script,
so an input such as `cycle: ${{ github.head_ref }}` can't run commands.
