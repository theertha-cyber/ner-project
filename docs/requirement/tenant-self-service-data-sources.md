# Tenant Self-Service Data Sources — Feature Requirements

> **Status:** Requirements for review. This is a brownfield feature brief, not an OpenSpec change and not implementation authorization.
>
> **Depends on:** the completed `tenant-pluggable-data-foundation` change. That change provides the initial document-ingestion and original-content-store seams, but it does not supply real external connectors, tenant-selected runtime adapters, tenant-managed databases, or database-chat support.

## 1. Purpose

Evolve the SaaS product from a platform-upload-only experience into a tenant-admin-configured data integration product. A tenant administrator must be able to configure and test a supported document source or structured database source through the portal. The application, not the development team, then uses that configuration at runtime.

The first release deliberately supports a small, explicit provider catalog:

| Capability | Initially supported options |
|---|---|
| Document intake | Platform Upload; Azure Blob Storage |
| Derived document data | Platform PostgreSQL with pgvector |
| Direct structured-data chat | Azure Database for PostgreSQL only |

The design must be extensible: adding a later supported provider must mean implementing a provider adapter behind the appropriate port, registering it in the catalog, and adding its portal configuration form. It must **not** require a second OCR/NER/RAG pipeline or special cases throughout the application.

This is a finite catalog of platform-supported providers. It is not a promise that a tenant can connect an arbitrary database, blob product, or cloud service.

## 2. Product model and terminology

The feature has two separate paths. They may share tenant administration and secret handling, but they are not interchangeable abstractions.

| Path | What the tenant supplies | What the platform does | What the chatbot uses |
|---|---|---|---|
| **Document-source ingestion** | Documents in Platform Upload or Azure Blob Storage | Reads a document, performs OCR/text extraction, NER where applicable, chunking, and embeddings | Derived text spans, entities, chunks, and embeddings held in platform PostgreSQL/pgvector |
| **Direct structured-data chat** | An existing Azure Database for PostgreSQL containing business data and a schema-contract JSON | Does not ingest the database, run NER, create DDL, or copy its rows | A read-only, validated SQL query at question time, using the tenant database as the source of truth |

`Platform Upload` is a document source. It remains available for the existing upload flow. `Azure Blob Storage` is a pull source that the platform synchronizes. An Azure PostgreSQL business database is a chat retrieval capability, not a document source and not a substitute for the platform's derived-data PostgreSQL database.

## 3. Goals

1. A tenant administrator can configure, test, activate, deactivate, and update the supported source connections in the portal without developer intervention.
2. All documents, regardless of source, use one common processing pipeline after their bytes are obtained.
3. Azure Blob documents are processed without durable retention of their original blob in platform MinIO; the original remains in the tenant's Azure Blob Storage.
4. The platform retains the derived data needed by its existing document intelligence product: document metadata/provenance, extracted text spans, NER outputs, chunks, embeddings, and sync state.
5. The chatbot can answer questions from a tenant's existing Azure PostgreSQL data without NER, DDL, generated entity tables, or copying the tenant's source rows to the platform.
6. Schema knowledge for direct structured-data chat is tenant-configured, dynamically retrieved from a schema vector index, and no longer baked into a static system prompt.
7. The same platform remains safe to operate for many tenants: credentials and data are isolated by tenant, and one tenant's connection can never be selected for another tenant.

## 4. Non-goals and hard boundaries

- No arbitrary or automatically supported data-source types.
- No Keka, Amazon S3, SharePoint, AWS database, external vector database, tenant-managed pgvector, or non-PostgreSQL database in this release. The adapter boundaries should make these later additions contained work.
- No migration of derived spans/chunks/embeddings into a tenant-managed PostgreSQL or vector database in this release. Derived document data remains on the platform PostgreSQL/pgvector plane.
- No tenant-provided database writes, DDL, schema migration, view creation, or materialized-view creation.
- No direct database access by the LLM. The LLM proposes a query; application code validates and executes it through a controlled connector.
- No role- or column-specific field visibility rules in this release. All fields in the approved schema contract are available to an authorized chatbot user.
- No raw tenant business rows, connection strings, passwords, access tokens, document content, generated SQL, or model prompts/answers in logs, metrics, traces, or audit payloads.
- No platform-wide “hexagonal rewrite.” This work extends the existing ingestion foundation only where a real runtime-provider boundary is needed.

