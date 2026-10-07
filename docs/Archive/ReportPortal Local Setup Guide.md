---
type: archive
status: archived
created: 2026-06-25
updated: 2026-10-07
---

# ReportPortal local setup (testo validation)

Persistent ReportPortal v5.15.x on Docker for end-to-end `ReportPortalReporter` testing. A **pre-seeded API key** is inserted into PostgreSQL after migrations — no UI token generation.

## Prerequisites

- **Docker Desktop** on macOS with **4–6 GB RAM** allocated (Settings → Resources → Memory).
- Port **8080** is free on the host (`lsof -i :8080`). This stack is separate from the repo's `docker-compose.yml` (Postgres only).

### Official documentation

| Topic | Reference |
|-------|-----------|
| ReportPortal | https://reportportal.io/docs/ |
| ReportPortal API | https://reportportal.io/docs/api-development/ |
| Test framework integration | https://reportportal.io/docs/log-data-in-reportportal/test-framework-integration/ |
| Docker Compose | https://docs.docker.com/compose/ |

## Pre-seeded credentials

| Purpose | Value |
|---------|--------|
| API token (Bearer) | `testo-local-validation_ERERERERQRGBEREREREREV2jef5txhXfGyP3Fw17h7wSbX5dgz7RhFB1P7mNawIW` |
| Dashboard login | `superadmin` / `erebus` |
| Project (in `testosterone.yaml`) | `superadmin_personal` |
| Endpoint | `http://localhost:8080` |

The token is a deterministic ReportPortal 5.x API key (`testo-local-validation` + fixed salt). It is stored as a SHA3-256 hex digest of the full bearer string in `api_keys` (see `infra/reportportal/seed-api-key.sql`).

## Quick start

From the repository root:

```bash
./scripts/reportportal-local.sh up
./scripts/reportportal-local.sh verify
```

Or manually:

```bash
docker compose -f docker-compose-rp.yml --profile core up -d
docker compose -f docker-compose-rp.yml ps
```

Allow **1–2 minutes** on first boot for migrations, token seed, and Java services to become healthy.

## Verify health and authentication

```bash
curl -sf http://localhost:8080/health

curl -sf -H "Authorization: Bearer testo-local-validation_ERERERERQRGBEREREREREV2jef5txhXfGyP3Fw17h7wSbX5dgz7RhFB1P7mNawIW" \
  "http://localhost:8080/api/v1/superadmin_personal/launch?page.size=1"
```

- HTTP **200** on the launch endpoint (empty list is fine) means the seed token works.
- HTTP **401** usually means `token-seed` did not run or migrations failed — check `docker compose -f docker-compose-rp.yml logs token-seed migrations`.

Optional dashboard: open [http://localhost:8080](http://localhost:8080) and sign in as `superadmin` / `erebus` (not required for API reporting).

## Run `sample-pytests` against local ReportPortal

```bash
export REPORTPORTAL_TOKEN=testo-local-validation_ERERERERQRGBEREREREREV2jef5txhXfGyP3Fw17h7wSbX5dgz7RhFB1P7mNawIW

testo run --cycle sample-pytests
```

`testosterone.yaml` already sets `endpoint`, `project`, and defaults the token to the same value if the env var is unset.

Success indicators:

- CLI mentions a ReportPortal launch / dashboard URL.
- `artifacts/reports/reportportal/summary.json` with `"ok": true`.

```bash
testo config validate
```

## Stop and reset

```bash
# Stop containers, keep Postgres data on disk
./scripts/reportportal-local.sh down

# Stop and remove named Docker volumes (rp-storage)
docker compose -f docker-compose-rp.yml down -v

# Full database reset (re-runs migrations + token seed on next up)
rm -rf ./data/reportportal/postgres
./scripts/reportportal-local.sh up
```

## Services (core profile)

| Service | Role |
|---------|------|
| `gateway` | Traefik — UI/API on host `:8080` |
| `postgresql` | Metadata DB (bind mount `./data/reportportal/postgres`) |
| `rabbitmq` | Message broker |
| `migrations` | Schema + default users/projects (one-shot) |
| `token-seed` | Inserts pre-hashed API key (one-shot) |
| `index` | Entry router |
| `service-ui` | Web UI |
| `service-api` | REST API |
| `service-uaa` | Auth (UAA) |
| `jobs` | Background jobs (required by API) |

Analyzer/OpenSearch is omitted; they are not needed for REST launch reporting.

---
**Context & Links:**
- [Command Reference § Reporter types (`reporters:` / `--reporter`)](../CLI%20Commands/Command%20Reference.md#reporter-types-reporters----reporter), [Architecture Overview](../Architecture/Architecture%20Overview.md), [QA Strategies § How results are logged and surfaced](../Testing%20Workflows/QA%20Strategies.md#how-results-are-logged-and-surfaced), [Troubleshooting and Error Codes](../CLI%20Commands/Troubleshooting%20and%20Error%20Codes.md)
