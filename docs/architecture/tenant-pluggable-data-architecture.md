# Tenant-Pluggable Data Architecture — Assessment Report

> **Status:** Architecture assessment for review. No code, no migrations, no OpenSpec artifacts created.
> **Question answered:** How does this stay *one product* with *one* document-processing and chatbot core, while each tenant can use an approved combination of their own document source, blob storage, relational database, vector store, and existing business database?
> **Evidence convention:** `Confirmed` = verified in this repository. `Inferred` = reasoned from confirmed facts. `Open` = needs product, security, or customer agreement.
> **Related documents:** `external-data-source-architecture.md` (full external-sync engine design) and `document-ingestion-source-boundary.md` (the ingestion seam). This report is the wider frame both sit inside. Section 17 reconciles all three.

---

> ### Naming and decision reconciliation (added 2026-09-07)
>
> Terminology across the three architecture documents and the OpenSpec change
> `tenant-pluggable-data-foundation` is now settled. Where this document uses a
> superseded term, read it as the chosen one:
>
> | Concept | Chosen term | Superseded term |
> |---|---|---|
> | Pull-side source port | `DocumentSource` | `SourceConnector` |
> | Configured-source table | `document_sources` | `data_sources` |
> | Configured source identifier | `source_id` (reserved value `platform-upload` for platform upload) | `source_instance_id` |
> | Stored-bytes locator in the application contract | `storage_reference` | `blob_path` (remains the physical column name until the `document-metadata-column-reconciliation` change) |
>
> Two design points are also revised by that change and take precedence over any
> contrary statement here: content access is **re-openable or explicitly single-use**
> rather than a one-shot byte buffer, and ingestion writes bytes through the
> **content-store boundary** rather than to MinIO directly. Retention is explicit,
> with three modes — `platform_blob`, `ephemeral`, `source_only` — and is never
> inferred from a NULL storage reference.

## 0. Read this first

Five boundaries were assessed. **They are not equally worth building, and treating them as five instances of the same pattern is the main risk in this programme.**

| Boundary | Verdict | Effort | Why |
|---|---|---|---|
| **Document acquisition** | **Build a port** | Small | Coupling is ~130 lines in two files. Everything downstream is already source-blind. |
| **Original blob storage** | **Build a port** | Small | Two call sites. Also the only way "don't copy our documents into your MinIO" becomes a setting rather than a fork. |
| **Vector / index store** | **Reshape an existing port** | Medium | A `Retriever` protocol already exists — but its methods take a SQLAlchemy session and a schema name, so it is a Postgres interface wearing an abstraction's clothes. |
| **Derived relational store** | **Do NOT abstract. Relocate instead.** | Medium, but different in kind | The derived layer *generates PostgreSQL DDL at runtime*, uses `ON CONFLICT … EXCLUDED`, materialized views, `pg_tables`, `DO $$` loops, `SET LOCAL ROLE`, and generated `tsvector` columns. An abstraction over "any relational store" would have to reimplement all of it per vendor. |
| **Tenant business-database querying** | **Build it — but as a new capability, not an adapter** | Medium | It stores nothing, has no document, no checksum, no purpose. It belongs next to the existing retrieval tools, and there is already a registry for those. |

**The single most important finding.** The request lists "another explicitly supported relational store" and "another vector database" as if they were configuration. The repository says otherwise for the relational case: the platform does not *use* PostgreSQL, it **writes PostgreSQL**, at runtime, in response to tenant-defined entity types. So the honest first supported set is:

> **PostgreSQL 16+ with the `vector` extension** — ours, or the tenant's own (self-managed, RDS, or Aurora PostgreSQL).

That is not a limitation to apologise for. It changes the relational problem from *"abstract the database"* (a large, risky, low-value refactor) into *"point the same schema at a different server"* (a bounded connection-routing problem). Different database engines — MySQL, SQL Server, Snowflake — are not adapters. They are a rewrite of the projection layer, and should be declined until a customer pays for one.

