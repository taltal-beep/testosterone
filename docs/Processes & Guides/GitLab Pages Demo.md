---
title: GitLab Pages Demo
tags: [ci, gitlab, pages, frontend, demo]
---

# GitLab Pages Demo

A public, link-shareable demo of Testo: a GitLab pipeline runs **real** `testo run`
cycles against `sample_target_repo`, then publishes the React UI to GitLab Pages
showing the results of those runs.

> Live site: `https://<namespace>.gitlab.io/<project>/` (see [[#What you have to do on GitLab]]).

Related: [[CI-CD Pipeline Setup]] (the reusable template for running Testo in
*your* pipeline), [[Architecture Overview]], [[Streamlit to React Migration Guide]].

## Why it is built this way

GitLab Pages serves static files only, so it cannot host `testo_api` (FastAPI).
Publishing the UI therefore needs run data frozen into files.

What it does *not* do is reimplement the UI against fixtures. Instead:

1. `scripts/export_static_site.py` calls every read-only endpoint the UI uses —
   in-process, through `TestClient` against the same `create_app()` the real
   server runs — and writes each response body to a JSON file.
2. `frontend/src/lib/static-backend.ts` installs a `fetch` shim in builds made
   with `VITE_STATIC_DATA_BASE`, mapping each API request onto the file the
   export wrote for it.

The pages, the API client and the query layer are unchanged, so the published
dashboard renders the same payloads the live API produces. The cost of the trick
is a layout contract between those two files, pinned by
`tests/unit/ci/test_gitlab_pages_demo_contract.py`.

```
testo run (pytest + Behave + BehaveX)
  └─ history DB + static/history/<run_id>/ (Allure HTML)
       └─ export_static_site.py ──► public/data/**.json  +  public/history/**
                                        └─ vite build ──► public/  ──► GitLab Pages
                                             (static-backend.ts reads data/)
```

## What the pipeline runs

`.gitlab-ci.yml` at the repo root (the reusable customer-facing template stays in
`ci/gitlab/testo.gitlab-ci.yml`):

| Job | Stage | What it does |
|-----|-------|--------------|
| `run_demo_cycles` | `demo` | Installs the package, runs `sample-all-frameworks` (green baseline) then `sample-all-frameworks-stochastic` (injected random failures), exports the site into `public/`. |
| `pages` | `deploy` | Builds the frontend in static mode and copies it over `public/`, then copies `index.html` to `404.html` so deep links survive a refresh. |

Two cycles are run on purpose: the second one fails tests at random, so the
published Dashboard and Compare pages show a real regression rather than an
empty diff.

Run history goes to file-backed SQLite inside the job workspace
(`DATABASE_URL=sqlite:///$CI_PROJECT_DIR/.ci-history/testo.db`), so the demo
needs no database service, no MinIO and no credentials.

### Build-time variables the `pages` job sets

| Variable | Value | Why |
|----------|-------|-----|
| `VITE_BASE` | Pages subpath, e.g. `/testosterone/` | Vite asset URLs and the router `basename`. |
| `VITE_STATIC_DATA_BASE` | `<subpath>/data` | Where the shim reads the exported JSON. |
| `VITE_API_BASE_URL` | `$CI_PAGES_URL` | Report links render as `<API base>/history/…`, which on Pages is the published copy of `static/history/`. |

All three are derived from `CI_PAGES_URL`; nothing is hardcoded, so the same
pipeline works for project, user and group Pages.

## Running it locally

```bash
pip install -e ".[api,db]" httpx
npm install                       # Allure 3 CLI, for the HTML reports

testo run --cycle sample-all-frameworks --ci
testo run --cycle sample-all-frameworks-stochastic --ci || true
python scripts/export_static_site.py --out public --site-url http://localhost:8090/testo

cd frontend
VITE_BASE=/testo/ VITE_STATIC_DATA_BASE=/testo/data \
  VITE_API_BASE_URL=http://localhost:8090/testo npm run build
cd .. && cp -r frontend/dist/. public/ && cp public/index.html public/404.html
```

Serve `public/` under a `/testo/` path (any static server) and the demo behaves
as it does on Pages, except for the 404 fallback, which is Pages-specific.

## What visitors see

A banner marks the build read-only and links to the pipeline that produced it.
Writes have nothing behind them, so the shim answers them with
`405 read_only_build`, and the UI shows that message — the Run button and the AI
summary button explain themselves instead of failing silently. The NDJSON event
stream is likewise absent: a static host cannot stream a run that is not running.

Report links work: `static/history/<run_id>/` is copied into the published site,
so the Allure reports for each framework open from the Run detail page.

## What you have to do on GitLab

Everything above is in the repository; these steps need a human and a GitLab
account.

1. **Create the GitLab project**, e.g. `gitlab.com/<user>/testosterone`, public
   (Pages sites on GitLab.com are public unless Pages Access Control is enabled;
   a private project's site is visible only to members).
2. **Get the code there.** GitLab's *pull* mirroring (GitLab fetches from GitHub)
   is a Premium feature, so on Free use one of:
   - the included `.github/workflows/mirror-to-gitlab.yml`, which pushes `main`
     to GitLab on every push. Set repository variable `GITLAB_MIRROR_URL` and
     secret `GITLAB_MIRROR_TOKEN` (a GitLab project access token with
     `write_repository`) on GitHub; the workflow is inert until both exist;
   - or a one-off `git push` to a second remote.
3. **Check runners.** GitLab.com shared runners need an account with CI/CD
   minutes available; GitLab.com asks free-tier accounts to complete identity
   verification (a payment method on file) before shared runners pick up jobs.
   A self-hosted runner works too.
4. **Run the pipeline** — it runs on pushes to the default branch, and can be
   started from CI/CD → Pipelines → Run pipeline.
5. **Open the site** at Deploy → Pages, which shows the URL
   (`https://<namespace>.gitlab.io/<project>/`). The first deployment can take a
   few minutes to become reachable.

Nothing in the pipeline needs secrets; the only credential anywhere is the
mirror token in step 2, and only if you choose that route.

## Maintenance notes

- The cycles the demo runs are `TESTO_BASELINE_CYCLE` / `TESTO_CURRENT_CYCLE` in
  `.gitlab-ci.yml`; a test asserts both still exist in `testosterone.yaml`.
- Adding a UI page that calls a new endpoint means exporting it in
  `scripts/export_static_site.py` *and* mapping it in `static-backend.ts`,
  otherwise the demo shows that panel's error state.
- The export scrubs checkout-absolute paths out of the payloads before they are
  published.
