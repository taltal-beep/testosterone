# Restore `doctor` / `clean` / `watch` / `init` CLI commands

## Problem

[[Command Reference]] documented four `testo` subcommands — `doctor`, `clean`, `watch`, `init` — with full flag tables and sample output, but none of them existed on `main`. `testo_core/cli/app.py`'s `_register_commands()` only wired up `run`, `config-db`, `diff`, `summary`, `cycles`/`plans`, `config`, `report`, `version`. Only stale `.pyc` cache files remained as evidence the four commands once ran locally.

Root cause: the source files (`testo_core/cli/commands/doctor.py`, `watch.py`, `clean.py`, `init_cmd.py`) were added on branch `cursor/report-infra-e976a` but that branch was never merged and drifted ~20 commits behind `main`, with no open PR.

## Decision

Port the four command modules from `cursor/report-infra-e976a` into `main`, adapting them to APIs that changed on `main` in the meantime rather than cherry-picking blindly.

## What changed vs. the source branch

- `testo_core/cli/ui/feedback.py` (`print_ok`/`print_fail`/`print_warn` helpers) never existed on `main` — replaced with direct `console.print("[ok]...[/]")`-style calls, matching the pattern already used in `testo_core/cli/commands/config_db.py`.
- `testo_core/cli/cleanup.py` (used by `clean`) also never existed on `main` — ported verbatim (self-contained, no API surface drift).
- `testo_core/cli/runner.py`'s `execute_plan_command()` on `main` no longer accepts `tag` / `fail_fast` / `dry_run` keyword arguments (those options exist in the CLI help text but are not implemented in `run.py` on `main` either — pre-existing gap, out of scope here). `watch.py`'s call site was adjusted to only pass the kwargs `execute_plan_command()` currently supports.
- `doctor.py` had a latent bug in the source branch: it read `cfg.cycles` / `cfg.source_path` guarded by `if not hard_fail:` even though `cfg` is only bound when config load succeeds — a CLI-executable hard-fail (not a config-load fail) would still enter that branch safely, but a config-load failure combined with any later flag flip would have risked a `NameError`. Fixed by gating on `if cfg is not None:` instead.
- `init.py`'s generated YAML dropped a `tags: [smoke]` line — `Plan`/`_parse_cycle` in `testo_core/config/schema.py` and `loader.py` on `main` have no `tags` concept; the key was silently ignored, so it was dead/misleading scaffolding.
- Added `watchdog>=4.0.0` to `pyproject.toml` core `dependencies` — required by `watch.py`, was previously undeclared.
- Exit code reconciliation: [[Command Reference]] had two contradictory claims for `testo doctor`'s hard-failure exit code — "exits 3" in the `testo doctor` section vs. "2 on hard FAIL" in [[Troubleshooting and Error Codes#Commands that use exit codes]]. The restored code uses `EngineExitCode.INVALID_INPUT` (2), matching both the original branch implementation and the Troubleshooting doc (the authoritative exit-code table). Fixed the contradictory line in [[Command Reference]].

## Current implementation (HOW — codebase)

| Command | Module | Registered in |
|---------|--------|----------------|
| `testo doctor` | `testo_core/cli/commands/doctor.py` | `testo_core/cli/app.py` → `_register_commands()` |
| `testo clean` | `testo_core/cli/commands/clean.py` + `testo_core/cli/cleanup.py` | same |
| `testo watch` | `testo_core/cli/commands/watch.py` | same |
| `testo init` | `testo_core/cli/commands/init_cmd.py` | same |

Tests: `tests/unit/testo_core/test_cli_doctor.py`, `test_cli_clean.py`, `test_cli_watch.py`, `test_cli_init.py`.

## Out of scope (deliberately not touched)

Shell completion, top-level `--version`, help-panel grouping/emoji (`rich_help_panel=`), and drift-guard tests — those are separate, parallel PRs. `_register_commands()` additions here intentionally match the plain (no `rich_help_panel`) style already on `main`, not the richer style also present in the source branch's `app.py`.

---
**Context & Links:** [[Command Reference]], [[Troubleshooting and Error Codes]], [[Architecture Overview#Exit code contract]]
