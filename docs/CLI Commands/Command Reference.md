# Command Reference

Entry point: **`testo`** (`pyproject.toml` → `testo_core.cli.app:main`). Legacy alias: **`uqo`** (deprecated headless wrapper).

Parent index: [[Index]]. Architecture: [[Architecture Overview]]. Run lifecycle: [[QA Strategies]].

```bash
testo --help
```

Help is grouped into panels: **Run and report**, **Config**, **Diagnostics**, **Maintenance**, **About**.

---

## `testo run`

Execute one cycle or all cycles from `testosterone.yaml`.

```bash
testo run --cycle sample-pytests
testo run --cycle all --tag smoke --fail-fast
testo run --cycle sample-pytests --dry-run
testo run --cycle sample-pytests --ci
testo run --cycle sample-pytests --stream
testo run --cycle sample-pytests --reporter allure,extent
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
| `--workers` | `-w` | Override parallel workers (e.g. BehaveX) |
| `--force` | `-f` | Run even when trigger would skip the cycle |
| `--tag` | | With `--cycle all`, only cycles listing this tag; with one cycle, fail if tag missing |
| `--fail-fast` | | Stop after first failing stage; with `all`, stop after first failing cycle |
| `--dry-run` | | Print resolved plan (respects triggers unless `--force`) |
| `--reporter` | | Comma-separated reporter types (overrides YAML `reporters:`) |

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

**`--dry-run`:** Table of stage index, name, equipment, cwd, and resolved shell command; or NDJSON `dry_run_stage` events when `--ci`.

### Exit codes

See [[Architecture Overview#Exit code contract]]. `testo run` returns the engine exit code directly.

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
| `testo config validate` | Load YAML; optional `--check-executables` for pytest/behave/behavex on PATH |
| `testo config init` | Write starter `testosterone.yaml` (`--path`, `--force`) |
| `testo config db` | Set `database.url` (PostgreSQL prompts or `--url`) |

```bash
testo config validate
testo config validate --no-check-executables
testo config init --path testosterone.yaml --force
testo config db --url sqlite:////tmp/testo-reports.db
```

**Validate success:**

```text
ok — version=1 cycles=6 reporters=4 defaults_target=.
```

**Deprecated:** `testo config-db` → use `testo config db`.

---

## `testo diff` / `testo summary`

Compare two archived report runs by UUID (from `testo report list`).

```bash
testo diff <BASELINE_ID> <CURRENT_ID>
testo summary   # same family; see help for metrics-only variants
```

Rich terminal diff of metrics and (for full diff) extracted Allure deltas. Requires `testo-core[db]`.

Prefer **`testo report compare`** for Rich diff plus Allure visual comparison pipeline.

---

## `testo doctor`

Health check: config load, framework CLIs on PATH, Node.js + Allure Report 3 CLI, optional Docker warnings, DB probe if `DATABASE_URL` or config URL is set.

```bash
testo doctor
testo doctor -c testosterone.yaml
```

**Output:** Rich table with Check / Status / Detail rows (`PASS`, `FAIL`, `WARN`, `SKIP`).

Exits **2** on hard failures (config or missing required executables) — see [[Troubleshooting and Error Codes#Commands that use exit codes]].

---

## `testo clean`

Remove `artifacts/` (from config or `./artifacts`) and `./temp`; optional Docker prune.

```bash
testo clean --yes
testo clean -y --docker
```

Without `--yes` / `-y`: refuses with exit **2**.

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

Interactive wizard for `testosterone.yaml` (non-interactive alternative: `testo config init`).

```bash
testo init
```

---

## `testo version`

```bash
testo version
# testo 0.1.0
```

---

## Other entry points (not `testo` Typer tree)

| Command | Package | Role |
|---------|---------|------|
| `uqo run …` | `testo_core.cli.deprecated` | Legacy headless JSON/ghost mode for CI |
| `testo-api` | `testo_api` | FastAPI server |
| `testo-ui` | `testo_ui` | Streamlit UI |

---

## Environment variables (common)

| Variable | Effect |
|----------|--------|
| `DATABASE_URL` | Overrides `database.url` in YAML for archives / list |
| `UQO_*` | Legacy runner/orchestration (Docker path) |
| Reporter tokens | e.g. `REPORTPORTAL_TOKEN`, `SLACK_WEBHOOK` via `${env:…}` in YAML |

---

## Reporter types (`reporters:` / `--reporter`)

Supported: `allure`, `extent`, `reportportal`, `testbeats`. Configured in root `testosterone.yaml`; outputs often under `reports/` (see repo `testosterone.yaml` for examples).

After `testo run`, terminal hints may point to `./reports/allure`, `./reports/extent`, etc.

### Official documentation

| Reporter | Reference |
|----------|-----------|
| Allure Report 3 | https://allurereport.org/docs/v3/ |
| ReportPortal | https://reportportal.io/docs/api-development/ |
| ReportPortal agents | https://reportportal.io/docs/log-data-in-reportportal/test-framework-integration/ |

## Related operational docs

- [[Release Management/README]] — install/contract gates per phase
- [[CI-CD Pipeline Setup]] — `uqo run` in CI wrappers
- [[ReportPortal Local Setup Guide]] — local ReportPortal stack for reporter validation
- [[Delta Comparison Policy]] — semantics for `testo diff` / `testo summary`
