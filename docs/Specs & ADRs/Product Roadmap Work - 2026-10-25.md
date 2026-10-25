---
type: spec
status: current
created: 2026-10-25
updated: 2026-10-25
related: "Product Review, Product Roadmap, Delta Comparison Policy"
---

# Product Roadmap Work - 2026-10-25

## Context

The [Product Review](../product-review.md) scored Testosterone 6.5 / 10 as a product and ended with a Now / Next / Later roadmap. Taltal said to start on it on 2026-10-25. Each item ships as its own pull request; this note records what each one decided, so the reasons survive the PR threads.

## Decisions

### Failing tests first on the run page (P1, P5, D1, D2, C4)

- **One read, no schema change.** `testo_core/services/run_failures.py::load_run_failures` reads the failing tests from the run's artifact snapshot (the Allure `*-result.json` files), the same source Compare and `testo flaky` use, so engine and ingested runs both work and old runs get the card too. `GET /api/v1/runs/{run_id}/failures` serves it; the static demo exports it as `data/runs/<id>/failures.json`.
- **"Failing since" is a streak, not a first-seen date.** It counts the consecutive earlier runs of the same cycle in which the test also failed, within the flaky window (20 runs). `1` is "New". It is still per cycle, not per branch; the main-branch baseline (P3) changes the comparison, not this count.
- **Flaky uses the same rule as `testo flaky`** (`flaky_service.classify`) over the same window, ending at this run.
- **Grouping by message.** The first line of `statusDetails.message` (or the trace) with numbers, hex ids and quoted values blanked is the group key; only groups of two or more are shown. Plain matching, no ML: it's predictable and good enough for "ten tests, one connection error".
- **Page order follows the question.** A one-line verdict under the title, then failing tests, the AI summary (failed runs only), stages, reports, test mix, details and artifacts. The run id, exit code and duration moved to Details. "Healthy pyramid" became "Pyramid-shaped: mostly unit tests" and the card is "Test mix", so a failed run no longer shows a green health word; the header dot says "API connected" instead of "All systems go".

## Consequences

- The run page answers "what broke?" without opening Allure or Compare.
- Reading a run's failures loads up to 20 earlier snapshots of its cycle, like `testo flaky` does. Fine for the run page; a per-test index would be the next step if it becomes slow.
- The PR comment still lists failing tests without grouping; it can reuse `load_run_failures` later.
