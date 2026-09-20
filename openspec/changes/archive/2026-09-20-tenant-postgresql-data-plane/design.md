## Context

Every tenant schema lives on one platform PostgreSQL (ADR-001). The pipeline writes that schema from five services and four Celery workers, generates DDL at run time (`entity_views.py`, `relational_projection.py`), provisions a `NOLOGIN` chat query role (`sql_execution_role.py`), and relies on in-schema foreign keys, same-transaction writes (`ocr_worker.py` spans + status), and in-schema filters (`retriever.py` → `azure_blob_hidden_documents`).

Engine access today:

- `src/shared/database.py` has `EngineResolver.resolve(tenant_id)` — one global async engine, `tenant_id` ignored, documented as the substitution point for this change.
- Worker engines bypass it: `extraction_service/worker.py`, `extraction_service/services/entity_store.py`, `training_service/worker.py`, `analytics_service/worker.py` call `create_engine(settings.database_url_sync)`.
- Fleet loops enumerate `pg_namespace`: `entity_views.py`, `sql_execution_role.py`, `gateway/verify_schema.py`, `gateway/api/v1/dashboard.py`.
- Provisioning (`gateway/services/tenant_service.py`) clones `tenant_template` with `CREATE TABLE … (LIKE …)` inside one transaction.
- Tenant-scoped Alembic migrations apply DDL to `tenant_template` and then `DO $$` loop over `pg_namespace`.

Control plane already present: `public.tenant_integration_profiles` (records `relational_adapter`/`index_adapter`, `retention_mode`), `public.tenant_data_source_connections` (ADR-011 lifecycle, `provider` CHECK, one-active-per-provider partial unique index), secret references resolved by `env://` locally and Vault in shared environments, `src/shared/data_sources/testing.py` secure test registry, `resolver.py` mapping `(relational_adapter, tenant_postgresql)` to the read-only `azure_postgresql` provider.

Stakeholder decisions already made: whole-schema relocation; new tenants only; fail closed with retry, no platform buffering; filename stays in the tenant store; residency tenants use `ephemeral` or `source_only` retention; one OpenSpec change.

## Goals / Non-Goals

**Goals:**

- Run the unchanged pipeline against a tenant-owned Azure Database for PostgreSQL – Flexible Server for `tenant_owned` tenants.
- Guarantee no silent fallback to the platform database for those tenants.
- Provision and migrate tenant stores with a single schema source of truth shared with the platform plane.
- Isolate a tenant store outage to that tenant.
- Keep quotas, counts, and system-admin views working without reaching into tenant stores.

**Non-Goals:**

- Moving existing tenants between planes.
- Non-Azure PostgreSQL targets or non-PostgreSQL engines.
- Residency for fine-tuned model artifacts, MLflow runs, or LLM/embedding transit.
- A separate external vector store.
- Customer database HA, backup, point-in-time restore, or deletion inside the tenant store.
- Distributed transactions across platform and tenant databases.

## Currently-In-Force ADRs

| ADR | Decision Summary | Constraint on This Design |
|-----|-----------------|--------------------------|
| 001-tenant-data-isolation | Schema-per-tenant on a single PostgreSQL; `public` for tenant-bound non-content control plane | Schema-per-tenant naming and search-path scoping still hold; single-instance topology is revisited by ADR-017 |
| 007-chatbot-architecture | RAG over SQL entities + pgvector + NER | Retrieval and SQL paths must run unchanged on either plane |
| 011-tenant-scoped-azure-connection-control-plane | Tenant-admin lifecycle, secret refs, TLS, evidence, one active per provider; PostgreSQL credential read-only | Reuse the lifecycle and evidence; the new provider's write credential is a revision recorded by ADR-017 |
| 012-durable-azure-blob-source-synchronization | Celery/RabbitMQ sync jobs, ledger, temporary bytes deleted | Sync ledger moves with the schema; retention constraint must hold |
| 013-contract-governed-external-postgresql-chat | Read-only contract-governed external query | Unchanged; must not share credentials with the data plane |
| 014-local-compose-deployment-topology | Single `dev` Compose environment, additive migrations, rolling | Local tenant store is a Compose service; migrations additive |
| 015-external-chat-reply-persistence | External rows never persisted to platform tables | Unaffected; reply persistence goes to the tenant's resolved store |
| 016-contract-grounded-external-sql-generation | External SQL grounded in published contract | Unaffected |
| 017-tenant-owned-postgresql-data-plane (proposed) | Whole-schema relocation to a tenant-owned store | Governs this design |