## 5. Tenant administrator experience

Only a tenant administrator may manage source connections. Other tenant users do not configure, test, or edit connections.

For each supported provider, the portal must offer a provider-specific configuration form. The administrator must be able to:

1. Select a supported provider and create a draft connection.
2. Supply the provider-specific non-secret settings and credentials required by that provider.
3. Run a connection test before activation.
4. See a safe, actionable result: successful, failed authentication, unreachable, insufficient permissions, invalid configuration, or unsupported configuration. The response must not echo a secret, connection string, remote document content, SQL, or provider error containing sensitive values.
5. Activate, deactivate, replace, or delete a connection.
6. See connection status, last test outcome, last sync outcome, last successful sync time, and safe aggregate counts/outcomes.

Credentials must be written to the platform's approved secret-management path. Application configuration and control-plane records store only a secret reference and non-sensitive connection metadata; they never store a plaintext credential.

The product must refuse activation if the configured provider is not in the supported catalog, the connection test fails, or required configuration is incomplete.

## 6. Document-source ingestion requirements

### 6.1 Common pipeline

Platform Upload and Azure Blob must converge at the existing `DocumentIngestionService` boundary. After content is obtained, the normal pipeline is shared:

```text
source obtains document bytes
  -> common ingestion and provenance
  -> OCR / text extraction
  -> text spans
  -> chunking and embeddings for query documents
  -> existing NER / extraction flow where applicable
  -> existing retrieval and chatbot flow
```

Azure-specific concepts must remain inside the Azure Blob adapter and its configuration/UI layer. The OCR, NER, chunking, extraction, and chat layers must not branch on Azure Blob versus Platform Upload.

### 6.2 Azure Blob synchronization

For this feature, a **sync** means:

1. Enumerate the configured Azure Blob scope.
2. Identify new and changed supported documents using source identity and version/change information available from Azure Blob.
3. Fetch or stream each document that needs processing.
4. Send it through the common ingestion pipeline.
5. Persist source identity, source version/change marker, safe provenance, processing result, and per-run sync outcome so the next sync can avoid reprocessing unchanged documents.

It does **not** mean copying every original document into the platform's durable MinIO store. The tenant's Azure Blob remains the durable original-document store. The platform may create a temporary working copy solely while processing a document and must delete it after the processing lifecycle reaches its terminal outcome. The platform retains derived outputs and source/sync metadata.

The tenant administrator must be able to start a manual Azure Blob sync. The platform must also run a scheduled sync for an active Azure Blob connection. Both routes must use the same idempotent synchronization use case.

The system must not create duplicate `documents`, text spans, chunks, embeddings, or derived NER output when a sync is retried or an unchanged object is encountered. A changed document must be reprocessed without leaving duplicate derived outputs.

### 6.3 Platform Upload

Platform Upload remains a supported source and retains its existing upload behaviour. It uses the common ingestion boundary rather than a separate downstream pipeline. Its retention remains configurable through the content-retention policy established by the ingestion foundation.

## 7. Direct structured-data chat requirements

### 7.1 Azure PostgreSQL as an existing business database

A tenant may connect an already-populated Azure Database for PostgreSQL for chatbot questions. This path applies to raw existing tables the tenant already owns. The platform does not need to process those rows through document ingestion or NER first.

The initial release supports direct tables only. It does not support database views, materialized views, stored procedures, write operations, or platform-created database objects.

At question time, the chatbot can select the direct structured-data capability for a tenant whose Azure PostgreSQL connection and schema contract are active. The capability must:

1. Retrieve relevant approved schema context from the tenant's schema vector index.
2. Ask the LLM to propose SQL using that retrieved context and fixed product safety instructions.
3. Validate the proposed SQL against the current approved schema-contract JSON.
4. Execute only validated SQL with the tenant's configured read-only database credential.
5. Return the resulting answer through the chatbot without retaining the database rows as a platform dataset.

