---
type: spec
status: current
created: 2026-10-25
updated: 2026-10-25
related: "Product Review, Product Roadmap Work"
---

# Product to Ten - 2026-10-25

## Context

The second pass of the [product review](../product-review.md) scored the product 7.5 and listed what a 10 needs in each area except trust, which only users and a launch move. Taltal asked for every other area to go as far toward 10 as code can take it, in waves of separate pull requests, merged when green. Earlier roadmap work is in [Product Roadmap Work - 2026-10-25](Product%20Roadmap%20Work%20-%202026-10-25.md).

## Decisions

### Recorded cycles get a page (P10)

`GET /api/v1/cycles` and `GET /api/v1/cycles/{cycle}` read `testosterone.yaml`, so a cycle created by `testo ingest`, the path the README leads with, was missing from Cycles and its page answered 404. Both routes now add the cycles that exist only in run history (`history.read_model.latest_run_per_cycle`, the newest run of each among the last 500), after the config's own, with `source: "history"`. Their detail page takes its stages from the latest run, and the UI hides the Run panel and the config-only stage fields (args, timeout, workers). A cycle that is in both stays a config cycle.

With no config file at all, as with `testo ui` over ingested runs, the read routes list the recorded cycles instead of answering 503. A `config_path` the caller names must still exist, and an invalid config is still a 503.

### "New" means new against the baseline, and the run says what it tested (P11, P12)

The run page's failing-tests card counted a test as new when the cycle's previous run, on any branch, passed it. On a repo with parallel pull requests that run is often someone else's branch. `load_run_failures` now uses the PR comment's rule ([Product Roadmap Work](Product%20Roadmap%20Work%20-%202026-10-25.md), P3): a run with a recorded target branch is judged against the latest run on that branch, and any other run against the run before on its own branch. A test is `new` when it isn't failing on that baseline. Streaks ("Failing for N runs") and flakiness follow the run's own branch; runs that recorded no branch stay in, since they can't be told apart. `GET /api/v1/runs/{run_id}/failures` adds `new` per test and `baseline_run_id`, plus `baseline_branch` when the baseline is another branch, so the card can say "1 new since main, 3 already failing on main" and mark a test "Also failing on main".

`GET /api/v1/runs/{run_id}` now returns the `branch`, `commit`, `base_branch` and `repository` the run recorded, and the run page shows them under its title, with the commit linked on GitHub.

## Consequences

- A team that only ingests JUnit gets the same cycle page as one that runs cycles through `testo run`, apart from starting runs.
- `GET /api/v1/cycles` reads up to 500 recent runs on each call. Fine at this scale; a distinct-cycles query in the repository is the next step if it shows up.