## Decisions

### Decision 1: Relocate the whole tenant schema by connection routing

**Choice:** A tenant's complete `tenant_<id>` schema is served by exactly one engine, chosen by `EngineResolver`. Nothing in the schema is split across servers.

**Rationale:** Foreign keys, single-commit OCR writes, retrieval `NOT EXISTS` filters, chat SQL joins, and materialized views all assume one database. Routing keeps every query, generated DDL statement, and migration identical.

**Alternatives considered:**
- Table-level split — ruled out: requires outbox/2PC and rewriting join paths.
- Repository abstraction over stores — ruled out: the derived layer emits PostgreSQL DDL at run time.

### Decision 2: Control-plane data-plane record with an explicit status machine

**Choice:** `public.tenant_data_planes(tenant_id PK, mode, status, connection_id, store_id, schema_revision, status_reason, health_outcome, health_checked_at, created_at, updated_at)`. `mode ∈ {platform, tenant_owned}` immutable (enforced by service and a trigger rejecting updates to `mode`). Status transitions:

```
platform:      ready (fixed; platform schemas stay on Alembic)
tenant_owned:  awaiting_store → provisioning → ready
               provisioning → provisioning_failed → provisioning (retry)
               ready → migration_required → ready
               ready ↔ paused
               ready|paused|migration_required|provisioning_failed → store_retired (terminal)
```

Status changes use compare-and-set (`UPDATE … WHERE status = :expected`) so concurrent activations, retries, and deploy runs cannot race.

**Rationale:** The resolver, content-route gate, portal, and admin console need one authoritative, content-free answer that remains readable when the tenant store is down. Health lives on the same row but is written separately and never gates by itself (readiness gating uses `status`; outages surface as `TENANT_DATA_PLANE_UNAVAILABLE` from real failures).

**Alternatives considered:**
- Columns on `public.tenants` — ruled out: mixes identity with store lifecycle and widens the tenants ORM model used everywhere.
- Derive readiness from connection status alone — ruled out: cannot express provisioning or migration state.

### Decision 3: New provider `azure_postgresql_data_plane`

**Choice:** Add the provider to `providers.py`, the `provider` CHECK constraint, portal provider catalog, and a registered secure tester. Configuration keys identical to `azure_postgresql` (`host`, `port`, `database`, `username`, `sslmode=verify-full`, `password_ref`). Change `AZURE_EXECUTABLE_SELECTIONS` so `(relational_adapter, tenant_postgresql)` and `(index_adapter, tenant_pgvector)` map to the new provider and additionally require data-plane `status = ready`. Reject a secret reference already used by the tenant's other PostgreSQL provider.

**Rationale:** The existing one-active-per-provider index then gives "one data plane per tenant" for free, and the read-only provider keeps its least-privilege meaning.

**Alternatives considered:**
- A `purpose` column on `azure_postgresql` — ruled out: breaks the partial unique index semantics and every consumer that treats that provider as read-only.

### Decision 4: Resolver builds cached per-tenant async and sync engines

**Choice:** `EngineResolver` gains `resolve(tenant_id)` (async) and `resolve_sync(tenant_id)` (sync, for Celery workers). Resolution:

1. `tenant_id is None` → platform engine (control-plane access).
2. Look up the data-plane record through a short-TTL (default 15 s) in-process cache of control-plane rows.
3. `platform` → platform engine.
4. `tenant_owned` and `status = ready` → engine cached by `(tenant_id, connection_id, connection.updated_at)`. Built with `asyncpg`/`psycopg2`, an SSL context with certificate and hostname verification, `pool_size`/`max_overflow` from settings (small defaults, e.g. 2/2), `connect_timeout`, and `statement_timeout` via server settings. Password resolved through the existing secret-reference resolution used by `data_sources/service.py`.
5. Any other status → raise `DataPlaneNotReady(status_class)`; resolution or connect failure → raise `DataPlaneUnavailable(reason_class)`.

