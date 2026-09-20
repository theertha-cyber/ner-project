## Why

Some tenants require that their sensitive derived data — OCR text, chunks and embeddings, extracted entities, chat history, and annotations — reside in a PostgreSQL server they own. Today every tenant schema lives on the single platform PostgreSQL instance (ADR-001), and the only tenant-owned PostgreSQL the platform accepts is a read-only business source (ADR-011, ADR-013). The seams for relocation already exist but are inert: `EngineResolver` ignores `tenant_id`, and the integration profile records `relational_adapter = tenant_postgresql` / `index_adapter = tenant_pgvector` without being able to execute them. ADR-017 decides how to make them real.

## What Changes

- Introduce a per-tenant **data plane** (`platform` | `tenant_owned`) recorded in the control plane and chosen by the System Admin at tenant creation; it cannot change afterwards. Existing tenants remain `platform`.
- For `tenant_owned` tenants, the **entire** `tenant_<id>` schema (documents, text spans, chunks with pgvector/HNSW, extraction runs and entities, generated entity tables, analytics materialized views, conversations and chat messages, feedback, conversation entity state, annotation tasks/labels/spans/suggested spans/imported annotations, sync ledger, schema index, tenant audit log, training jobs, model versions) lives in the tenant's Azure Database for PostgreSQL – Flexible Server. No table is split across servers.
- Add a new approved connection provider, `azure_postgresql_data_plane`, with write/DDL privileges in a platform-dedicated database, distinct from the read-only `azure_postgresql` source. It reuses the ADR-011 lifecycle, secret references, TLS `verify-full`, and activation evidence, plus residency-specific test checks (server version, `vector` availability, `CREATE` privilege, query-role creation, empty target schema).
- Route every tenant-data engine through `EngineResolver`: platform engine for `platform` tenants; a cached, bounded per-tenant engine for `tenant_owned` tenants; **never** a fallback to the platform engine. Worker-local `create_engine(settings.database_url_sync)` calls for tenant data are replaced.
- Provision the tenant schema into the tenant store from a versioned tenant-store schema baseline plus ordered tenant-store revisions, record a per-store schema revision and store identity, and apply pending revisions on deploy. Fleet operations enumerate tenants from the control plane instead of `pg_namespace`.
- Add a content-free `public.tenant_document_registry` (id, tenant, source type, status, size, checksum, retention mode, timestamps) maintained for **all** tenants, used for quotas, counts, and system-admin views. `filename` stays in the tenant store only.
- Fail closed per tenant when its store is unreachable: `503 TENANT_DATA_PLANE_UNAVAILABLE` for API calls, uploads rejected before bytes are accepted, background tasks retried with bounded backoff then parked. No platform-side buffering of tenant content. Service readiness continues to reflect only platform dependencies.
- Constrain `tenant_owned` tenants to `ephemeral` or `source_only` retention; `platform_blob` is rejected.
- **BREAKING (spec-level):** tenant provisioning no longer always creates a platform schema; tenant-scoped migrations must additionally ship a tenant-store revision; system-admin document counts come from the registry.

## Capabilities

### New Capabilities

- `tenant-data-plane-routing`: Per-tenant data-plane assignment and status in the control plane, engine resolution with no platform fallback, readiness gating of tenant content routes, control-plane tenant enumeration for fleet operations.
- `tenant-residency-store-provisioning`: Materialising the tenant schema into a tenant-owned store, store identity, per-store schema revision tracking, deploy-time revision application, and the tenant-store revision discipline for future migrations.
- `tenant-data-plane-failure-isolation`: Fail-closed behaviour, error contract, background-task retry/park, no platform-side buffering, content-free per-tenant store health signal.
- `tenant-document-registry`: Content-free control-plane document registry for all tenants, its maintenance, reconciliation, and consumers.

### Modified Capabilities

- `tenant-data-source-control-plane`: Adds the `azure_postgresql_data_plane` provider, its residency-specific test checks, one active per tenant, pause/retire semantics, and same-store replacement for credential rotation.
- `tenant-integration-profile`: `tenant_postgresql` / `tenant_pgvector` become executable only for a `tenant_owned` tenant with an active, provisioned data-plane connection; `tenant_owned` tenants reject `platform_blob` retention.
- `tenant-provisioning`: Tenant creation accepts a data-plane mode; `tenant_owned` tenants are created without a platform schema in `awaiting_store`.
- `tenant-schema-migrations`: Atomic template cloning applies to the platform plane only; tenant-scoped schema changes also propagate to active residency stores through tenant-store revisions.
- `tenant-data-source-portal`: Tenant administrators can create, test, activate, and monitor a data-plane connection and see data-plane status; content areas show a safe not-ready state.
- `admin-console`: System Admin chooses the data plane at tenant creation and sees data-plane status; document counts come from the registry.

## Impact

- **Code:** `src/shared/database.py` (resolver), `src/shared/tenant_context.py` and each service's tenant-context middleware, worker engine factories in `extraction_service`, `training_service`, `analytics_service`, `document_service` (OCR, ingestion, blob sync), `src/shared/entity_views.py` reconciler, `src/chat_api/services/sql_execution_role.py`, `src/gateway/services/tenant_service.py`, `src/gateway/verify_schema.py`, `src/gateway/api/v1/dashboard.py`, `src/shared/data_sources/*`, `src/shared/integration_profile/*`, `src/shared/retrieval/retriever.py` (engine only), gateway data-source and admin APIs, portal settings and admin pages.
- **Data:** new public tables (`tenant_data_planes`, `tenant_document_registry`) with backfill for existing tenants; new provider value on `tenant_data_source_connections`; a new tenant-store schema baseline and revision directory.
- **Operations:** per-store migration runs on deploy, per-tenant network paths and credentials, local Compose gains a second pgvector PostgreSQL acting as a tenant-owned store.
- **Unchanged:** read-only external PostgreSQL chat (ADR-013), Azure Blob sync semantics (ADR-012) apart from the retention constraint, platform tenants' behaviour.

## Open Questions

- **Fine-tuned model artifacts and MLflow runs** trained on a `tenant_owned` tenant's spans remain in platform MinIO/MLflow. Assumed acceptable and stated as an explicit residency exclusion; confirm.
- **LLM and embedding calls** process tenant text in transit through platform-configured providers. Assumed out of scope for at-rest residency; confirm the tenant-facing statement.
- **Offboarding:** retiring a data-plane connection makes content inaccessible to the platform; deleting content inside the tenant store is a customer action. Confirm this is acceptable for contracts.
- **Latency and recovery targets** for tenant stores remain deferred (consistent with DEC-004 in the data-sources requirement).
- The two open changes `external-postgresql-chat-sql-generation` and `harden-blob-sync-scheduling-and-retention` touch engine use and the sync ledger; they should be archived or rebased before implementation starts.

## Change Notes

- 2026-09-14: `external-postgresql-chat-sql-generation` (30/39 tasks) and `harden-blob-sync-scheduling-and-retention` (0 tasks, no-tasks state) are not archived. Their in-progress work already exists as uncommitted diffs on this branch (`external-tenant-data-sources`), touching `src/chat_api/services/external_postgres_chat.py`, `src/document_service/blob_sync/*`. Decision: treat as rebased onto this branch and proceed with `tenant-postgresql-data-plane` implementation on top, rather than blocking on their archival.
