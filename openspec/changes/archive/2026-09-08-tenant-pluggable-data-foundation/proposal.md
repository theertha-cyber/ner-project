## Why

Documents can only enter this platform one way — a multipart upload handled inline in `src/document_service/api/v1/documents.py:58`, which is simultaneously the HTTP route, the ingestion use case, the MinIO client, the persistence layer, and the job dispatcher. Every future document source would therefore need its own upload, storage, and processing path, and no tenant can be told "we will not keep your original documents" because the OCR worker selects its extraction branch by splitting the MinIO object key (`ocr_worker.py:197`).

This change installs the bounded first foundation of the target described in `docs/architecture/tenant-pluggable-data-architecture.md`: one application-owned ingestion entry point, one content-store boundary, explicit retention semantics, and developer-managed integration profiles that record adapter selection. It does not attempt any later capability. Four named follow-on changes carry the rest.

## What Changes

- **A document-ingestion use case is extracted from the upload route.** It becomes the only code path permitted to create a `documents` row: it owns id generation, validation, checksum, duplicate identification, retention resolution, the row write, and processing dispatch. The route keeps JWT and role resolution, the role-to-purpose rule, multipart mechanics, and status codes, and becomes the first adapter over the contract. Externally observable behaviour of `POST /api/v1/documents` is unchanged.
- **A content-store boundary is introduced** with three operations — put, open, delete. The existing `MinioStorageClient` becomes the default adapter for two configured instances: a durable store and a working store. The storage reference becomes an **output** of the store rather than a path invented by the route.
- **Retention becomes explicit, with three declared modes.** `platform_blob` retains the original durably. `ephemeral` writes a bounded working copy, uses it to complete processing, and deletes it at a terminal state — this is how no-retention is honestly delivered for platform upload. `source_only` persists nothing and reopens by asking the source; it is modelled now and becomes executable only when pull sources land.
- **Content acquisition is declared, not assumed.** A source declares itself `single_use` or `reopenable`. Platform upload is `single_use`, because once the HTTP request ends the browser cannot be asked again. The ingestion operation combines that declaration with the tenant's retention mode to decide how the worker will obtain bytes, records the outcome, and rejects the one impossible combination — `single_use` content with `source_only` retention.
- **BREAKING (internal contract, not HTTP):** processing is dispatched with document and tenant identity only, and resolves bytes from persisted state. `process_document` and `trigger_ocr` change signature. The OCR branch is selected from the document's resolved media type — declared type, then filename extension, then sniff — never from the storage key. `content_type`, currently a dead parameter on both functions, becomes authoritative.
- **Reprocessing becomes idempotent and honestly bounded.** Existing spans and chunks are purged before reprocessing, but only after bytes are successfully resolved. The transition to `processing` becomes conditional on the document still being `pending`. A reprocess request for a document whose bytes are no longer resolvable fails explicitly and leaves derived data intact.
- **Provenance and retention columns are added to `documents`** — origin, `source_type`, `source_id`, `external_id`, `source_version`, source timestamps, `origin_metadata`, `retention_mode`, and the ingesting actor's kind — all additive and defaulted, applied to `tenant_template` and looped over existing tenant schemas per the `030`/`034` pattern. No uniqueness constraint on the external identity. The storage reference continues to be persisted in the existing `blob_path` column; no second column for the same value is introduced.
- **Document visibility is aligned with retrieval.** The non-administrative list filter applies only to documents whose ingesting actor is a human; a system-ingested document is visible tenant-wide, so listing and chat citation cannot disagree.
- **Developer-managed integration profiles are introduced in control-plane storage**, recording adapter selection, typed non-secret configuration, and typed secret references — never credential values. Only the platform defaults are executable in this change; any other recorded selection cannot be activated.
- **Minimal choke-point cleanup, only where this foundation needs it:** the ten copies of `_schema(tenant_id)` collapse to one shared helper, and engine acquisition goes through a single resolver still returning today's process-global engine.

**Explicitly out of scope, architecturally preserved:** Keka, S3, Azure, and SharePoint source implementations; the pull-side `DocumentSource` contract; sync engine, discovery, checkpoints, scheduling, retries, and deletion reconciliation; tenant-hosted PostgreSQL routing and migrations; tenant-hosted or external vector stores; the retrieval and index boundary; direct querying of a tenant's business database; semantic schema contracts and tenant query validation; generic relational-database support; and customer self-service configuration.

**Removed from an earlier draft of this change:** the `Retriever` signature refactor. It does not unblock source-agnostic ingestion, MinIO independence, or no-retention processing, and it touches the chat path. It moves to the named `document-index-boundary` change.

## Capabilities

### New Capabilities

- `document-ingestion-boundary`: the application-owned ingestion contract — the normalized document a source adapter submits, the declared content-acquisition capability, what the use case owns versus what an adapter owns, platform upload as the first adapter, dispatch that carries no content, and the prohibition on source-specific behaviour downstream.
- `original-document-storage`: the content-store boundary (put, open, delete), the three retention modes and the content resolution each implies, the bounded working copy that makes ephemeral retention work, bounded reprocessability, and the prohibition on any consumer parsing the storage reference.
- `tenant-integration-profile`: control-plane storage of per-tenant adapter selection, the typed allowlisted configuration shape, the status model including an explicit `error` state, the rule that only platform defaults are executable, and secret references only.

### Modified Capabilities