The cache is bounded (LRU, configurable max engines) and disposes evicted engines. Lifecycle operations (pause, replace, retire) bump `updated_at` on the connection and the data-plane row; other processes observe it within the TTL. A shared `tenant_session(tenant_id)` / `tenant_sync_session(tenant_id)` helper sets `search_path` exactly as `tenant_context.get_session` does now. All worker `create_engine(settings.database_url_sync)` calls for tenant data are replaced; an architecture test greps for direct construction outside `database.py`, `seed.py`, `verify_schema.py`, and MLflow bootstrap.

**Rationale:** Minimal call-site churn (sessions change how they are obtained, not what they run), explicit no-fallback, and bounded resource use per tenant.

**Alternatives considered:**
- PgBouncer per tenant — ruled out for v1: extra infrastructure per customer with no functional gain at current scale.
- No cache (engine per request) — ruled out: TLS handshake per request to a remote server dominates chat latency.

### Decision 5: Tenant-store schema = checked-in baseline + ordered Python revisions, shared with Alembic

**Choice:** New package `src/shared/tenant_store/`:

- `baseline.py` — `statements(schema: str) -> list[str]`, idempotent (`IF NOT EXISTS`), reproducing `tenant_template` at the current Alembic head, including generated `chunk_tsv`, HNSW index, materialized views, and a new `platform_store_meta(store_id uuid, tenant_id, schema_revision, provisioned_at)` table.
- `revisions/NNNN_<name>.py` — each exposes `REVISION`, `statements(schema) -> list[str]`, idempotent.
- `apply.py` — applies baseline + pending revisions to one engine/schema and records `schema_revision`.
- `migrate.py` — CLI run after `alembic upgrade head`: iterates `tenant_owned` tenants in `ready`/`migration_required`, applies pending revisions per store, isolates failures, sets `migration_required` below `MIN_SUPPORTED_TENANT_STORE_REVISION`.

Going forward, a tenant-scoped Alembic migration calls the same revision's `statements()` inside its `tenant_template` + `pg_namespace` loop, so the DDL is written once. A parity test runs `alembic upgrade head` on a scratch platform database and `apply` on an empty scratch database, then compares `information_schema`/`pg_indexes`/`pg_matviews`/`pg_constraint` for the tenant schema.

**Rationale:** Running Alembic against a tenant store would create platform `public` tables there and replay 40+ historical migrations that assume platform state. Runtime `pg_dump` would need platform database access and binaries in workers. Pure statement builders match the existing `build_role_statements` / `build_entity_table_statements` convention and are testable without a database.

**Alternatives considered:**
- Alembic with a separate `version_locations` branch per store — ruled out: history is intertwined with public DDL; branch maintenance cost is high.
- Clone from platform template over the network — ruled out: couples provisioning to platform DB reachability from customer network and copies no data-free guarantees.

### Decision 6: Provisioning runs as a durable Celery task with compare-and-set

**Choice:** Successful activation of `azure_postgresql_data_plane` (or `POST /api/v1/data-plane/provision` retry by a tenant admin) CAS-sets `awaiting_store|provisioning_failed → provisioning` and enqueues `provision_tenant_data_plane(tenant_id)` on a `data_plane` queue served by the document-service Celery worker (same RabbitMQ as ADR-012). The task: verify store identity rules; `CREATE EXTENSION IF NOT EXISTS vector`; `CREATE SCHEMA IF NOT EXISTS`; apply baseline + revisions; write `platform_store_meta` with a new `store_id` (or verify existing); run `build_role_statements` for the tenant schema (or verify pre-created role grant); reconcile generated entity tables from `public.entity_definitions`; CAS `provisioning → ready` storing `store_id` and revision. Failures map to finite reason classes and CAS to `provisioning_failed`.

