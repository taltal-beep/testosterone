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

### The UI in the wheel: `testo ui` (P2)

- **Built at release time, not at install time.** `scripts/build_ui_bundle.sh` builds the frontend with `VITE_API_BASE_URL=""` into `testo_api/ui_dist/` (gitignored), and hatch's `artifacts` setting puts it in the sdist and the wheel. The publish workflow and CI's `package` job run it before `python -m build`; `scripts/package_smoke.sh` fails when the wheel has no `ui_dist/index.html`. Building with npm in a hatch hook would make every source install need Node.
- **`TESTO_UI_DIR` still wins**; without it `testo_api/ui.py::ui_dir()` falls back to the bundled build, so `testo-api` serves the UI too when it has one. The team server image keeps its own build.
- **`testo ui` is local only.** It binds `127.0.0.1` and adds exactly its own two origins to `TESTO_CORS_ORIGINS`, so the UI it serves can start runs without a token while a foreign or DNS-rebinding page is still refused. Anything wider is `testo-api` with a token.
- **`testo-api` starts uvicorn with the `create_app` factory**, so the app reads the environment at serve time rather than when `testo_api` was first imported.

### Timing noise is not a regression (P6)

Compare flagged a 3 ms slower run as a regression, so every pair of runs had red in it. A duration change now counts only when it is at least 5 % of the baseline and at least a floor (100 ms for run durations, 5 ms for the per-test average); smaller changes are neutral with reason `within_noise`, shown as "Within noise", and the dashboard trend reads "flat". The rule and constants live in [Delta Comparison Policy](Delta%20Comparison%20Policy.md#timing-noise-added-2026-10-25). Counts and health keep no floor. A fixed rule beats a statistical one (per-test variance across runs) for now: it needs no history and is easy to explain; variance-based thresholds can come with the slowest-tests work (P7).
### Accessibility and copy pass (A1–A7, C1–C3, C5–C7, C9, D4–D6)

One pull request for the review's small UI and copy findings, since each is a line or two:

- Primary buttons use `brand-600` (white text at about 5.6:1, was 4.2:1), and a global `:focus-visible` ring makes keyboard focus visible on every control.
- A "Skip to content" link jumps to `<main id="main">`; the desktop crumb bar is a `<header>` landmark; the mobile menu button is 44×44.
- Card titles are `h2`, so pages go h1 → h2. AI settings uses `PageHeader` (its h1) and its form no longer overflows a 390px phone (`w-full min-w-0` on the form and inputs).
- Load errors say what to check ("Couldn't load runs. Check that the API is running, then reload.") instead of "Failed to load X."; loading text uses "…"; titles and nav labels are in sentence case.
- The sidebar's "Advanced" heading is "Tools" and the help card is a plain "Docs" link. The dashboard hides "Trend: unknown", lists only reports that exist, and formats its duration with `formatDuration`.
- `testo --help` leads with the README's tagline, and CLI help text no longer shows reStructuredText double-backtick quotes.

C8 (the default AI model) is left as it is: picking a new model name is a product call, not copy.

## Consequences

- The run page answers "what broke?" without opening Allure or Compare.
- Reading a run's failures loads up to 20 earlier snapshots of its cycle, like `testo flaky` does. Fine for the run page; a per-test index would be the next step if it becomes slow.
- `pip install 'testo-core[api]'` gets the UI from the next release; until then it needs a checkout.
- The PR comment still lists failing tests without grouping; it can reuse `load_run_failures` later.