The platform must enforce, at minimum: one statement, read-only `SELECT` semantics, approved tables and columns only, an enforced row limit, an execution timeout, and no unvalidated query execution. The validator is authoritative; similarity retrieval alone is never permission to query a table or column.

### 7.2 Tenant schema-contract JSON

The tenant administrator uploads a structured JSON document describing the business database query surface. JSON is the required format; free-form text is not accepted as the canonical contract.

The JSON must represent each queryable table and enough business context for correct SQL generation. At minimum, it must support:

- table name;
- table-level business description and intended question types;
- columns, their data types, and their business descriptions;
- primary keys and join-relevant keys/relationships;
- permitted values, status/indicator semantics, and important query rules;
- instructions such as required columns for follow-up/caching, where applicable.

The example described by the tenant—such as a `fisc_user_profile` table with descriptions for `claim_ind`, `approver_ind`, `pbwuserid`, and explicit query guidance—is the intended level of semantic detail. The contract is not merely technical DDL; it is the approved business meaning of the schema.

The platform must validate this JSON against a published, versioned JSON Schema before accepting it. The portal must show that exact format and an example to the administrator at upload time.

The accepted original JSON is the canonical, versioned source of truth. The platform automatically chunks and embeds its table/column/rule descriptions into a **tenant-isolated schema vector index**. That index is a vector-search representation of the JSON, not a second tenant-maintained schema source.

The LLM receives relevant retrieved schema chunks dynamically instead of a tenant database schema baked into the system prompt. Fixed system-level safety behaviour remains in the system prompt. The original JSON remains necessary for exact allowlist validation, audit/version history, re-embedding, recovery, and safe handling of incomplete vector retrieval.

### 7.3 Schema-contract lifecycle and drift

The portal must show the active schema-contract version associated with a direct database connection. A new contract replaces the active version only after JSON validation and schema-index creation succeed.

If the live Azure PostgreSQL schema no longer matches the active approved JSON contract, direct database chat must be blocked until the tenant administrator uploads an updated contract. The product does not attempt automatic schema learning or silently generate DDL.

## 8. Source selection and chatbot behaviour

The application must resolve which active, supported capability applies for the tenant before it invokes a connector or retrieval tool. Source selection must be configuration-driven, tenant-scoped, auditable, and enforced server-side; a browser request must never select another tenant's connection.

The chatbot planner may use the platform's existing document-derived retrieval/data path or the tenant's active direct Azure PostgreSQL capability, according to tenant configuration and the question. The direct database capability is a retrieval tool alongside existing chat capabilities, not a document-ingestion adapter.

## 9. Data ownership and retention

| Data | Location/retention for this feature |
|---|---|
| Azure Blob original documents | Tenant Azure Blob; platform does not retain a durable MinIO copy |
| Temporary bytes while Azure Blob document is processed | Platform working storage only; deleted after terminal processing outcome |
| Platform-upload originals | Governed by the existing per-tenant retention mode |
| Derived spans, chunks, embeddings, NER outputs, document provenance, and sync state | Platform PostgreSQL/pgvector |
| Tenant Azure PostgreSQL business rows | Tenant database only; queried read-only at question time |
| Uploaded schema-contract JSON | Platform control plane, versioned canonical artifact |
| Schema-contract embeddings | Platform tenant-isolated schema vector index |
| Connection credentials | Approved secret-management system only; application stores a secret reference |

## 10. Brownfield architecture constraints

1. Build on the existing `DocumentIngestionService`, `DocumentContent`, and content-store boundary rather than duplicating upload logic.
2. Implement Azure Blob as a pull-side `DocumentSource` adapter; Platform Upload is an inbound adapter and does not pretend to implement discovery/synchronization.
3. Keep provider SDK/API knowledge in adapters. The application core receives normalized source identity, metadata, and reopenable content access.
4. Keep the existing platform PostgreSQL/pgvector data plane for derived document data in this release. Do not introduce a generic database repository abstraction or generic vector-store abstraction.
5. Implement direct Azure PostgreSQL querying as a new chat retrieval tool/connector. Do not represent it as a document source, content store, or derived-data persistence adapter.
6. Connection resolution must be per tenant and runtime-configured. A process-global default adapter is insufficient for an active self-service tenant connection.
7. Background sync must be durable, observable, retry-safe, and idempotent. It must not be an unbounded task running inside a web request process.

