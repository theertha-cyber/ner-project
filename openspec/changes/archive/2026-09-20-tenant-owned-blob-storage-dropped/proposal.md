## Why

A tenant can now keep its relational data and vectors in a PostgreSQL server it owns (ADR-017), but the bytes of an uploaded document still land in platform MinIO. That gap is visible in the code: `tenant-postgresql-data-plane` had to *forbid* `platform_blob` retention for a `tenant_owned` tenant, because there was no tenant-side blob store to retain an original in — so those tenants can only choose `ephemeral` or `source_only`, and lose durable originals to buy residency. The seam for closing this is already cut and inert: `CONTENT_STORE_ADAPTERS` records `tenant_azure_blob`, the resolver maps it to an Azure provider, and `DocumentIngestionService._write_content` carries a docstring stating that the profile's `content_store_adapter` is deliberately not consulted. This change consults it.

## What Changes

- Make `content_store_adapter = tenant_azure_blob` **executable**. When a tenant has an active, write-capable tenant blob connection, every document byte the platform stores for that tenant is written to the tenant's own Azure Blob container instead of platform MinIO.
- Add an Azure Blob content-store adapter behind the existing three-operation `ContentStore` boundary (`put` / `open` / `delete`). No caller learns that the backend changed: no container name, account, credential, or key rule crosses the boundary.
- Route **both** store instances per tenant, not just the durable one. `get_durable_store()` and `get_working_store()` become tenant-scoped. An `ephemeral` document's working copy is the same tenant's bytes under a shorter lifetime, so it goes to the same tenant-owned container; bounded lifetime is enforced by a container lifecycle rule rather than by the application, exactly as it is on MinIO today.
- Cover **chat attachments** by construction: they are ingested through `DocumentIngestionService`, so routing the store routes them.
- Add a new approved connection provider, `azure_blob_content_store`, with **write and delete** privileges on a platform-dedicated container — distinct from the existing read-only `azure_blob` source provider, which keeps its least-privilege meaning. This mirrors the `azure_postgresql` / `azure_postgresql_data_plane` split (ADR-017, Design D3) and gets "one content store per tenant" from the existing one-active-per-provider index for free.
- Record on every document **which content store produced its reference**. A `StorageReference` is opaque and carries no backend identity, so a tenant that activates a blob store after documents already exist would otherwise have unreadable history. The recorded kind — the value each adapter already declares as `kind` — routes `open` and `delete`. Existing rows backfill to `platform_minio`.
- **Lift** the ADR-017 constraint: `platform_blob` retention becomes permitted for a `tenant_owned` tenant, but only while that tenant holds an active content-store connection. The rejection stays in place for a `tenant_owned` tenant without one.
- Fail closed. If the tenant's container is unreachable, uploads are rejected before bytes are accepted and content reads return a typed unavailable error. No platform-side buffering, no fallback to MinIO — a silent fallback would write tenant content to platform infrastructure, which is the one outcome this change exists to prevent.
- **Explicitly out of scope, and stated as a residency exclusion:** fine-tuned model artifacts (`tenants/{id}/models/v{n}/`) and MLflow run artifacts (`s3://ner-platform/mlflow/`) remain in platform MinIO for every tenant. They are platform operational output, not tenant-submitted content, and MLflow's artifact root is one server-wide setting rather than a per-tenant one.
- **BREAKING (spec-level):** the content store is no longer a single process-wide instance; every call site must resolve a store for a tenant. `reset_stores()` semantics change accordingly.

## Capabilities

### New Capabilities

- `tenant-content-store-routing`: Resolving a tenant's content store from its profile and active connection at write time, tenant-scoped durable and working instances, fail-closed behaviour with no MinIO fallback, and the bounded per-tenant client cache.
- `tenant-blob-content-store-provisioning`: The `azure_blob_content_store` provider — its closed configuration, write-capable test checks (container reachable, round-trip put/open/delete, lifecycle rule present for working copies), activation evidence, pause/retire semantics, and same-container replacement for credential rotation.
- `content-store-backend-attribution`: Recording the producing store's kind alongside every storage reference, routing `open` and `delete` by the recorded value, backfill of existing rows, and the prohibition on re-deriving the backend from the profile's current state.