**Rationale:** DDL over a remote network can exceed request timeouts; idempotent statements make retries safe; CAS prevents double provisioning.

**Alternatives considered:**
- Synchronous provisioning in the activation request — ruled out: timeouts and partial state on client disconnect.

### Decision 7: Content-free registry written after tenant commit, reconciled periodically

**Choice:** `public.tenant_document_registry(document_id, tenant_id, source_type, status, file_size_bytes, checksum, retention_mode, created_at, updated_at, PK(tenant_id, document_id))`. A single `registry.record(tenant_id, …)` helper is called after tenant-store commits in ingestion, OCR status transitions, blob-sync replace/hide, and deletion. A Celery beat task reconciles per tenant (skipping unreachable stores). Quota checks (`dashboard.py` and upload path), system-admin counts, and dashboard totals read the registry. Alembic migration backfills from existing platform schemas.

**Rationale:** Two databases cannot share a transaction; the tenant store is authoritative and the registry is a repairable projection. Writing it for all tenants keeps one code path.

**Alternatives considered:**
- Registry-first write — ruled out: a registry row could exist for a document whose tenant row never committed, inflating quota.

### Decision 8: Typed data-plane errors, shared handlers, retry-by-countdown with circuit breaker

**Choice:** `DataPlaneNotReady` → 409 `TENANT_DATA_PLANE_NOT_READY`; `DataPlaneUnavailable` → 503 `TENANT_DATA_PLANE_UNAVAILABLE`. Registered by a shared FastAPI exception-handler installer used by all services. Driver exceptions raised inside `tenant_session` for `tenant_owned` tenants (`OSError`, `asyncpg` connection/auth errors, SQLAlchemy `OperationalError`/`InterfaceError`, timeouts) are classified into `unreachable|auth_failed|timeout` and re-raised as `DataPlaneUnavailable`; the original message is dropped before logging. Health writes to the data-plane row are rate-limited per tenant; a beat probe (`SELECT 1`) updates health for `tenant_owned` tenants.

Celery tasks catch `DataPlaneUnavailable` and `self.retry(countdown=backoff)` up to `NER_DATA_PLANE_TASK_MAX_RETRIES` (applies even to tasks that today use `max_retries=0`, for this error class only), then record failed-retryable. While a tenant's recorded health is `unreachable` and younger than the probe interval, resolution fails fast without connecting (circuit breaker), so retrying tasks release worker slots in milliseconds. In-process OCR (`asyncio.create_task`) discards produced text on failure; a recovery sweep re-dispatches that tenant's documents stuck in `processing` once health returns to `healthy`.

Upload pre-check: resolve engine and run `SELECT 1` before reading the request body into the content store.

**Rationale:** Uniform error contract, no content leaks through driver messages, no platform buffering, bounded shared-worker impact.

**Alternatives considered:**
- Mark service `/health` not-ready on tenant outage — ruled out: one customer would take the service out of rotation for all.

### Decision 9: Content routes gated by a shared dependency

**Choice:** Each service's tenant-context middleware resolves the data-plane record and, for content routers, a dependency raises `DataPlaneNotReady` unless `ready`. Gateway tenant-admin, data-source, and data-plane status routes are exempt.

### Decision 10: Cross-plane reads are explicit

**Choice:** `entity_definitions`, `external_pg_contracts`, integration profile, and connections stay in `public`. Code that combines them with tenant data (entity reconciler, chat SQL whitelist, sql role grants, retrieval tool registry) reads the control plane through the platform session and the tenant schema through the resolved session — two sessions, never a cross-schema SQL join against `public` from a tenant session. A source check flags `public.` references inside SQL executed on a tenant session (for example `documents.py` joins `public.tenant_users` for uploader names — that becomes a second lookup).

**Rationale:** On a tenant store `public.tenant_users` does not exist; any such join would fail or, worse, hit a customer-created table of the same name.

### Decision 11: Local Compose tenant store

