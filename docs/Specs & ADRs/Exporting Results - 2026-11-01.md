---
type: spec
status: current
created: 2026-11-01
updated: 2026-11-01
---

# Exporting Results - 2026-11-01

## Context

Taltal: "there is no easy way to extract results". The dashboard's main use is good-looking data for senior managers, and the only copy button in the UI was the rerun command on the failing tests card. Research (Grafana, Datadog, Looker, ReportPortal, TestRail, Allure 3) found one pattern everywhere: a PDF of the dashboard rendered by a headless browser, a layout choice, and delivery on a schedule to email, Slack or Teams. Test tools stop at a one-off PDF of one run; none ships slides. On 2026-11-01 Taltal chose to build all four phases of the plan.

## Decision

One renderer for every format: the UI's pages, with the data the API already computes. No second hand-made template per format.

1. **Copy anything.** Every titled `Card` has a Copy menu (`components/ui/CopyMenu.tsx`, helpers in `lib/clipboard.ts`): copy as text, copy as table (`text/html` with an inline-styled table plus tab-separated `text/plain`, so it pastes as a table in email, Slack, Confluence, Notion and Google Docs, and as cells in a spreadsheet), download CSV, copy or download a chart as a PNG (the SVG with its computed paint inlined, drawn at 2x on a white background), and a link to the card (`#card-<title>`). Cards opt out with `copy={false}`. The run page has "Copy summary": `GET /api/v1/runs/{id}/markdown`, the same text as `testo report markdown` without the hidden PR-comment marker.
2. **Manager report page and PDF.** A `/report` page laid out as a printable document (light theme, page breaks), printed to PDF by the browser.
3. **Server-side PDF and PNG.** The same page rendered by headless Chromium (Playwright) from `testo export` and the API, and attached to the scheduled digest.
4. **Data and slides.** CSV and XLSX, a single-file HTML snapshot, and a PowerPoint deck with native charts.

Phases 2 to 4 update this note as they land.

## Consequences

- The clipboard needs a secure context (HTTPS or `localhost`); elsewhere the menu falls back to plain text, and says so when even that is refused.
- Chart images work for SVG charts. Bar charts drawn with plain `div`s are copied as text or table, not as images.
- The static demo answers `/runs/{id}/markdown` from `runs/<id>/markdown.json`, written by `scripts/export_static_site.py`.
