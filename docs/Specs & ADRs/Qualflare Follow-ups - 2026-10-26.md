---
type: spec
status: current
created: 2026-10-26
updated: 2026-10-26
---

# Qualflare Follow-ups - 2026-10-26

## Context

A comparison with Qualflare (a hosted test-results service with a free plan for open source projects) listed what it offers that Testosterone didn't: a public results page with a README badge, an AI chat about the test suite, test case management (manual cases, milestones, defects, Jira) and phone apps. Its runner list also led to [Runner Coverage](Runner%20Coverage%20-%202026-10-26.md)'s RSpec, k6, XCTest and Android addendum.

## Decision

Build the parts that fit "what changed on every run" and skip the rest:

- **README badge** (this note's first part, below).
- **Ask about your tests**: a chat over the recorded history, using the AI provider already configured for summaries.
- **Create a Jira issue** from a failing test, next to the GitHub issue link.
- **Not built:** test case management (manual cases, milestones) is another kind of product and would blur the pitch; native phone apps aren't needed because the UI already works in phone browsers.

### README badge

`services/badge.py` turns a cycle's latest run into one `Badge` (label, message, colour): `412 passed`, plus `N failed` (failed and broken) and `N flaky` (the cycle's `testo flaky` count). Red when anything failed, yellow when only flaky, green otherwise, grey with no run. Two renderings:

- `render_svg`: a flat badge in the shields.io style, with a `<title>` so screen readers read "tests: 412 passed". No font metrics are available server-side, so text width is estimated generously.
- `shields_endpoint`: the JSON shields.io's endpoint badge reads, for people who want its styles and logos.

`testo badge` writes either one (CI publishes it next to a report, e.g. GitHub Pages); the API serves both live at `GET /api/v1/badge.svg` and `GET /api/v1/badge.json` with a five-minute cache. They are ordinary reads: `TESTO_PROTECT_READS` covers them, so a private server's badge only shows to signed-in viewers. No public share link was added; a public page stays the published static report.

## Consequences

- The badge costs one flaky-test scan of the cycle's recent runs per request; the cache header keeps GitHub's image proxy from asking often.
- Details per command: [Command Reference § testo badge](../CLI%20Commands/Command%20Reference.md#testo-badge).