**Choice:** Add `postgres-tenant-store` (`pgvector/pgvector:pg16`) with its own credentials resolved through `env://`. The secure tester detects Azure via `current_setting('azure.extensions', true)`; when unset it falls back to `pg_available_extensions`, so the same checks run locally.

### Decision 12: Feature flag for shared environments

**Choice:** `NER_TENANT_OWNED_DATA_PLANE_ENABLED` (default `true` in local dev, `false` elsewhere). When false, creating a `tenant_owned` tenant and creating `azure_postgresql_data_plane` drafts are rejected; existing `tenant_owned` tenants still route to their stores (never to the platform).

## Risks / Trade-offs

- [Resolver cache staleness lets a paused connection serve for up to the TTL] → Pause/retire invalidate the local process cache immediately; TTL bounds other processes to 15 s; documented in the portal confirmation.
- [A source path still constructs the platform engine for tenant data, silently writing residency content to the platform] → Architecture test over `src/`, integration test asserting zero rows in platform DB for a residency tenant after a full upload→extract→chat flow, no `tenant_<id>` schema on platform DB.
- [SQL executed on tenant sessions references `public.*`] → Source check (Decision 10) plus residency integration suite runs against a store with no `public` platform tables.
- [Parity drift between Alembic and tenant-store revisions] → Parity test in CI; tenant-scoped migrations call revision builders.
- [Registry drift] → Tenant store authoritative; periodic reconciliation; quota slightly stale at worst.
- [Ephemeral working copy expires during a long outage, making documents non-reprocessable] → Failed-retryable documents surface with reason class; `source_only` sync re-reads from source; documented residency trade-off.
- [Latency to remote store raises chat p95 and OCR time] → Pooled cached engines, batched span inserts retained; targets deferred (DEC-004) and measured in verification.
- [Customer DBA refuses role creation] → Pre-created `NOLOGIN` role fallback verified by the tester.
- [Customer tampering in the tenant store] → Out of platform control; schema revision and identity checks detect gross drift only; stated in ADR-017.
- [Many residency tenants multiply deploy time] → Per-store migration runs isolated and bounded concurrently; failures do not block startup.
- [Offboarding cannot delete tenant-store content] → Retirement response and portal copy state customer responsibility.

## Migration Plan

1. Alembic `043_tenant_data_plane`: create `public.tenant_data_planes` (backfill `platform/ready` for all tenants), `public.tenant_document_registry` (backfill from platform schemas), add `azure_postgresql_data_plane` to the provider CHECK, add `platform_store_meta` to `tenant_template` and existing platform schemas (with generated `store_id`, current revision). Additive only (ADR-014).
2. Ship `src/shared/tenant_store` baseline at head `043`, parity test, and `migrate.py`; add the migrate step after `alembic upgrade head` in the Compose migration service.
3. Ship resolver, sessions, error handlers, and worker engine replacement. For platform tenants behaviour is identical — verify with the existing suite (diff against baseline failing ids).
4. Ship registry writes/readers and reconciliation.
5. Ship provider, tester, provisioning task, data-plane API, portal and admin-console UI behind the feature flag.
6. Enable in local dev; run the residency integration suite against `postgres-tenant-store`.

Rollback: disable the flag (no new residency tenants or drafts). Code rollback to a version without the resolver is unsafe once a `tenant_owned` tenant exists because the old code would route it to the platform; therefore rollback requires either no `tenant_owned` tenants or roll-forward. New public tables and columns are additive and left in place.

## Open Questions

- ADR-017 revisits ADR-001's single-instance topology and ADR-011's "one PostgreSQL connection, read-only credential" catalog statement; ADR-017 records both as partial supersession without editing either file.
- Fine-tuned model artifacts and MLflow runs for residency tenants stay on platform storage — confirm as a stated exclusion.
- LLM/embedding provider transit — confirm tenant-facing residency statement excludes processing in transit.
- Default resolver TTL, pool sizes, retry budget, and probe interval are proposed values pending DEC-004 targets.
- Open changes `external-postgresql-chat-sql-generation` and `harden-blob-sync-scheduling-and-retention` must be archived or rebased first; both touch engine acquisition or the sync ledger.