**Is this bounded?** Boundaries 1, 2, and the control-plane work are bounded and worth doing now. Boundary 4 (relocating a tenant's derived data) is bounded but operationally heavy. Boundaries 3 and 5 are genuinely new subsystems, not refactors. Sequence matters more than scope — see §14.

---

## 1. Current architecture — the data flows

### 1.1 Document intake and processing

Everything enters through one door: `POST /api/v1/documents` ([documents.py:58](../../src/document_service/api/v1/documents.py)). The portal posts directly to `document_service`; it is **not** proxied through the gateway (`gateway/main.py` registers no document router). `Confirmed`

That single handler validates the file type and size, generates the document id, invents the MinIO object key, hashes the bytes, looks for a byte-identical earlier upload, writes to MinIO, inserts the `documents` row, commits, and fires OCR.

OCR then runs as `asyncio.create_task` inside the web process (`ocr_worker.py:271`) — in-process, non-durable, unbounded. `Confirmed`

The worker re-reads the bytes from MinIO, decides whether to run PyMuPDF text extraction or Tesseract OCR **by splitting the MinIO object key on a dot** (`ocr_worker.py:197`), writes text spans, marks the document processed, and — only for `purpose='query'` documents — chunks the text, embeds it, and inserts rows carrying a pgvector value.

### 1.2 Entity extraction

A Celery worker (`extraction_service/worker.py`) selects documents where `status='processed' AND purpose='query'`, reads their text spans, tokenizes, calls `model_serving` for BIO tags, post-processes, and writes results into three places: the EAV table `extracted_entities`, the typed table `document_entities`, and **a set of relational tables generated at runtime from the tenant's own entity definitions**.

That last part is the important one. `entity_views.py` (1 080 lines) builds `CREATE TABLE IF NOT EXISTS` and `ALTER TABLE … ADD COLUMN IF NOT EXISTS` statements per tenant, per entity type, and reconciles them before every batch run. `relational_projection.py` builds the corresponding upserts. `Confirmed`

### 1.3 Retrieval and chat

`chat_api` runs a LangGraph pipeline. A planner picks between two capabilities — `semantic_retrieval` and `structured_retrieval` — registered in a `ToolRegistry` (`shared/retrieval/tools/registry.py`) and invoked with a `ToolContext` built from authenticated request state. `Confirmed`

Semantic retrieval fuses a dense pgvector query and a sparse PostgreSQL full-text query using Reciprocal Rank Fusion **in Python** (`retriever.py`, `HybridRetriever`), then optionally reranks via a cross-encoder in `model_serving`.

Structured retrieval generates SQL against an allowlist of tables and the tenant's generated entity tables, validates it, and executes it under a `NOLOGIN` least-privilege role assumed per statement inside a read-only transaction (`sql_execution_role.py`). `Confirmed`

### 1.4 Everything else touching the same data

Annotation (tasks, spans, export to training datasets), training (MLflow, model artifacts in MinIO), analytics (four materialized views per tenant schema), and the dashboard all read the same tenant tables.

---

## 2. Coupling map

### 2.1 Coupled to platform upload

| Where | What |
|---|---|
| `documents.py:58-139` | The ingestion use case *is* the HTTP handler. `UploadFile` and `Request` are in scope for hashing, storage, and persistence. |
| `documents.py:98` | The storage key is computed by the route and then passed onward as a pipeline input. |
| `documents.py:139`, `ocr_worker.py:271` | Fire-and-forget dispatch inside the API process. |
| `documents.py:169` | Non-admins only see documents where `uploaded_by` matches them. A fetched document has no uploader. |
| `documents` table | No source, no external identity, no source timestamps. |

### 2.2 Coupled to MinIO

| Where | What |
|---|---|
| `documents.py:117` | `MinioStorageClient()` constructed inline. No injection point. |
| `ocr_worker.py:185` | The worker constructs its own client and re-reads the bytes. MinIO is the pipeline's only content source. |
| `ocr_worker.py:197` | **The OCR branch is selected by parsing the object key.** This one line blocks the entire "no platform retention" requirement. |
| `storage.py:33` | The key is built inside `upload_file` from `tenant_id`. |
| `document_service/main.py:84` | Readiness asserts MinIO. |

Out of scope and must stay so: `model_serving/services/model_loader.py:11` and `training_service/worker.py:178` also use MinIO — for **model artifacts**, not tenant documents. Different plane, different lifecycle.

### 2.3 Coupled to PostgreSQL — the deep coupling

This is where the report diverges most from the brief's framing.

| Where | What | Portable to another engine? |
|---|---|---|
| `shared/database.py` | One process-global engine built from one connection string. 44 call sites reach it. | The *routing* is fixable. |
| `_schema(tenant_id)` | The `tenant_{id}` helper is **redefined in at least ten modules** (document, annotation ×5, chat ×2, extraction ×2, ocr worker…). | Schema-per-tenant is a PostgreSQL idiom. |
| `entity_views.py` | Generates DDL at runtime: `CREATE TABLE IF NOT EXISTS`, `ALTER TABLE … ADD COLUMN IF NOT EXISTS` (explicitly relying on it being metadata-only in PG 11+), typed columns, index naming. | **No.** |
| `relational_projection.py` | `INSERT … ON CONFLICT (…) DO UPDATE SET … EXCLUDED.…`, `GREATEST()`, `COALESCE()`. | **No.** |
| `alembic/011`, `015` | Four materialized views per tenant schema, created through `DO $$` loops with `format()` and `%I`. | **No.** |
| `alembic/024` | `chunk_tsv tsvector GENERATED ALWAYS AS (to_tsvector('english', chunk_text)) STORED`, GIN index, HNSW index. | **No.** |
| `tenant_service.py:52-59` | Provisioning clones `tenant_template` via `pg_tables` + `CREATE TABLE (LIKE …)`. Foreign keys are **not** copied. | **No.** |
| `sql_execution_role.py` | `CREATE ROLE … NOLOGIN`, `SET LOCAL ROLE`, `BEGIN READ ONLY`, grants derived from `pg_tables`. | **No.** |
| Schema drift | `002` created `mime_type`/`file_size_bytes`/`storage_uri`; `003` added `content_type`/`file_size`/`blob_path`. Uploads write the `003` set; `sql_generator.py:24` advertises the `002` names to the LLM and `dashboard.py:694` reads `file_size_bytes` — always NULL. | Pre-existing defect. |

**Read that table as a whole.** Eight of the nine rows are PostgreSQL-specific by design and for good reasons. A repository abstraction over them would need a DDL generator, an upsert generator, a view generator, and a privilege model per vendor. That is not an adapter; that is a second product.

### 2.4 Coupled to pgvector and PostgreSQL full-text

| Where | What |
|---|---|
| `ocr_worker.py:24-48` | Chunk insert with `CAST(:embedding AS vector)`. |
| `retriever.py:69` | `1 - (embedding <=> :q)` and `ORDER BY embedding <=> :q`. |
| `retriever.py:110` | `chunk_tsv @@ plainto_tsquery('english', :q)` — the sparse half. |
| `alembic/010`, `024` | `vector(1536)` column, HNSW index, generated tsvector column, GIN index. |
| `documents.py:298`, `ocr_worker.py` | Chunk deletion on document delete and (missing today) on reprocess. |

**Note what shares one table.** `document_chunks` holds the chunk text, the dense vector, the sparse index, page/offset metadata, and `purpose`, with a foreign key to `documents`. Dense and sparse retrieval hit the same row; fusion happens afterwards in Python. Moving vectors to an external store therefore does **not** move "the embeddings" — it splits one table three ways. §11 deals with the consequences.

### 2.5 Coupled to current tenant schemas

`WHITELISTED_TABLES` in `sql_generator.py` names `documents`, `document_chunks`, `document_text_spans`, `document_entities`, `extraction_runs` and their columns; the grant list in `sql_execution_role.py` is derived from the same set plus resolved generated tables; the analytics views join `documents` to `extracted_entities`; the dashboard joins `annotation_tasks` to `documents`.

---

## 3. What is already infrastructure-agnostic

| Component | Evidence | Status |
|---|---|---|
| Text extraction | `ocr_worker.py:66, 104, 126` — pure `bytes → spans` | **Agnostic** |
| Chunking | `shared/retrieval/chunking.py` — pure `text → chunks` | **Agnostic** |
| Embedding | `chat_api/services/embedding_service.py` — pure `texts → vectors` | **Agnostic** |
| Reranking | `shared/retrieval/reranker.py` + `model_serving` — operates on text | **Agnostic** |
| Rank fusion | `HybridRetriever` — RRF computed in Python, not SQL | **Agnostic** |
| Retrieval planning | `orchestrator.py`, `ToolRegistry`, `ToolContext` | **Agnostic in structure**, Postgres-typed in signature |
| Retriever abstraction | `retriever.py:18` — already a `Protocol` | **Half-agnostic** — takes `AsyncSession` and `schema` |
| Extraction eligibility | Selects on `status` and `purpose` only | **Agnostic** |
| Entity post-processing | `entity_postprocessor.py` — operates on values | **Agnostic** |
| Tenant identity | JWT-derived, never from a request body | **Agnostic** |
| Content hashing | `content_hash.py` — one algorithm, any origin | **Agnostic** |
| Statement building | `relational_projection.py` builds statements and **executes nothing** | **Well-factored, still Postgres dialect** |

Two things stand out. First, the *compute* is already portable — OCR, chunking, embedding, reranking, fusion, and post-processing neither know nor care where anything is stored. Second, **two ports already exist in embryo**: `Retriever` and `RetrievalTool`. The work is less "introduce ports" than "finish two that were started and add two that are missing".

---

## 4. Recommended target architecture

```
                       ┌──────────────────────── CONTROL PLANE (always platform) ────────────────────────┐
                       │  public.tenants · tenant_users · entity_definitions · audit_events              │
                       │  widget_api_keys · integration profiles · secret REFERENCES (never secrets)     │
                       └───────────────────────────────────┬───────────────────────────────────────────┘
                                                           │ resolves, per tenant
                                                           ▼
   ┌─ SOURCES ─────────────┐        ╔═══════════════════════════════════════════╗
   │ platform upload       │        ║        APPLICATION CORE (one copy)        ║
   │ Keka                  │───────▶║                                           ║
   │ tenant S3             │  P1    ║  ingestion · OCR · chunking · embedding   ║
   │ Azure Blob            │        ║  NER · post-processing · rank fusion      ║
   │ SharePoint (future)   │        ║  retrieval planning · answer synthesis    ║
   └───────────────────────┘        ║                                           ║
                                    ║  knows nothing about MinIO keys, Postgres ║
                                    ║  schema names, pgvector syntax, provider  ║
                                    ║  APIs, or credentials                     ║
                                    ╚══╤═════════════╤═════════════╤═════════╤══╝
                                       │ P2          │ P3          │ P4      │ P5
                                       ▼             ▼             ▼         ▼
                        ┌──────────────────┐ ┌──────────────┐ ┌─────────┐ ┌──────────────────┐
                        │ ORIGINAL BLOB    │ │ DERIVED      │ │ INDEX / │ │ TENANT BUSINESS  │
                        │ STORE            │ │ RELATIONAL   │ │ VECTOR  │ │ DB QUERY         │
                        ├──────────────────┤ ├──────────────┤ ├─────────┤ ├──────────────────┤
                        │ platform MinIO ◀ │ │ platform PG◀ │ │pgvector◀│ │ (none by default)│
                        │ tenant S3        │ │ tenant PG    │ │ tenant  │ │ tenant RDS       │
                        │ tenant Azure     │ │ (RDS/Aurora  │ │ pgvector│ │ tenant Aurora    │
                        │ no retention     │ │  PostgreSQL) │ │ external│ │ (read-only)      │
                        └──────────────────┘ └──────────────┘ └─────────┘ └──────────────────┘
                              ◀ = default adapter, unchanged for existing tenants

   P1 DocumentIngestion (inbound) + DocumentSource (pull, deferred)
   P2 OriginalDocumentStore          P3 tenant data-plane connection routing (NOT a repository abstraction)
   P4 DocumentIndex                  P5 StructuredDataConnector (a retrieval tool, not a data source)
```

Two rules make this one product rather than five:

1. **The core is single-instance and stateless about infrastructure.** Same OCR, same chunker, same NER, same planner, same prompts, for every tenant.
2. **The control plane is never tenant-selectable.** Who the tenants are, what entity types they defined, what the audit trail says, and which adapters they use — that stays with the platform, always. Otherwise the platform cannot enumerate its own customers.

---

## 5. The boundaries that should exist

| # | Boundary | Recommendation | Rationale |
|---|---|---|---|
| **P1** | Document acquisition | **Yes — build now** | Small, high value, unblocks every future source, and makes upload a first-class adapter instead of a special case. |
| **P2** | Original blob storage | **Yes — build now** | Two call sites. Without it, "no platform retention" is a fork of the pipeline rather than a setting. |
| **P3** | Derived relational persistence | **No port. Connection routing + a strict dialect contract.** | The derived layer emits PostgreSQL. Abstracting it means reimplementing DDL, upserts, views, and privileges per vendor. Relocating it means changing one connection. |
| **P4** | Index / vector persistence and retrieval | **Yes — reshape the existing `Retriever` protocol into a real port** | It is already a `Protocol`; it just leaks `AsyncSession` and `schema`. Two-thirds of the work is signature design, not new code. |
| **P5** | Direct structured-data querying | **Yes — as a new retrieval capability, not an adapter over anything** | It produces no documents and stores nothing. `ToolRegistry` is its natural home. |

Boundaries the brief did not ask for and that should **not** be created: any port over SQLAlchemy, any repository per table, any abstraction over the embedding model, the reranker, Celery, MLflow, or model serving. They are not tenant-selectable, so a port over them buys indirection and nothing else.

---

## 6. Boundary specifications

### P1 — Document acquisition

| | |
|---|---|
| **Contract** | *Ingest this document.* Platform id, trusted tenant id, source type, configured source instance, opaque external id (nullable), filename, media type, size, checksum (platform-computed), source version and timestamps (all nullable), purpose, actor, retention policy, and **re-openable access to the bytes**. |
| **Default adapter** | The existing upload route, thinned to HTTP concerns: multipart handling, JWT/tenant resolution, the role-to-purpose rule, status codes. |
| **Example tenant adapter** | Keka: OAuth, employee/document/attachment enumeration, `{employeeId}:{documentId}:{attachmentId}` as the opaque external id, extension-derived media type, per-endpoint rate limits. All of it inside the adapter. |
| **Consumers that must change** | The upload route (thinned); `process_document` (takes a document id, resolves content through the port, and branches on **media type**, not on the object key). |
| **Must not leak in** | Provider credentials or tokens; pre-signed URLs; bucket, container, or subdomain names; MinIO paths as required fields; PostgreSQL schema names; pgvector details. |

**Push versus pull.** Upload is a *push* source — the bytes arrive unannounced. Keka, S3, Azure, and SharePoint are *pull* sources — the platform enumerates, decides what is new, then fetches. One interface that both satisfy forces upload to implement "list everything you have", which it cannot do honestly. So: **one inbound contract every adapter calls**, and a **separate pull-side contract** (`check_connection` / `discover` / `fetch`) that only fetchers implement. Upload still becomes an adapter; it just does not pretend to be enumerable. `Inferred`

### P2 — Original document storage

| | |
|---|---|
| **Contract** | *Store these bytes for this tenant's document, and give me back a reference — or tell me you stored nothing.* Plus: *open the bytes at this reference.* |
| **Default adapter** | The existing `MinioStorageClient`, wrapped and otherwise unchanged. |
| **Example tenant adapters** | Tenant S3 bucket; tenant Azure container; **no-retention**, which stores nothing and returns no reference. |
| **Consumers that must change** | The upload route (stops inventing the key); `process_document` (stops re-reading MinIO directly and stops parsing the key). |
| **Must not leak in** | Bucket or container names, endpoints, credentials, region, or the key-construction rule. The reference the store returns is opaque to everything else. |

Three decisions this boundary forces, and all three must be made **now**, while there is only one implementation:

1. **The storage reference is an output, not an input.** Today the route invents the path before storage runs. Reverse it, or no adapter can ever decline to store.
2. **A NULL reference is a valid outcome**, meaning "not retained by the platform" — not a broken row.
3. **Nothing downstream may parse the reference.** `ocr_worker.py:197` does exactly this today and is the single line blocking the privacy requirement.

### P3 — Derived relational persistence

**This is deliberately not a port.** The contract is a *schema and dialect contract*, and the mechanism is connection routing.

| | |
|---|---|
| **Contract** | *A PostgreSQL 16+ database, with the `vector` extension available, in which the platform owns a `tenant_{id}` schema and may create, alter, and query tables within it — including tables generated at runtime from that tenant's entity definitions.* |
| **Default adapter** | The platform PostgreSQL cluster. Unchanged. |
| **Example tenant adapter** | The tenant's own PostgreSQL — self-managed, RDS PostgreSQL, or Aurora PostgreSQL — reachable over a private network path, with a platform-owned role holding DDL rights inside that schema only. |
| **Consumers that must change** | Every module that calls `get_engine()` — but only in *how they obtain* the engine, not in what they do with it. And the ten copies of `_schema()` should collapse to one. |
| **Must not leak in** | The connection string, credentials, host, or cluster identity — anywhere except the control-plane profile and the secret store. |

**Why this framing rather than a repository abstraction.** Look at what the derived layer actually does: it decides at run time that a tenant needs a `skills` table, emits `CREATE TABLE IF NOT EXISTS` for it, adds a typed column to `subject` with `ADD COLUMN IF NOT EXISTS` (relying explicitly on that being metadata-only in PostgreSQL), writes rows with `ON CONFLICT … DO UPDATE SET … GREATEST(confidence, EXCLUDED.confidence)`, and then grants a `NOLOGIN` role `SELECT` on it so generated SQL can read it. Four analytics materialized views sit on top. `Confirmed`

A vendor-neutral abstraction would need to reproduce all of that per engine. The value delivered would be zero until a customer demands a non-PostgreSQL store — and at that point the honest answer is a scoped project, not a configuration flag.

**What this buys instead:** the same schema, the same SQL, the same migrations, running in the customer's database. That satisfies "tenant-managed relational store" for every realistic customer, because RDS and Aurora PostgreSQL are what enterprises actually run.

### P4 — Index / vector persistence and retrieval

| | |
|---|---|
| **Contract** | Two operations. *Index these chunks for this document* (text, embedding, page and offset metadata, purpose). *Retrieve the top-k chunks for this query* (dense, sparse, or hybrid), plus *delete this document's chunks*. Results are the existing `RetrievalResult` shape — document id, chunk index, text, score, page, offsets — which is already storage-neutral. |
| **Default adapter** | pgvector in the tenant schema, with the existing HNSW index, the generated `tsvector` column, and RRF fusion in Python. |
| **Example tenant adapter** | The tenant's own PostgreSQL with pgvector (trivial — it is the default adapter pointed elsewhere, and it follows automatically from P3). A genuinely external vector database is a larger step; see §11. |
| **Consumers that must change** | `ocr_worker` (indexes through the port instead of inserting rows); `DenseRetriever`/`SparseRetriever`/`HybridRetriever` (become the platform adapter behind the port); the document delete path; the retrieval tools' context. |
| **Must not leak in** | `AsyncSession`, `schema`, table names, `<=>`, `tsvector`, index types. **The current `Retriever` protocol leaks the first two and must be reshaped.** |

### P5 — Tenant business-database querying

| | |
|---|---|
| **Contract** | *Given a question and an approved semantic layer, produce evidence rows.* The connector receives a validated, bounded, read-only query and returns rows plus provenance. It is registered as a retrieval capability for the tenants that have one. |
| **Default adapter** | None. Most tenants have no such integration, and the planner simply never sees the capability. |
| **Example tenant adapter** | Tenant RDS/Aurora PostgreSQL, read-only, over a private network path, with a least-privilege credential resolved from a secret reference. |
| **Consumers that must change** | The retrieval planner's capability list (already registry-driven); answer synthesis and citation rendering (rows are not chunks and not entities). |
| **Must not leak in** | Credentials, host names, the tenant's full catalog, and — critically — **any schema the tenant has not explicitly approved**. |

---

## 7. Choosing adapters per tenant — the integration profile

One record per tenant, in **control-plane storage**, naming the adapters and pointing at secrets. Never holding a secret.

| Field | Example | Notes |
|---|---|---|
| Document sources | `[platform_upload, keka_prod]` | A tenant may have several. Each is a configured instance with its own non-secret settings. |
| Original blob store | `platform_minio` \| `tenant_s3` \| `none` | `none` is the privacy posture, not an error state. |
| Derived relational store | `platform_pg` \| `tenant_pg:<profile>` | Dialect contract fixed at PostgreSQL 16+. |
| Index store | `platform_pgvector` \| `tenant_pgvector:<profile>` \| `external:<kind>` | Usually follows the relational choice. |
| Structured-data connectors | `[]` or `[tenant_aurora_hr]` | Path D. Empty for almost everyone. |
| Secret references | `vault://tenants/acme/keka`, … | **Locators only.** |
| Network profile | private link / VPN / IP allowlist identifier | Needed the moment anything is tenant-hosted. |
| Status | `draft → validated → active → paused → retired` | A profile must pass connection and smoke checks before it goes active. |

**Rules.**

1. Profiles are **developer-managed**. No customer-facing self-service. This is a deliberate product constraint and it is what makes the supported matrix finite.
2. **Secret references only.** `AGENTS.md` invariant 3 forbids secrets in source, config, or committed `.env`, and forbids defaults for secret-class settings. A tenant credential in an ordinary database row would violate its spirit and would expose secrets to every admin endpoint that returns a profile. `Confirmed` (invariant) / `Inferred` (application).
3. **One honest deviation to record.** The invariant's fail-fast-at-startup rule cannot fully apply: profiles are per-tenant rows created at runtime, so the process cannot enumerate required secrets at boot. Failure surfaces at resolution time and moves the profile to an error state with an operator-visible message. Better acknowledged than silently excepted.
4. **Resolution happens once, at the edge**, and flows down as an immutable, tenant-bound context. Adapters receive resolved values and never learn where they came from — so an adapter has no API with which to ask for another tenant's credentials.
5. **The supported matrix is a list, not a promise.** Publish which combinations are validated. Anything else is "not supported yet", with a stated cost to add.

---

## 8. Control plane versus tenant data plane

| Data | Plane | Why |
|---|---|---|
| `public.tenants`, `tenant_users` | **Control** | The platform must enumerate its own customers and authenticate users even when a tenant's store is unreachable. |
| `public.entity_definitions` | **Control** | It is *configuration*, not extracted content. It also drives DDL generation and the SQL allowlist, so it must be readable when provisioning the tenant store. |
| `public.audit_events` | **Control** | Audit must survive a tenant integration being paused, misconfigured, or retired. |
| `public.widget_api_keys` | **Control** | Authentication material. |
| Integration profiles | **Control** | New. |
| `documents` metadata | **Tenant-selectable, with a control-plane shadow** | See below. |
| `document_text_spans` | **Tenant-selectable** | OCR text is tenant content. |
| `document_chunks` | **Tenant-selectable** | Text plus embeddings — derived tenant content. |
| `extracted_entities`, `document_entities`, generated tables, `subject` | **Tenant-selectable** | The most sensitive derived data in the system. |
| Analytics materialized views | **Tenant-selectable** | They are views over tenant content. |
| `conversations`, `chat_messages`, feedback | **Tenant-selectable** — and easy to forget | Question text and answers are tenant content with the same residency exposure as documents. |
| Annotation tasks, labels, imported annotations | **Tenant-selectable** | Human-labelled tenant content. |
| `training_jobs`, `model_versions` | **Control-leaning** | Operational records the platform must see to run training. Note `model_versions` currently lives in tenant schemas. |
| Model artifacts (MinIO), MLflow | **Control** | Platform-owned model plane. Out of scope entirely. |

**The one genuinely hard call: `documents`.** If the whole row moves to the tenant's database, the platform can no longer answer "how many documents does this tenant have?" or bill, or run fleet-wide operations, without reaching into customer infrastructure. If it stays, the filename — often personal data — stays with the platform.

**Recommendation:** keep a minimal, content-free **document registry** in the control plane — document id, tenant id, source type and instance, status, size, checksum, timestamps, retention mode. Everything with content in it — filename, OCR text, chunks, entities, projections — follows the tenant's chosen store. Checksum and size are metadata about content, not content. `Open` — filename is the boundary case and needs a privacy ruling.

---

## 9. Hosting the platform's own schema in a tenant-managed database

This is the realistic version of "tenant-managed relational store", and it is **not** an abstraction problem.

**What stays identical:** the schema, every migration, every query, the projection statements, the generated DDL, the analytics views, the least-privilege query role. One codebase, one dialect, one set of migrations.

**What changes:** which server the connection points at.

| Concern | What it means in practice |
|---|---|
| **Connection routing** | Today `get_engine()` returns one process-global engine (`shared/database.py`). It becomes a per-tenant resolver with a small pool cache. Every one of the 44 call sites keeps working; they change *how they get* the engine, not what they do with it. |
| **Migrations** | Alembic must run per tenant database, not once. Version state is per database. A tenant on an older revision is a supportable state, so the code must tolerate a version window — that is a real, ongoing operational cost. |
| **Provisioning** | `tenant_service.py` clones `tenant_template` using `pg_tables` and `CREATE TABLE (LIKE …)`. In a tenant database there is no template to clone from, so the template must be materialised there first. Note that the clone **does not copy foreign keys**, so integrity is already application-enforced — which, conveniently, means nothing depends on cascade behaviour that a fresh database might lack. `Confirmed` |
| **Privileges** | The platform needs DDL rights within its schema (entity tables are created at run time) and the ability to create the `NOLOGIN` query role. Some enterprise DBAs will refuse the second. Fallback: pre-created role, platform grants only. `Open` |
| **Extensions** | `vector` must be installed. On RDS/Aurora that is a parameter-group and `CREATE EXTENSION` matter, and it needs to be a documented prerequisite, not a runtime surprise. |
| **Network** | Workers must reach the customer's database privately — PrivateLink, VPC peering, or VPN. Latency now sits inside the OCR worker's per-span inserts and inside chat p95. Both currently assume a local database. |
| **Failure isolation** | A tenant database being down must degrade that tenant only. Today one global engine and one readiness probe make "the database" a single fate. |
| **Backups, retention, deletion** | Become the customer's responsibility, and "delete this tenant" stops being something the platform can fully execute alone. |
| **Cross-plane reads** | The projection reconciler reads `public.entity_definitions` (control plane) and writes to the tenant store. That cross-plane read must be explicit and resilient, not incidental. |

**The honest summary:** technically this is the *smallest* of the tenant-hosting options and the one with the least code change. Operationally it is the *largest*, because it multiplies migrations, monitoring, network paths, and support surface by the number of such tenants. Price it accordingly.

---

## 10. Why querying a tenant's business database is a different thing entirely

| | Platform schema in a tenant database (§9) | Tenant's existing business database (Path D) |
|---|---|---|
| Who owns the schema | Platform | Customer |
| Who migrates it | Platform | Nobody — it changes underneath us |
| What is stored | Documents, spans, chunks, entities | Nothing of ours |
| When it is touched | Ingestion and query time | Query time only |
| Write access | Yes, within our schema | **Never** |
| Failure mode | That tenant's pipeline stalls | One chat answer degrades |
| Correct home | Connection routing | A retrieval capability |

Forcing Path D behind a document-source or storage abstraction would require inventing a document id, a checksum, a purpose, a status, and a storage reference for something that has none of them.

### 10.1 The semantic-layer approach

The LLM must never receive unrestricted database access. The platform already has the right shape for this, in `sql_generator` and `sql_execution_role` — the difference is that in a customer's database, **we do not control the grants**, so the reviewed contract has to do more of the work.

**A tenant contributes** (developer-reviewed, version-controlled, checked into the profile, never scraped automatically):

- the exact tables and views that may be queried, and the exact columns within them;
- relationships and join paths;
- business definitions in plain language ("active headcount excludes contractors");
- worked example questions with their correct queries;
- row limits, freshness expectations, and any columns that must never be selected.

**At query time:**

1. The planner sees a capability described in business terms, not table names.
2. Only the *relevant slice* of the approved contract enters the prompt — not the customer's whole catalog.
3. The model proposes a query.
4. **The platform validates it**: single statement, read-only, every referenced relation and column on the approved list, no DDL/DML, no functions outside an allowlist, length bounded, a mandatory row limit. This is the discipline `validate_sql` already implements against the platform's own schema.
5. Execution runs through the tenant connector under a **least-privilege, read-only credential** with its own statement timeout and row cap. Two independent controls: a validator gap degrades into a permission error, not a disclosure. That is exactly the reasoning already written into `sql_execution_role.py`. `Confirmed`
6. Results are bounded, provenance-tagged, and never written back into platform storage.
7. Per `AGENTS.md` invariant 4, neither the generated SQL nor the returned values may be logged or placed on spans.

**Open questions:** what happens when the customer's schema drifts from the contract (recommendation: fail the capability loudly rather than guess); whether results may be cached at all (recommendation: no, initially); and who signs off on the approved surface on the customer's side.

---

## 11. Vector retrieval with a different vector store

This is the boundary where the brief's assumption most needs testing.

**What "moving the vector store" actually moves.** `document_chunks` holds five things at once: chunk text, the dense vector, the generated sparse index, page/offset metadata, and `purpose` — with a foreign key to `documents`. Dense and sparse retrieval read the same rows; fusion happens afterwards in Python.

So there are three real options, not one:

| Option | What it means | Assessment |
|---|---|---|
| **A. Tenant's own PostgreSQL with pgvector** | The default adapter, pointed at a different server. Hybrid retrieval, fusion, filtering, and cascade deletes all keep working unchanged. | **Recommended first step.** Falls out of §9 almost for free. Covers the realistic privacy case. |
| **B. External vector database, dense only** | Vectors move out; chunk text and sparse index stay in PostgreSQL. | **Do not do this.** One document's chunks now live in two stores that can disagree, deletion becomes a two-phase problem, and hybrid retrieval crosses a network boundary mid-query. |
| **C. External vector database, full ownership** | The external store holds chunk text, vector, and metadata, and provides its own sparse or hybrid capability. | Viable, and the only clean external option. But it needs: metadata filtering equivalent to the `document_id`/`purpose` filters; a delete-by-document operation; a hybrid mode or an accepted quality regression; and its own consistency story with the relational side. A genuine project. |

**What the port must therefore express**, independent of store: index a document's chunks; retrieve top-k for a query with an optional document-id filter and a purpose filter; delete a document's chunks; and **declare its own capabilities** — does it do dense, sparse, hybrid; does it filter by metadata; is it strongly consistent after write. The core reads those capabilities and adapts, exactly as the ingestion design reads source capabilities rather than branching on a provider name.

**What must not leak in:** `AsyncSession`, schema names, `<=>`, `tsvector`, HNSW parameters. The current `Retriever` protocol leaks the first two today.

**Consistency, said plainly.** PostgreSQL indexing is transactional with the chunk write. Most external vector stores are eventually consistent. A document can therefore be "processed" and not yet retrievable. That is a user-visible behaviour change and needs a product decision, not a silent one. `Open`

---

## 12. Cross-cutting implications

**Privacy and retention.** Originals, OCR text, chunks, embeddings, and extracted entities are all tenant content. So are conversations and chat messages, which is easy to overlook. Retention posture for originals (`retain` / `don't retain`) is a *different* setting from residency of derived data — a likely first policy is "originals stay ours, derived data stays theirs", and conflating the two fields makes it unrepresentable. Embeddings deserve explicit treatment: they are lossy, but they are derived from the text and should be treated as tenant content, not as anonymous numbers. `Open` — needs a documented position before the first privacy-sensitive customer asks.

**Tenancy.** Isolation today is by schema, enforced by construction: a cross-tenant read requires naming another schema. Tenant-hosted stores *strengthen* that (separate databases entirely) but weaken the platform's ability to reason about the fleet. The tenant id must continue to enter once, from the JWT, and never be re-derived — including inside adapters.

**Credentials.** References only, resolved once at the edge, passed down as resolved values inside an immutable tenant-bound context, never logged, never persisted, never returned by an admin endpoint. Rotation must not require a deploy.

**Network.** Every tenant-hosted option adds an egress path from platform workers to customer infrastructure: private connectivity, egress allowlists, certificate handling, and a documented latency budget. Note that ingestion, extraction, and chat have very different tolerances — a slow tenant database is survivable during a nightly sync and unacceptable inside a chat turn.

**Auditing.** Audit stays in the control plane. It should record *which adapters served a request* — that is what makes "where is this tenant's data?" answerable retrospectively rather than by inspecting configuration.

**Retry and idempotency.** Two pre-existing defects will be exposed immediately by any second source, and both must be fixed before one exists: reprocessing a document does not purge its old spans and chunks (so they duplicate), and the transition to `processing` is unconditional (so an at-least-once dispatch OCRs twice). Also note the platform retry budget (`retry_max_total_seconds`) is short; a remote tenant store or a rate-limited provider will need its own, longer, budget rather than inheriting this one.

**Observability.** `AGENTS.md` invariant 4 is strict and correct: log the shape, never the data — no SQL, no prompt text, no document content, no entity values, no connection strings, and metric labels must come from finite, declared sets. Adding adapters must extend that discipline, not dodge it: `store_kind` and `source_type` are safe labels (finite, platform-declared); tenant ids are already allowlist-gated; anything derived from customer configuration is not a label.

---

## 13. Phased migration plan

| Phase | Content | Independently valuable? | Risk |
|---|---|---|---|
| **0. Choke points** | Collapse the ten `_schema()` copies into one. Make engine acquisition go through a single resolver (still returning the one global engine). Reshape the `Retriever` protocol so it stops taking `AsyncSession` and `schema`. Fix the two idempotency defects. | Yes — pure hygiene, no behaviour change | Low |
| **1. Ingestion seam + blob port** | The inbound ingestion contract; upload becomes the first adapter; `OriginalDocumentStore` with MinIO as the default; the OCR branch keys off media type instead of the object key. | Yes — removes the single-door problem | **Medium — this is the only phase that touches the platform's sole document entry point** |
| **2. Control plane + profiles** | Integration profile storage, secret-reference resolution, the minimal document registry, provenance columns on documents, adapter selection wiring. Still only default adapters exist. | Yes — makes configuration explicit and auditable | Low |
| **3. Prove no-retention** | A second blob adapter that stores nothing, and a fake re-openable source, exercised end to end through OCR, chunks, and chat. | Yes — **this is what proves the privacy story is real rather than aspirational** | Low |
| **4. Tenant-hosted PostgreSQL** | Per-tenant connection routing, per-tenant migrations, provisioning into a customer database, network path, failure isolation, monitoring. Vector follows automatically. | Yes — delivers Example C | **High operationally**, moderate in code |
| **5. First pull source (Keka)** | The pull-side contract, sync engine, identity ledger, credentials, scheduling — as already designed in `external-data-source-architecture.md`. | Yes — delivers Example B | Medium |
| **6. Structured-data connector (Path D)** | Semantic-layer contract, validation, least-privilege execution, capability registration, citation handling. | Yes — delivers Example D | Medium |
| **7. Deferred** | External vector databases (option C in §11); non-PostgreSQL relational stores; SharePoint and other sources. | — | Design now, build on demand |

**One rule for phases 4–6:** if adding the first real tenant adapter forces a change inside the application core, the boundary was drawn wrong. Stop and fix the boundary rather than adding a special case.

---

## 14. Isolated first phase versus deferred design

**Implement now (phases 0–3).** These are small, contained, and independently useful even if no tenant ever brings their own infrastructure. Nothing downstream of OCR changes. No new services. No new stores. The deliverable is: documents can arrive from somewhere other than an upload, and originals need not be copied into platform MinIO.

**Design now, build when a customer commits (phases 4–6).** The contracts should be written, and the phase-1 contracts must be *shaped* so these can land without reopening them — specifically: content access must be re-openable, the storage reference must be an outcome that may be NULL, and the index port must not mention sessions or schemas. But the machinery — per-tenant connections, sync engines, semantic layers — should wait for a paying reason.

**Design and defer indefinitely (phase 7).** External vector databases and non-PostgreSQL relational stores. Document what adding one would cost, publish the supported matrix, and decline until someone funds it.

---

## 15. Is this bounded, or is it becoming too broad?

**Phases 0–3 are bounded.** Roughly 130 lines of coupling in two files, plus hygiene. Everything from text spans onward is already infrastructure-agnostic — OCR, chunking, embedding, reranking, and rank fusion are pure functions today. This is not a rewrite; it is finishing two abstractions that were already started and adding two that are missing.

**Phase 4 is bounded in code and unbounded in operations.** Pointing the same schema at a different PostgreSQL server is a small change. Running migrations, monitoring, and support across N customer-owned databases is a permanent operational commitment. That is a business decision, not an architectural one.

**Phases 5 and 6 are new subsystems, not refactors.** A sync engine and a semantic-layer query connector are each real projects with their own failure modes.

**Where it would become too broad — the failure modes to avoid:**

- Abstracting PostgreSQL itself, or introducing a repository per table. The derived layer generates DDL at run time; a vendor-neutral version of that is a second product.
- Merging document sources, blob stores, relational stores, vector stores, and live queries into one "data source" interface. They differ in lifecycle, consistency, ownership, and failure mode. One interface would fit none of them.
- Making this customer-configurable. The finite, developer-maintained supported matrix is precisely what keeps the surface small enough to test.
- Confusing "tenant S3 as a source" with "tenant S3 as blob storage". Same SDK, different jobs, and they must stay different classes even for the same bucket. This is the most likely way the design quietly decays.

**Smallest sequence that reaches the goal:** phase 0 → phase 1 → phase 2 → phase 3. Stop there and reassess. Every later phase should be triggered by a named customer, not by the architecture diagram.

---

## 16. Open decisions

| ID | Decision | Owner | Recommendation |
|---|---|---|---|
| **D1** | Is the supported relational contract "PostgreSQL 16+ with pgvector", full stop? | Product + Eng | **Yes.** Publish it. Treat other engines as funded projects. |
| **D2** | Does the whole `documents` row follow the tenant store, or does a content-free registry stay in the control plane? | Product + Legal | Registry stays; content follows. Filename is the boundary case. |
| **D3** | Are embeddings tenant content for residency purposes? | Legal | Yes. Treat them like OCR text. |
| **D4** | Do conversations and chat messages follow tenant residency? | Legal + Product | They should. Easy to overlook, and they contain question text. |
| **D5** | Can the platform hold DDL rights and create a role inside a customer database? | Security + customer | Needed as designed. Fallback: pre-created role, platform grants only. |
| **D6** | Is eventual consistency acceptable for retrieval if an external vector store is ever used? | Product | Avoid the question by not doing option B. Decide it before option C. |
| **D7** | What happens when a customer's business schema drifts from the approved contract? | Product | Fail the capability loudly. Never guess. |
| **D8** | May Path D results be cached or persisted at all? | Legal + Product | No, initially. |
| **D9** | Naming: this repo already contains two vocabularies for the same concepts (`DocumentSource` vs `SourceConnector`; `document_sources` vs `data_sources`). | Eng | Settle before any spec is written. |
| **D10** | Fix the `002`/`003` column drift (`mime_type`/`file_size_bytes` vs `content_type`/`file_size`) as part of phase 1, or file separately? | Eng | Fix in phase 1 — that phase makes `content_type` authoritative while the chatbot still advertises `mime_type`. |
| **D11** | Portal visibility for documents with no human uploader. | Product | Visible tenant-wide. Today they would be hidden in the UI but answerable in chat. |
| **D12** | Who signs off, on the customer side, on the approved query surface for Path D? | Product + customer | Named role, documented, versioned with the profile. |

---

## 17. Relationship to the other two documents

| Document | Scope | Status after this report |
|---|---|---|
| `external-data-source-architecture.md` | Full external-sync engine: connectors, sync runs, identity ledger, Keka mapping | **Still authoritative for phase 5.** Two revisions: content access must be re-openable rather than a byte buffer, and ingestion must write through the blob port rather than to MinIO directly. |
| `document-ingestion-source-boundary.md` | The ingestion seam and the push/pull split | **Still authoritative for phases 1 and 3.** This report places it inside the wider picture and adds the control-plane and relational-relocation dimensions it did not cover. |
| This report | The five-boundary frame, the control plane, tenant-hosted stores, Path D | The frame the other two sit inside. |

One vocabulary must be chosen across all three before implementation begins (D9).

---

## 18. The answer to the central question

**How does this stay one product?**

Because the part that would be expensive to fork — OCR, chunking, embedding, NER, post-processing, rank fusion, retrieval planning, answer synthesis — **is already infrastructure-agnostic and stays exactly as it is.** It is one core, one codebase, one set of prompts, for every tenant.

Around that core sit four narrow contracts and one new capability:

1. **Where documents come from.** Upload becomes the first adapter rather than a special path.
2. **Where original bytes go — if anywhere.** A NULL storage reference is a valid, supported outcome.
3. **Where derived data lives.** Not an abstraction over databases: the same PostgreSQL schema, relocatable to the customer's own PostgreSQL. One dialect, one set of migrations, a different connection.
4. **Where the index lives and how it is searched.** A protocol that already exists and needs its signature cleaned of sessions and schema names.
5. **Reading a customer's existing business database at chat time.** A new retrieval capability with a reviewed semantic layer, platform-side validation, and least-privilege read-only execution — registered in a tool registry that already exists.

**What must be decided now, while there is still only one implementation of everything**, or the later options quietly become impossible:

- the storage reference is an outcome, may be NULL, and **nothing downstream may parse it** (one line, `ocr_worker.py:197`, currently makes the whole privacy story impossible);
- content access is re-openable, so processing does not silently depend on platform retention;
- the index port never mentions a session or a schema;
- credentials are references, resolved once at the edge;
- control-plane data never becomes tenant-selectable.

**What should be declined, clearly and now:** abstracting PostgreSQL, abstracting SQLAlchemy, one universal data-source interface, customer self-service configuration, and any claim that arbitrary customer infrastructure is supported. The supported matrix is a short, published list, and every addition to it is a funded piece of work.

Nothing in this report has been implemented. No code changed, no migration created, no OpenSpec change opened.