- `document-ingestion`: the existing "SHALL store the file in MinIO at path `tenants/{tid}/documents/{docId}.{ext}`" requirement is restated in terms of the configured content store and the resolved retention mode; async OCR gains dispatch-by-identity, content resolution from recorded state, media-type authority, and reprocess idempotency. Adds document provenance and retention metadata, and document visibility by ingesting actor.
- `secret-hygiene`: extended to cover per-tenant integration credentials — typed references, rejection by declared schema rather than heuristic, resolution once at the edge, and the acknowledged deviation that runtime-created per-tenant references cannot be validated at process startup.

## Impact

**Code changed**

- `src/document_service/api/v1/documents.py` — upload route thinned to an adapter; provenance and retention written on insert; the non-administrative list filter narrowed to human-ingested documents.
- `src/document_service/services/ocr_worker.py` — dispatched by identity; bytes resolved from recorded retention mode; branch on media type; purge-after-resolve; conditional status transition; working-copy deletion at terminal state.
- `src/document_service/services/storage.py` — wrapped as the default content-store adapter for durable and working instances; key construction stays inside it; a delete operation is exposed.
- New package under `src/document_service/` for the ingestion use case, the content-store boundary, and the dispatcher.
- `src/shared/database.py` — engine acquisition behind a resolver.
- `src/shared/` — one shared `schema_for_tenant` helper replacing ten local copies across document, annotation (×5), chat (×2), extraction (×2), and the OCR worker.
- New Alembic migrations: additive columns on `tenant_template.documents` with the `DO $$` loop over existing `tenant_%` schemas; the integration-profile table in `public`.

**Explicitly unchanged**

Text extraction, chunking, embedding, reranking, rank fusion, the `Retriever` protocol and every retrieval implementation, the extraction service and its worker, entity post-processing, relational projection and generated entity tables, the chat graph, the annotation service, model serving, the training service, MLflow, and the portal. MinIO usage in `model_serving/services/model_loader.py` and `training_service/worker.py` is the model plane and is out of scope.

**Operational**

No new services and no new containers. One new configured storage instance — the working store — which requires an independent object-lifetime policy so an abandoned working copy expires without depending on the application. The migrations are additive and defaulted, so existing rows and queries keep working.

**Risk concentrated in one place:** this change touches the platform's only document entry point. The regression gate is that every existing **scenario** in `tests/test_document_ingestion.py` and `tests/test_document_content_hash.py` still passes, with the edits to those two files confined to mock patch targets and fixture DDL — never to a `GIVEN`, a `WHEN`, or an asserted outcome. The original "pass unmodified, clean `git diff`" gate was found unsatisfiable during implementation: those tests patch `documents.MinioStorageClient`, `documents.trigger_ocr`, and `documents.generate_uuid`, and `mock.patch` raises `AttributeError` on an absent attribute, so the gate directly contradicts the requirement that the route reference no content store. Their fixture also builds `documents` without the provenance columns this change writes. The behavioural diff on both files is reviewed line by line as evidence instead.

## Named follow-on changes

These are deferred deliberately. Each is a separate OpenSpec change, and none is a prerequisite of this one.

- **`document-metadata-column-reconciliation`** — resolve the `002`/`003` drift: `002` created `mime_type`, `file_size_bytes`, `storage_uri`; `003` added `content_type`, `file_size`, `blob_path`. Uploads write only the `003` set, while `sql_generator.py:24` advertises the `002` names to the LLM and `dashboard.py:694` reads `file_size_bytes` — always NULL. Also renames `blob_path` to `storage_reference`. Not fixed here because it touches the chatbot query surface and the least-privilege grant list derived from it. **Blocking prerequisite for `external-document-sources`**: a fetched document's media type and size must be trustworthy end-to-end before any non-upload source writes them.
- **`tenant-postgresql-data-plane`** — per-tenant PostgreSQL connection routing, per-tenant migration execution, provisioning into a customer database, private network connectivity, per-tenant health and failure isolation, observability, and tenant-owned pgvector running the same platform schema. Depends on the engine resolver introduced here.
- **`document-index-boundary`** — an index contract covering write, retrieve, and delete; pgvector as the default adapter; the `Retriever` signature reshape removed from this change; external index support only when a customer funds a complete retrieval integration including metadata filtering, delete-by-document, and a hybrid or explicitly accepted dense-only mode.
- **`external-document-sources`** — the pull-side `DocumentSource` contract, Keka, S3, and Azure Blob connectors, the sync engine, the external identity ledger and its uniqueness constraint, checkpoints, retries, scheduling, and deletion reconciliation policy, as designed in `docs/architecture/external-data-source-architecture.md`.
- **`tenant-structured-data-chat-tool`** — tenant-approved schema contracts, read-only connectors, generated-SQL validation, least-privilege execution, `ToolRegistry` integration, result provenance, and schema-drift handling for querying a tenant's existing business database at chat time.

## Open Questions

All decisions that block implementation have been resolved and are reflected consistently in design, specs, tasks, and verification. What remains needs human agreement, not further design.

- **A1 — Working-store transit is acceptable for the tenants we intend to serve.** Under `ephemeral` retention a document's bytes do transit platform-operated storage for the duration of processing. This is disclosed, bounded, and deleted at a terminal state, but it is not "the bytes never touch our infrastructure". A tenant that cannot permit that transit cannot use platform upload and must wait for a reopenable source. **Requires product and security agreement before the first such tenant is onboarded.**
- **A2 — The working store's expiry value.** The design requires an independent object-lifetime policy on the working store; the specific duration is an operational choice bounded below by the slowest realistic OCR run.
- **A3 — Non-administrative visibility of system-ingested documents.** Decided here as tenant-wide, so listing and chat citation agree. Confirm with product before the first external source ingests anything, since it widens what a `business_user` can see.
