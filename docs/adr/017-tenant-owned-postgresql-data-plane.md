# 017. Tenant-Owned PostgreSQL Data Plane (Data Residency)

## Status
Proposed

Partially supersedes ADR-001 (single-PostgreSQL-instance topology only; schema-per-tenant and control-plane rules remain in force) and ADR-011 (the two-provider catalog and "the Azure PostgreSQL credential is read-only" statement, for the new data-plane provider only). Neither prior ADR file is edited.

## Context

ADR-001 places every tenant's content in a `tenant_<id>` schema on one platform PostgreSQL instance. Some tenants require that their sensitive derived data — OCR text, chunks and embeddings, extracted entities, chat history, annotations — reside in a PostgreSQL server they own and operate. ADR-011 and ADR-013 already admit a tenant-owned Azure Database for PostgreSQL, but only as a **read-only business source**: the platform never writes to it and never owns anything inside it. Residency is a different relationship. The platform must own a schema in the tenant's server and run the whole pipeline against it.

The derived layer does not merely use PostgreSQL; it writes PostgreSQL at run time (`tenant-pluggable-data-architecture.md` §6 P3, archived change `tenant-pluggable-data-foundation`):

- `entity_views.py` emits `CREATE TABLE` / `ALTER TABLE … ADD COLUMN` from tenant entity definitions, and `relational_projection.py` upserts with `ON CONFLICT … DO UPDATE`.
- Migrations `011`, `024` create materialized views, a generated `tsvector` column and an HNSW index per schema.
- `sql_execution_role.py` creates a `NOLOGIN` role assumed per statement with `SET LOCAL ROLE`.

The tenant schema is also **internally coupled**. Foreign keys run from `document_text_spans`, `document_chunks`, `spans`, `suggested_spans` to `documents`; from `extracted_entities` to `extraction_runs`; from `annotation_labels` to `annotation_tasks`. The OCR worker writes `document_text_spans` and `documents.status` in one commit (`ocr_worker.py`). Retrieval filters chunks with `NOT EXISTS` against `azure_blob_hidden_documents` (`retriever.py`). Chat Text-to-SQL joins `documents` to `document_entities`. A table-by-table split of the schema across two servers breaks all of these, because PostgreSQL cannot join or commit across servers.

Seams already exist: `EngineResolver` in `src/shared/database.py` is the single engine choice point and accepts a `tenant_id` it currently ignores; the integration profile records `relational_adapter = tenant_postgresql` and `index_adapter = tenant_pgvector` as recordable-but-not-executable selections.

## Decision

### 1. The unit of residency is the whole tenant schema