### Modified Capabilities

- `original-document-storage`: Retention modes resolve to a tenant-owned store when one is active; the working copy's bounded lifetime may be enforced by a tenant container lifecycle rule; a storage reference is accompanied by a recorded backend kind.
- `tenant-integration-profile`: `tenant_azure_blob` becomes executable for a tenant holding an active `azure_blob_content_store` connection; `platform_blob` retention becomes permitted for a `tenant_owned` tenant on that same condition, and stays rejected without it.
- `tenant-data-source-control-plane`: Adds the `azure_blob_content_store` provider and its write-capable test checks, one active per tenant.
- `tenant-data-source-portal`: Tenant administrators can create, test, activate, and monitor a content-store connection, and see which backend their content is stored in.
- `azure-blob-source-sync`: The `SYNC_ALLOWED_RETENTION` constraint is relaxed — a sync may proceed under `platform_blob` retention when the durable store is the tenant's own, since the objection was durable platform-side storage of synced content, not durable storage as such.

## Impact

- **Code:** `src/document_service/content_store/*` (new adapter, tenant-scoped instances, contract unchanged), `src/document_service/ingestion/service.py` (`_write_content`, `_durable`, `_working`), `src/document_service/services/ocr_worker.py` (store resolution at terminal state), `src/document_service/blob_sync/{sync,reopen}.py`, `src/shared/integration_profile/{adapters,service}.py`, `src/shared/data_sources/{providers,resolver,service}.py`, document content-read routes in `document_service` and `chat_api`, portal data-source settings.
- **Data:** new provider value on `tenant_data_source_connections`; a `content_store_kind` column on `documents` in the tenant-store baseline plus a tenant-store revision, backfilled to `platform_minio`.
- **Dependencies:** synchronous `azure.storage.blob.BlobServiceClient`. The package is already a dependency, but `blob_sync` uses the `.aio` client; the `ContentStore` protocol is synchronous, so the adapter uses the sync client rather than making the boundary async.
- **Operations:** tenant-provided container with write access, a lifecycle rule on the working prefix, per-tenant network paths and credentials. Local Compose gains an Azurite container to stand in for a tenant-owned blob store.
- **Unchanged:** model artifacts and MLflow (stated exclusion above), the `ContentStore` contract's three operations, platform tenants' behaviour, and the read-only `azure_blob` source provider's privileges.

## Decisions

Settled 2026-09-18, before design:

- **Existing bytes are not migrated.** Documents written before activation stay in MinIO and remain readable through their recorded backend kind. A tenant's content may be split across two backends indefinitely; that is accepted in exchange for no bulk-copy job, no partial-migration failure states, and no activation precondition on tenant emptiness. A migration, if ever wanted, is a later change that this change's attribution column makes possible.
- **One container, two prefixes.** The tenant provisions a single container; durable and working bytes separate by prefix, with a prefix-scoped lifecycle rule on the working prefix. One tenant-side artifact to provision, one credential to rotate.
- **The slots are independent.** A `platform` data-plane tenant may point its content store at its own blob while its rows stay on the platform server. No cross-slot constraint is introduced; the only condition on `tenant_azure_blob` is an active content-store connection.

## Open Questions

- **Working-copy expiry is the tenant's to enforce.** If the tenant removes or misconfigures the prefix lifecycle rule after activation, `ephemeral` retention silently stops being bounded. Assumed: the activation test asserts the rule exists and refuses the connection without it; ongoing drift is not detected. Confirm whether periodic re-assertion is required, or track as an accepted risk.
- **Deletion on retire.** Retiring a content-store connection makes content inaccessible to the platform; deleting the objects is a customer action, consistent with the ADR-017 offboarding position. Confirm for contracts.
- **Read-path latency.** Every content read for an active tenant becomes a cross-network call to the tenant's Azure account rather than an in-cluster MinIO call. Consistent with DEC-004, latency and recovery targets remain deferred; confirm that deferral still holds for the interactive chat-attachment read path specifically.
