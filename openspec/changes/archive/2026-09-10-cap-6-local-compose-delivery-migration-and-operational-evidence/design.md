## Context

CAP-2 added public control-plane migrations (`040_tenant_data_source_connections`), CAP-3 added the tenant-schema sync ledger (`041_azure_blob_sync_ledger`), CAP-4 added schema-contract migrations (`042_external_pg_contracts`), plus gateway routes (`/api/v1/data-sources`, external-PG contract routes), chat-API external-query services, and new declared metric families in `src/shared/observability/domain_metrics.py`. The local `docker-compose.yml` already provides single-command startup with `db-init` (`alembic upgrade head` + seed + verify), healthchecks, `depends_on` sequencing, and a local observability stack (otel-collector, Tempo, Loki, Prometheus, Grafana). The running stack on this machine is up and healthy. What is missing is the delivery record for the feature: the ordered migration evidence, the rolling deployment sequence, the readiness/health confirmation covering the new surfaces, the safe-telemetry evidence for the new terminal outcomes, and the documented compatible recovery path. Azure live verification stays deferred per `run.provisioning` (fixtures/fakes only; capabilities inactive until approved resources and activation evidence exist).

## Goals / Non-Goals

**Goals:**

- Record the local rolling delivery sequence for the CAP-2–CAP-5 increments inside the approved single `dev` Compose environment.
- Evidence additive, backward-compatible migration ordering (039 → 040 → 041 → 042) and rerunnable reconciliation.
- Confirm health/readiness coverage for the touched services/workers and safe aggregate telemetry for connection, sync, drift-block, and external-query terminal outcomes.
- Document and exercise the compatible rollback/roll-forward recovery path (runnable health-checked stack within 30 minutes, no destructive database rollback).

**Non-Goals:**

- Staging/production deployment, Kubernetes/ECS, production SLOs/RPO/RTO, traffic splitting, destructive rollback, cloud secret-manager, remote DNS/TLS — all explicitly deferred and claimed nowhere.

## Currently-In-Force ADRs

| ADR | Decision Summary | Constraint on This Design |
|-----|-----------------|--------------------------|
| ADR-001-tenant-data-isolation (as amended by 011) | `public` may hold tenant-bound non-content control-plane records | Migrations 040/042 must stay non-content control-plane; no tenant content in `public` |
| ADR-009-system-admin-sets-training-hyperparameters | Training hyperparameter governance | Untouched; delivery must not alter training job semantics |
| ADR-010-per-entity-type-dataset-threshold | Per-type dataset thresholds | Untouched; no metric label may carry entity-type values |
| ADR-011-tenant-scoped-azure-connection-control-plane | Tenant-scoped connection lifecycle, activation evidence | Delivery keeps capabilities inactive until connection-test + activation evidence pass |
| ADR-012-durable-azure-blob-source-synchronization | Durable idempotent Blob sync via worker/ledger | Delivery must preserve worker/ledger semantics; no in-process scheduling |
| ADR-013-contract-governed-external-postgresql-chat | Live-introspection drift block before every external query | Delivery must not weaken the drift block; direct-query fixture check only |
| ADR-014-local-compose-deployment-topology | Single `dev` Compose env, rolling strategy, final-only approval, loopback-only | All delivery claims stay inside this topology; no multi-env or zero-downtime promise |

## Decisions

### Decision 1: Evidence-first delivery change, no runtime behavior change

**Choice:** CAP-6 adds a runbook, a delivery-evidence pytest module, and the spec/verification record; it changes no service runtime behavior unless verification finds a sequencing/readiness gap.

**Rationale:** Compose already sequences `postgres-test (healthy)` → `db-init (completed)` → application services, and `service-readiness` already requires real-dependency `/health`. Rebuilding working topology to "deliver" would risk the stack every other capability verified against.