A tenant is assigned exactly one **data plane**: `platform` (default, today's behaviour) or `tenant_owned`. For a `tenant_owned` tenant, the complete `tenant_<id>` schema — every table, generated entity table, materialized view, index and the chat query role grants — lives in the tenant's server and nowhere else. The schema definition, migrations, queries and generated DDL are identical on both planes; only the engine differs. No table of the tenant schema is split across servers.

Tenant data plane (tenant server when `tenant_owned`):
`documents` (content-bearing row, including `filename`), `document_text_spans`, `document_chunks` (pgvector + HNSW), `extraction_runs`, `extracted_entities`, `document_entities`, generated `subject` / `e_*` tables, `mv_*` materialized views, `conversations`, `chat_messages`, `chat_message_feedback`, `conversation_entity_state`, `annotation_tasks`, `annotation_labels`, `spans`, `suggested_spans`, `imported_annotations`, `azure_blob_*` sync ledger, `external_pg_schema_index`, `audit_log`, `training_jobs`, `model_versions`.

Control plane (platform `public`, always):
`tenants`, `tenant_users`, `widget_api_keys`, `audit_events`, `entity_definitions`, `tenant_integration_profiles`, `tenant_data_source_connections` and idempotency, `external_pg_contracts`, and a new content-free **document registry**.

### 2. A content-free document registry in the control plane, for all tenants

`public.tenant_document_registry` holds only: document id, tenant id, source type, status, size, checksum, retention mode, created/updated timestamps. It never holds filename, OCR text, error text, or any derived content. It is written for every tenant on both planes, so quota, counts, billing and fleet operations have one code path and do not reach into customer infrastructure. The tenant-schema `documents` row remains authoritative for content; the registry is a projection maintained by the ingestion and status-transition paths.

`entity_definitions` stays in the control plane: it is configuration, it drives runtime DDL and the SQL allowlist, and it must be readable while the tenant store is being provisioned or is unavailable. Its `examples` field may contain real values; tenant administrators are informed it is platform-held.

### 3. A distinct connection provider with write privileges

Residency uses a new approved provider, `azure_postgresql_data_plane`, alongside (never instead of) the read-only `azure_postgresql` source. It reuses the ADR-011 lifecycle (`draft → validated → active → paused/error → retired`), closed typed configuration, `verify-full` TLS, secret references (`env://` locally, Vault in shared environments), and `network_approved` + `governance_approved` activation evidence. It must not reuse a business-source connection's credentials. The integration profile selections `relational_adapter = tenant_postgresql` and `index_adapter = tenant_pgvector` become executable only with an active connection of this provider.

Supported target: **Azure Database for PostgreSQL – Flexible Server, PostgreSQL 16+**, in a database dedicated to the platform. The connection test verifies, as finite outcome classes: TLS reachability, server version, `vector` available in `azure.extensions` and creatable, `CREATE` privilege on the database, ability to create or be granted the chat query role, and absence of a pre-existing non-empty `tenant_<id>` schema.

Customer prerequisites: dedicated database; `VECTOR` allow-listed; a login role owning that database (or holding `CREATE`); private endpoint or TLS public endpoint with platform egress allowlisting. Where the customer refuses role creation, a customer-pre-created `NOLOGIN` query role granted to the login role is accepted.

### 4. New tenants only; plane is fixed

The data plane is chosen by the system administrator at tenant creation, recorded in `public.tenant_data_planes`, and cannot change afterwards. A `tenant_owned` tenant is created **without** a platform schema and starts in status `awaiting_store` (lifecycle: `awaiting_store → provisioning → ready`, with `provisioning_failed`, `migration_required`, `paused`, and terminal `store_retired`). Until its residency connection is active and provisioned, every tenant content route and task fails with `TENANT_DATA_PLANE_NOT_READY`; only tenant administration and data-source settings are available. Moving an existing tenant between planes is out of scope and requires a later ADR. A retired residency connection moves the tenant to `store_retired`, which is terminal for content access.

### 5. Provisioning and migrations run per data plane

Provisioning on a tenant server cannot clone `tenant_template`, which does not exist there. The platform instead materialises the tenant schema from a checked-in, idempotent tenant-store baseline plus ordered tenant-store revisions (pure statement builders, also called by tenant-scoped Alembic migrations so DDL is written once), then records a store identity and schema revision in `<tenant schema>.platform_store_meta`. A parity test keeps the baseline + revisions identical to `tenant_template` at Alembic head. Deploys run `alembic upgrade head` on the platform database and then apply pending tenant-store revisions to each residency store; a store below the platform's minimum supported revision, or whose migration fails, is `migration_required` and fails closed until migrated. A replacement connection must reach the same store identity. Fleet operations that currently enumerate `pg_namespace` (`entity_views` reconciler, `sql_execution_role` provisioning, `verify_schema`, system-admin dashboard) enumerate tenants from the control plane and resolve each tenant's engine.

### 6. Engine routing and failure isolation

`EngineResolver.resolve(tenant_id)` returns the platform engine for `platform` tenants and a cached, bounded per-tenant engine for `tenant_owned` tenants, built from the active connection and resolved secret. Worker-local `create_engine(settings.database_url_sync)` calls for tenant data are replaced by the resolver. The resolver never falls back to the platform engine for a `tenant_owned` tenant.

When a tenant store is unreachable, **only that tenant fails closed**: API requests return `503 TENANT_DATA_PLANE_UNAVAILABLE`; uploads are rejected before bytes are accepted; Celery tasks retry with bounded backoff and then park as failed-retryable. No tenant content is buffered, queued or cached on the platform side during the outage. Service readiness reflects the platform database only; per-tenant store health is a separate, content-free control-plane signal.

### 7. Originals do not rest on the platform

A `tenant_owned` tenant's integration profile retention mode must be `ephemeral` or `source_only`; `platform_blob` is rejected at profile validation and at activation. Ephemeral working copies are deleted after processing under the existing retention rules.

### Threat model (STRIDE)

| Threat | Control |
|---|---|
| Spoofing | Engine resolved only from authenticated server-side tenant context and the tenant's active control-plane connection; TLS `verify-full`; queued task payloads carry tenant id, never connection data. |
| Tampering | Platform-owned dedicated database and schema; migrations are platform-authored and versioned per store; schema revision checked before use. Customer DBAs retain superior privileges — the platform cannot prevent customer-side tampering and does not claim to. |
| Repudiation | Content-free control-plane audit events for create, test, activate, provision, migrate, pause, retire, outage transitions. |
| Information disclosure | No fallback to the platform engine; no platform-side buffering during outage; registry is content-free; originals not retained; engine cache keyed by tenant and invalidated on connection change; endpoints, credentials, SQL and content excluded from logs, metrics, traces and audit payloads. |
| Denial of service | Per-tenant bounded pools and connect/statement timeouts; one tenant's outage cannot exhaust shared worker concurrency (bounded retries, parked tasks). |
| Elevation of privilege | Chat generated SQL still runs under the `NOLOGIN` query role via `SET LOCAL ROLE`; residency login role has rights only in its dedicated database; business-source and residency credentials are never shared. |

## Alternatives Considered

| Option | Why not chosen |
|---|---|
| Move a hand-picked set of tables, keep the rest on the platform | Severs foreign keys, single-transaction writes (OCR status + spans), retrieval `NOT EXISTS` filters, and chat SQL joins across two servers. Requires outbox/2PC and rewriting query paths. |
| Vendor-neutral relational/vector abstraction | The derived layer generates PostgreSQL DDL at run time; an abstraction must re-implement it per engine and delivers nothing until a non-PostgreSQL customer exists. |
| Reuse the read-only `azure_postgresql` provider | Different privilege model and purpose; sharing it couples a least-privilege read-only role to DDL rights and breaks one-active-per-provider semantics. |
| Allow migrating existing tenants in v1 | Needs write-freeze, dump/restore, verification and rollback tooling; deferred to keep v1 bounded. |
| Buffer writes on the platform during tenant outage | Tenant content would rest on platform infrastructure, contradicting the residency promise. |
| Keep `filename` in the control plane | Filenames routinely carry personal data. |
| Separate database per tenant on platform infrastructure | Solves isolation, not residency. |

## Consequences

Positive:
- Same schema, migrations, SQL and pipeline on both planes; one code path.
- Residency covers database rows and original files; the platform holds only configuration, identity and content-free metadata.
- Tenant outage is isolated to that tenant.

Negative:
- Operational surface multiplies per residency tenant: migrations, version windows, network paths, monitoring, support.
- Latency of OCR span inserts and chat retrieval now includes a network hop to the customer's server.
- Backup, restore, retention enforcement and final deletion of tenant content become shared with, and partly dependent on, the customer.
- Platform cannot fully delete a residency tenant's content alone; offboarding produces a customer-actionable instruction.
- `tenant_owned` tenants cannot use `platform_blob` retention, so reprocessing depends on the source.

## Related
- Amends: `001-tenant-data-isolation.md` — "single PostgreSQL instance" becomes "one data plane per tenant, platform or tenant-owned; schema-per-tenant on either".
- Extends: `011-tenant-scoped-azure-connection-control-plane.md` (new provider), `012-durable-azure-blob-source-synchronization.md` (retention constraint).
- Distinct from: `013-contract-governed-external-postgresql-chat.md` (read-only business source; unchanged).
- Architecture: `docs/architecture/tenant-pluggable-data-architecture.md` §6 P3, §8, §9.
- OpenSpec change: `tenant-postgresql-data-plane`.

## Revision History

- 2026-09-14: Initial proposal.
