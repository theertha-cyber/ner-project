# Smoke -- tenant-self-service-data-sources-20260909-2

Scope: post-deployment smoke against the live dev system. Base URL http://localhost:8000 (docker-compose, dev). Signed in as seeded tenant admin for authenticated checks.

## Results

| Check | Expected | Observed | Status | Evidence |
|---|---|---|---|---|
| `GET /health` | ok with reachable database | `{"status":"ok","dependencies":{"database":{"status":"healthy","detail":"reachable"}}}` | pass | deployment record + live curl |
| `GET /health/live` | ok | `{"status":"ok"}` | pass | live curl |
| Portal root `http://localhost:3000/` | HTTP 200, renders | HTTP 200; renders "NER Platform" shell | pass | live curl + `../evidences/tenant-self-service-data-sources-20260909-2/accessibility/login.png` |
| `GET /api/v1/data-sources` without token | 401, no data | 401 `AUTH_ERROR` with request id, no data | pass | live curl |
| Seeded tenant-admin login | bearer token issued | `access_token` + user `admin@democorp.io` / `tenant_admin` / `demo-tenant` | pass | live API (token kept in memory only) |
| `GET /api/v1/data-sources` as tenant admin | 200 safe `ConnectionPage` | 200 empty page (`total: 0`), names/outcomes only, no secret material | pass | live API |
| Data Sources page as tenant admin | list renders, empty state | renders with search/provider/status filters, "No data sources yet", sidebar entry present | pass | `../evidences/tenant-self-service-data-sources-20260909-2/accessibility/data-sources.png` |

## Decision

**Go.** The deployment is stable enough for the deeper gates below. No No-Go condition.