## 11. Acceptance outcomes

The eventual OpenSpec change must specify executable verification for each of these outcomes:

1. An authorized tenant administrator can configure and successfully test an Azure Blob connection; a non-admin cannot.
2. A failed configuration test or missing secret prevents activation and exposes no sensitive value.
3. A manual and a scheduled Azure Blob sync each ingest a new supported document through the same common pipeline.
4. Processing an Azure Blob document produces platform-derived spans/chunks/embeddings while no durable original blob is retained in platform MinIO.
5. Retrying a sync or encountering an unchanged blob creates no duplicate document-derived records.
6. An authorized tenant administrator can upload a valid schema-contract JSON; invalid JSON and JSON that fails the published contract are rejected.
7. A valid schema contract is versioned, indexed into only that tenant's schema vector index, and dynamically retrieved for an applicable database-chat question.
8. A direct Azure PostgreSQL chatbot question executes only validated, read-only, single-statement SQL limited to tables and columns approved by the active JSON contract.
9. A proposed write, multiple statement, unapproved relation/column, or query after detected schema-contract drift is blocked before execution.
10. A tenant can neither inspect nor use another tenant's connection, schema contract, source metadata, derived records, or schema-index entries.

## 12. Decisions already made

- The product is a supported-provider catalog, not a universal datasource connector.
- First document sources: Platform Upload and Azure Blob Storage.
- First direct business-database source: Azure Database for PostgreSQL only.
- Tenant administrators alone configure and test connections.
- Direct business-database chat is read-only and table-only; no views or DDL.
- The tenant supplies an enriched, structured JSON schema contract.
- The contract is embedded into a tenant-isolated schema vector index for LLM context, while the original JSON is preserved automatically as the authoritative versioned contract.
- Existing static tenant-schema context in prompts moves to retrieved schema context for this capability.
- No role-specific schema/column access rules and no usage limits in this release.
- Azure Blob sync supports both manual and scheduled operation.
- Azure Blob originals use a temporary processing copy only, then deletion; derived content remains on the platform.

## 13. Open product decisions to resolve in the OpenSpec design

These behaviours have not been chosen and must not be guessed during implementation:

1. **Deleted-source policy:** when an object is deleted from Azure Blob, should its platform-derived records remain available, be hidden from chatbot retrieval, or be deleted?
2. **Connection concurrency:** may a tenant have both an active Azure Blob document source and an active Azure PostgreSQL direct-chat source at the same time? May it have more than one active connection of a given capability? The phrase “swap sources” needs a precise activation model.
3. **Changed-document history:** when an Azure Blob object changes, should the old derived version be replaced only, retained as version history, or retained for a defined period?
4. **Schema-drift detection mechanism:** the required response is decided—block database chat until a new contract is uploaded—but the mechanism for detecting a mismatch needs design and verification criteria.
5. **Scheduled-sync cadence and catch-up behaviour:** scheduling is required, but the tenant-configurable versus platform-default cadence and behaviour after missed runs are not yet specified.

## 14. Suggested implementation split

This is too large for a revision of `tenant-pluggable-data-foundation`; it requires a follow-on OpenSpec proposal, likely decomposed into independently reviewable slices:

1. tenant integration control plane, admin portal, catalog, secret references, and connection testing;
2. Azure Blob `DocumentSource`, durable manual/scheduled sync engine, provenance, and temporary-content lifecycle;
3. direct Azure PostgreSQL chat connector, schema-contract JSON validation/versioning/indexing, dynamic context retrieval, and SQL safety validation;
4. integration of source selection into the chatbot planner and tenant configuration.

Each slice must preserve the stated data-retention boundaries and have executable acceptance verification before implementation begins.
