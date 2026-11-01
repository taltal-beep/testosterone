---
type: spec
status: current
created: 2026-11-01
updated: 2026-11-01
---

# Easy Setup - 2026-11-01

## Context

A team with tests and CI already had to read [Getting Started](../Getting%20Started.md), write `testosterone.yaml` by hand, find the right result-file flag for each runner and write a workflow before seeing anything. `testo demo` and the `/try` page show what Testosterone does on sample or pasted results; nothing set up the team's own project. Four changes were approved together, each its own pull request:

1. `testo init` detects the stack, writes the config and the CI workflow, and records a first run.
2. The GitHub Action works with no config file: it finds result files itself and posts the pull request comment.
3. Copy-paste setup for each stack and each CI system (GitHub Actions, GitLab CI, Jenkins, CircleCI).
4. A dry run that shows the pull request comment the last results would get.

## Decision

- **One place knows the stacks.** `testo_core/services/project_setup.py` reads project files only (nothing is run): `detect_project()` returns a `Stack` per runner with the `testosterone.yaml` stage that runs it so its results are read (native equipment for pytest, Jest, Vitest and Playwright; a `command` stage with `junit_xml` for Go, .NET, Maven, Gradle, RSpec and PHPUnit) and how to install its dependencies. `find_result_files()` finds results a test run left behind by content, skipping files git tracks (fixtures) and dependency folders. `testo_core/services/ci_templates.py` turns the same facts into CI files. `testo init`, the Action's zero-config mode and the docs snippets all use these, so they can't disagree.
- **`testo init` writes, then records.** It writes `testosterone.yaml`, `.github/workflows/testosterone.yml` and missing `.gitignore` lines, keeps any file that exists unless `--force`, and records a first run (existing results through the ingest path, else one `testo run`). A failing test still counts as recorded (exit `0`). The old wizard stays as `testo init --interactive`. Reference: [Command Reference § testo init](../CLI%20Commands/Command%20Reference.md#testo-init).
- **The Action needs no config.** `integrations/github-action/run_testo_action.py` picks `testo ingest --ci` over `testo run --ci` when the workspace has no config or the `results` input is set, and `testo ingest` with no file arguments uses `find_result_files()`, so the Action, a GitLab job and a laptop find results the same way. `comment-on-pr: auto` is on in that mode only, so configured users who never asked for a comment don't start getting one. History is the part a fresh runner lacks: a `prepare-history` step points `DATABASE_URL` at a SQLite file under `~/.cache/testosterone` and the composite action restores and saves it with `actions/cache` (new key per run and step, restored by workflow-and-job prefix), unless the user already set a database. Only the database is cached so the cache doesn't grow with report copies.
- **Generated YAML is text, not a dump.** The templates write comments and key order the way a person would, and the tests load the output back (`discover_and_load`, `yaml.safe_load`) so it stays valid.

## Consequences

- The detection rules are heuristics. A project that installs test dependencies some other way gets a workflow whose install step needs a tweak; `--dry-run` shows it before anything is written.
- Cypress is detected but not added, since it needs the app running first.
- Adding a stack means one `Stack` entry in `project_setup.py` and, for CI, its language setup in `ci_templates.py`.
