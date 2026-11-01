---
type: spec
status: current
created: 2026-11-01
updated: 2026-11-01
---

# Engine Fixes - 2026-11-01

## Context

The [Engine and CLI Bug Hunt](../engine-cli-review.md) (2026-10-31) fixed the small bugs it found and left 15 proposals (P1 to P16, no P15) that change behaviour or are bigger than a one-line fix. Taltal approved all of them on 2026-11-01. They ship as several small pull requests, one area each, so each can be reviewed and reverted alone.

## Decision

| # | Change | Where |
|---|--------|-------|
| P1 | **One run of a cycle at a time per artifacts folder.** `CycleRunService.run` holds an OS file lock on `<artifacts>/<cycle>/.lock` (`fcntl.flock`, `msvcrt.locking` on Windows) from the first stage until the reporters, native report snapshot and report archive have read the folder. A second run of the same cycle waits and prints `another run of cycle 'x' is using ... (pid N); waiting for it to finish`. Other cycles, and the same cycle with another `artifacts_root`, never wait. The OS drops the lock when the process dies, so a killed run never leaves it held. | `testo_core/engine/cycle_lock.py`, `testo_core/services/cycle_run.py` |

Rows are added as each pull request lands.

## Consequences

- P1: two CI jobs of one cycle on one runner now run one after the other instead of overwriting each other's results. The API already refused a second run of a busy cycle in its own process; the lock also covers the CLI next to the API. With `--async-report-db` the background archive reads the folder after the lock is released, so a run that starts right then can still race it; per-run folders (`artifacts/<cycle>/<run-id>/`) would remove that and are left for later.
