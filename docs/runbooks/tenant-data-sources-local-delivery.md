# Tenant Data Sources — Local Delivery Runbook (dev only)

Scope: the single approved `dev` Docker Compose environment on the developer
machine (ADR-014). Loopback entry point only. Everything here is a dev
operating target; there is no production SLO, RPO/RTO, or uptime promise.

## 1. Rolling deployment sequence

Deploy changed services/workers sequentially using the approved `rolling`
strategy. Each replacement waits for compatible migrations and readiness
before the next starts; the prior compatible component stays until its
replacement is healthy. Single-replica local services may still interrupt —
this strategy makes no zero-downtime claim.

```bash
docker compose build        # rebuild from the current working tree
docker compose up -d        # db-init first, then services in dependency order
docker compose ps           # confirm every service is Up (healthy where applicable)
```

Migration order (enforced by `db-init`: `alembic upgrade head` + seed +
verify, gating all app services via
`depends_on: db-init: condition: service_completed_successfully`):

| Order | Revision | Content |
|---:|---|---|
| 1 | 039 | Tenant integration profiles (pre-existing) |
| 2 | 040 | Connection control plane (CAP-2) |
| 3 | 041 | Blob sync ledger (CAP-3) |
| 4 | 042 | Schema contracts (CAP-4) |

All three data-source revisions are additive in `upgrade()` (downgrade-only
DROPs). `db-init` is idempotent: re-running on an initialized database
applies nothing new and exits 0. Verify a single head with
`alembic heads` (expected: `042`).

## 2. Health/readiness checklist

| Surface | URL | Expect |
|---|---|---|
| gateway | http://localhost:8000/health | 200 `{"status": "ok"}` |
| document_service | http://localhost:8001/health | 200 |
| extraction_service | http://localhost:8002/health | 200 |
| training_service | http://localhost:8003/health | 200 |
| model_serving | http://localhost:8004/health | 200 |
| annotation_service | http://localhost:8005/health | 200 |
| chat_api | http://localhost:8006/health | 200 |
| analytics_service | http://localhost:8007/health | 200 |
| portal | http://localhost:3000 | 200, app shell |
| Grafana | http://localhost:3001 | 200 |
| Prometheus | http://localhost:9090 | 200 |
| Loki | http://localhost:3100 | ready |
| Tempo | http://localhost:3200 | ready |

`/health` reflects real dependency state (returns 503 naming the failed
dependency); `/health/live` reports process liveness only. A stopped
`otel-collector` costs telemetry, not traffic: requests keep serving and
health checks keep passing.

## 3. Safe operational telemetry

Terminal outcomes for connection lifecycle, connection tests, Blob sync,
drift-blocked and external-query attempts are recorded on declared finite
metric families only:

- `ner_data_source_lifecycle_total` (provider, action, outcome)
- `ner_data_source_tests_total` (provider, outcome, reason)
- `ner_blob_sync_total` (trigger, outcome)
- `ner_external_pg_query_total` (outcome, reason)

No family carries `tenant_id` or entity-type values; per-connection/run
attribution joins the trace. Unknown values coerce to `other`, which is
itself declared. Verify with:

```bash
python scripts/telemetry_scan.py --dry-run   # self-check, no stack needed
python scripts/telemetry_scan.py --skip-flow # live capture against the stack
```

Exit 0 with the record-count floor met means clean; exit 2 (capture too
thin) means check export, not the application; exit 3 means a backend was
unreachable and the scan proves nothing. Never report exit 2/3 as clean.

## 4. Compatible rollback / roll-forward (dev target: healthy within 30 min)

Destructive database rollback is never assumed. On a failed local deploy:

1. Roll back: restore the prior compatible image/configuration
   (`git stash`/`git checkout` the change, `docker compose build <service>`,
   `docker compose up -d <service>`), **or** roll forward with a compatible
   corrective migration (`alembic upgrade head` stays additive).
2. Re-run the Section 2 checklist until every surface is healthy.
3. Record start/end timestamps from the system clock; the dev target is a
   runnable health-checked stack within 30 minutes.

Last resort only — `docker compose down -v` permanently deletes every local
tenant, user, document, and training run in the `postgres-data` volume (see
`docs/local-dev.md`). It is a drift remedy, not a rollback step.

### Recovery exercise record (2026-09-10)

- Procedure: `docker compose restart gateway`, then polled
  `http://localhost:8000/health` until 200 with the system clock.
- Start/end/elapsed: recorded in the CAP-6 verification evidence
  (`openspec/changes/cap-6-local-compose-delivery-migration-and-operational-evidence/verification.md`
  Evidence Log) at exercise time.
- Result target: stack back to fully health-checked state in under
  30 minutes with no volume removal and no migration change.

## 5. Activation gate (unchanged)

Blob sync and external-PG chat stay **inactive** until a secure connection
test and both activation attestations (`network_approved`,
`governance_approved`) pass per tenant. Azure live verification is deferred:
verify with fixtures/fakes (`FixtureExternalDatabase`,
`telemetry_scan.py --dry-run`); capabilities remain inactive until approved
resources and activation evidence exist.

## 6. Explicitly out of scope

Staging/production deployment, Kubernetes/ECS, production SLOs, RPO/RTO,
traffic splitting (blue-green/canary), cloud secret-manager, remote DNS,
TLS termination, dashboards/alert rules, and any uptime claim. A later
non-local deployment requires a new approved topology ADR.