**Alternatives considered:**
- Repave `docker-compose.yml` for the feature — ruled out because the existing sequencing already satisfies the rolling strategy for local single-replica services.
- New compose profiles/services for data sources — ruled out because no new process exists (sync rides the existing Celery/extraction worker topology per ADR-012).

### Decision 2: Migration compatibility asserted by chain inspection, not rewrite

**Choice:** The evidence test parses the Alembic revision chain (039 → 040 → 041 → 042, single head) and asserts each data-source revision is additive (no drop-table/drop-column on existing tables) rather than editing the revisions.

**Rationale:** Rewriting archived migrations would invalidate every database migrated by CAP-2–CAP-4. The deployment-plan requires additive/backward-compatible migrations; inspection proves it without touching history.

**Alternatives considered:**
- Squash/rewrite 040–042 — ruled out: destroys migration history and breaks `db-init` idempotency on existing volumes.
- Database-roundtrip migration test — ruled out for the ordering property (needs a scratch Postgres); chain inspection is deterministic and hermetic. A live `alembic upgrade head` on the running stack is recorded separately as environment evidence.

### Decision 3: Telemetry evidence via declarations + scan, not new dashboards

**Choice:** Operational telemetry is evidenced by (a) unit-asserting the declared finite metric families/labels for the four terminal outcome classes, and (b) running `scripts/telemetry_scan.py --dry-run` (self-check) plus a live `--skip-flow` capture against the running stack; no dashboards or alert rules are added (`docs/local-dev.md` explicitly defers them).

**Rationale:** NFR-OPS-001 requires safe aggregate telemetry with declared finite labels; dashboards belong to a later change by recorded decision.

**Alternatives considered:**
- Add Grafana dashboards/alerts now — ruled out: contradicts the recorded "deliberately absent" scope and invents an alerting posture nobody approved.
- Live seeded sync/query flow against Azure — ruled out: `run.provisioning` defers Azure; fixtures/fakes only.

### Decision 4: Recovery evidenced by procedure + timed compose-level exercise record

**Choice:** The runbook documents compatible rollback (restore prior image/configuration) and roll-forward (compatible corrective migration); evidence is the documented procedure plus a timed record of returning the local stack to a health-checked state. Destructive database rollback is never assumed.

**Rationale:** NFR-DR-001 dev target is a 30-minute return to runnable health-checked state; the local database volume is disposable dev data (`docs/local-dev.md`), so recovery never promises point-in-time restore.

**Alternatives considered:**
- `docker compose down -v` as the recovery path — ruled out as the primary path: it destroys dev data and is a rebuild, not a rollback; documented only as the last-resort drift remedy it already is.
- Production RPO/RTO claims — ruled out: deferred, no approved target exists.

## Risks / Trade-offs

- [Running stack predates this change's images] → Evidence records image build state (`docker compose build` freshness note in runbook); recovery procedure starts from a rebuild when drift is suspected.
- [Single-replica local services can interrupt during replacement] → No zero-downtime claim; rolling means ordered with readiness gates, per ADR-014.
- [Live Azure paths cannot be exercised] → Fixture/fake evidence only; capabilities stay inactive; verification records the deferral explicitly.
- [Telemetry scan capture too thin on an idle stack] → `--skip-flow` evidence requires the record-count floor to pass; otherwise record exit-code-2 handling per `docs/local-dev.md` rather than claiming a clean scan.

## Migration Plan

1. `docker compose build` (freshness) → `docker compose up -d` (existing `db-init` applies 039 → 040 → 041 → 042, seeds, verifies).
2. Poll `/health` per service until healthy; portal on :3000, Grafana on :3001.
3. Run delivery-evidence pytest module + telemetry scan; record outputs in `verification.md`.
4. On failure: restore prior compatible image/configuration (rollback) or apply a compatible corrective migration (roll-forward); re-run health checks; never `down -v` except for the documented drift remedy with its data-loss warning.

## Open Questions

- None. No in-force ADR needs revisiting; production topology remains a future approved ADR.
