# Document Ingestion Source Boundary

> **Status:** Architecture proposal for human review. No code, no migration, no OpenSpec change created.
> **Scope:** A single Ports-and-Adapters seam around document ingestion, so that a new document source plugs into one common processing flow. Nothing else.
> **Relationship to prior art:** `docs/architecture/external-data-source-architecture.md` (henceforth **EDS**) designs the full external-sync engine. This document is *narrower and earlier*: it designs only the seam EDS calls "P0 — the ingestion seam", and revises it where the residency/privacy requirement and the "upload becomes an adapter" requirement change the answer. Section 12 reconciles the two.
> **Evidence convention (inherited from EDS):** `Confirmed` = verified in this repo. `Inferred` = reasoned from confirmed facts. `Open Decision` = needs human approval.
> **Precedence:** ADR > PROJECT.md > AGENTS.md > docs/. This is a `docs/` artifact.

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

## 1. Current document lifecycle, end to end

Traced from code, not from the spec.

```
portal  useUpload()                       src/portal/src/hooks/use-upload.ts
  |  XHR multipart, direct to document_service (NOT proxied through gateway)  Confirmed
  v
POST /api/v1/documents                    documents.py:58  upload_document()
  |- purpose validated + role-gated       documents.py:63..79
  |- is_allowed_file(filename)            documents.py:81  -> ocr_worker.py:60 (extension allowlist)
  |- file.read() -> bytes, 50MB cap       documents.py:87..92
  |- doc_id = uuid4()                     documents.py:96
  |- ext = extension(filename)            documents.py:97
  |- blob_path = tenants/{tid}/.../{id}.{ext}   documents.py:98   <- storage key built in the route
  |- checksum = sha256(bytes)             documents.py:99  -> content_hash.py
  |- duplicate lookup by checksum         documents.py:105..114
  |- MinioStorageClient().upload_file()   documents.py:117
  |- INSERT tenant_{tid}.documents        documents.py:120..136  (raw SQL, status='pending')
  |- COMMIT                               documents.py:137
  \- trigger_ocr(doc_id, tid, blob_path, content_type)   documents.py:139
        v
     asyncio.create_task(process_document(...))          ocr_worker.py:271
        |  in-process, non-durable, unbounded            Confirmed (EDS R2)
        v
     process_document()                                  ocr_worker.py:160
       |- SELECT purpose FROM documents                  ocr_worker.py:166
       |- UPDATE status='processing' (unconditional)     ocr_worker.py:173
       |- MinioStorageClient().get_file(blob_path)       ocr_worker.py:185  <- re-reads bytes from MinIO
       |- ext = blob_path.split(".")[-1]                 ocr_worker.py:197  <- PIPELINE BRANCH FROM STORAGE KEY
       |- extract_text_pdf / _pdf_as_image / _image      ocr_worker.py:66/104/126  (pure: bytes -> spans)
       |- INSERT document_text_spans                     ocr_worker.py:210
       |- UPDATE status='processed'                      ocr_worker.py:225
       |- if purpose != 'query': return                  ocr_worker.py:234
       |- chunk_text(span)                               shared/retrieval/chunking.py  (pure)
       |- EmbeddingService().embed_batch()               chat_api/services/embedding_service.py
       \- INSERT document_chunks (CAST ... AS vector)    ocr_worker.py:24..48   <- pgvector
                 v
   extraction (batch, Celery)              extraction_service/worker.py
     |- eligible = documents WHERE status='processed' AND purpose='query'   worker.py:124, extraction.py:183
     |- reads document_text_spans                                           worker.py:356
     \- writes extracted_entities / document_entities / generated relational tables
                 v
   retrieval                                shared/retrieval/retriever.py:69 (pgvector), :110 (tsvector)
     \- document_chunks WHERE purpose='query'
                 v
   chat_api / LangGraph                     chat_api/graph/nodes.py, services/sql_generator.py
```

**One door.** Every document in the platform enters through `documents.py:58`. There is no code path that creates a `documents` row from anything other than a multipart upload. `Confirmed`

---

## 2. Every point coupled to platform upload / MinIO / PostgreSQL / pgvector

### 2.1 Coupled to *platform upload specifically* — this is the whole problem surface

| # | Location | Coupling | Consequence for a second source |
|---|---|---|---|
| C1 | `documents.py:58-139` | The use case **is** the HTTP handler. Validation, hashing, dedup, storage, persistence, and dispatch are inline in a FastAPI route with `UploadFile` and `Request` in scope. | A non-HTTP source must either fabricate an `UploadFile` or duplicate 80 lines. |
| C2 | `documents.py:98` | Storage key computed by the route, then written to the row **and** passed to the worker. | The key is an input to the pipeline, not an output of storage. |
| C3 | `documents.py:139`, `ocr_worker.py:271` | `asyncio.create_task` in the API process. | A 2 000-document backfill runs unbounded inside the web server. Non-durable. `Confirmed` (EDS R2) |
| C4 | `documents.py:169` | `list_documents` filters non-admins by `uploaded_by = :user_id`. | A fetched document has no uploader, so it is invisible in the portal, yet retrievable in chat (`retriever.py:70` filters only on `purpose`). `Confirmed` (EDS R4/OD-9) |
| C5 | `documents` table | No source, no external identity, no source timestamps. Columns are `id, tenant_id, filename, mime_type, file_size_bytes, checksum, storage_uri, status, ocr_applied_flag, error_message, created_at` (`002`) + `content_type, file_size, blob_path, updated_at` (`003`) + `purpose` (`022`) + `uploaded_by` (`030`). | Provenance is unrepresentable. |
| C6 | `documents.py:105-114` | Duplicate detection is checksum-only within a tenant, and deliberately *identifies* rather than merges. | Correct for uploads; insufficient as an identity rule for a repeatedly-enumerated source (same object seen every sync). |
| C7 | `ocr_worker.py:160`, `:271` | `content_type` is a **dead parameter** — accepted by both functions, referenced nowhere in the body. | The declared media type has no authority; see C8 consequence in §10. |

### 2.2 Coupled to MinIO

| # | Location | Coupling |
|---|---|---|
| M1 | `documents.py:117` | `MinioStorageClient()` constructed directly in the route. No port, no injection. |
| M2 | `ocr_worker.py:185-186` | Worker constructs its own client and **re-reads the bytes from MinIO**. The pipeline's only content source is platform-owned object storage. |
| M3 | `ocr_worker.py:197` | `ext = blob_path.split(".")[-1]` — **the OCR branch is selected by parsing the MinIO object key.** This is the single most damaging coupling in the system: it makes the storage key a required, semantically-loaded pipeline input, and it makes "process a document we did not copy into MinIO" structurally impossible. |
| M4 | `storage.py:8-49` | `MinioStorageClient` hardcodes endpoint/keys from global `settings`, calls `_ensure_bucket()` on construction, and builds the key itself in `upload_file` (`storage.py:33`). |
| M5 | `main.py:84` | Readiness probe asserts MinIO. Appropriate today; becomes wrong for a tenant with no platform blob storage. |

Out of scope, listed so they are not swept in: `model_serving/services/model_loader.py:11` and `training_service/worker.py:178` also use MinIO. They store **model artifacts**, not documents. They must not be touched by this change.

### 2.3 Coupled to platform PostgreSQL

| # | Location | Coupling |
|---|---|---|
| P1 | Everywhere | Persistence is raw `text(f"... {schema}.table ...")` against a single global engine (`shared/database.get_engine()`), with `schema = f"tenant_{tid.replace('-','_')}"` duplicated in at least six modules. |
| P2 | `gateway/services/tenant_service.py:52-59` | Provisioning clones `tenant_template` via `pg_tables` + `CREATE TABLE (LIKE ...)`. New template tables are inherited automatically; **foreign keys are not copied**. `Confirmed` (EDS R6) |
| P3 | Schema drift | `002` created `mime_type` / `file_size_bytes` / `storage_uri`; `003` added `content_type` / `file_size` / `blob_path`. The upload path writes only the `003` set. `sql_generator.py:24` exposes the *`002`* names to the LLM, and `dashboard.py:694` selects `file_size_bytes` — both read columns that are NULL on every uploaded document. `Confirmed`. Pre-existing defect; this change must not paper over it. |

### 2.4 Coupled to pgvector

| # | Location | Coupling |
|---|---|---|
| V1 | `ocr_worker.py:24-48` | `INSERT ... CAST(:embedding AS vector)` into `{schema}.document_chunks`. |
| V2 | `retriever.py:69` | `1 - (embedding <=> :q)` plus `ORDER BY embedding <=> :q`. |
| V3 | `retriever.py:110` | `chunk_tsv @@ plainto_tsquery` — the sparse half lives in the same table. |
| V4 | `024_hybrid_retrieval_hnsw.py` | HNSW index. |

**Deliberately not addressed by this change.** V1–V4 are the vector-store concern (concern 4 of the brief's four), not the source concern. Section 11 states what must merely stay *possible*.

---

## 3. What is already source-independent

This is the good news, and it is why the seam can be small.

| Component | File | Why it is already source-blind |
|---|---|---|
| Text extraction | `ocr_worker.py:66, 104, 126` | `extract_text_pdf/_image/_pdf_as_image` are pure `bytes -> list[span]`. They never learn where the bytes came from. |
| Chunking | `shared/retrieval/chunking.py` | Pure `str -> list[Chunk]`. |
| Embedding | `chat_api/services/embedding_service.py` | Pure `list[str] -> list[vector]`. |
| Extraction eligibility | `extraction.py:183`, `worker.py:124` | Selects on `status='processed' AND purpose='query'` only. A fetched document becomes eligible by existing. |
| Extraction input | `worker.py:356` | Reads `document_text_spans`. Origin-blind. |
| Entity projection | `extraction_service/services/relational_projection.py`, `entity_store.py` | Keyed by `document_id`. |
| Retrieval | `retriever.py:69, 110` | Filters `purpose='query'`. Origin-blind. |
| Reranking | `shared/retrieval/reranker.py`, `model_serving` | Operates on chunk text. |
| Chat / LangGraph | `chat_api/graph/nodes.py`, `rag_orchestrator.py` | Consumes chunks and entities. |
| Annotation | `annotation_service/**` | Joins `documents` by id for filename and purpose only (`tasks.py:54, 117`). |
| Tenant isolation | `shared/tenant_context.py`, per-service `middleware/tenant_context.py` | `tenant_id` from JWT, never from body. `Confirmed` |
| Content hashing | `content_hash.py` | Pure. One algorithm for every origin. |

**The pipeline from `document_text_spans` onward is already a common pipeline.** Nothing downstream of OCR knows how a document arrived. The coupling is confined to roughly 90 lines in `documents.py:58-139` and 40 lines in `ocr_worker.py:160-200`. `Confirmed`

---

## 4. The proposed boundary — smallest useful seam

### 4.1 The one structural insight that changes the shape

The brief proposes a single `DocumentSource` abstraction with `PlatformUploadAdapter` as its first implementation. **Repository evidence says that is one abstraction too few.**

Upload is a **push** source: bytes arrive unbidden, over HTTP, once, already in hand. Keka / S3 / Azure Blob are **pull** sources: the platform enumerates, decides what is new, then fetches. A single interface that both satisfy must contain `discover()` — which upload cannot implement except as a lie (`yield nothing`) — and `check_connection()` — which upload cannot implement except as `return OK`. Two stub methods on the very first adapter is the classic sign of a merged abstraction.

The split the code supports:

```
  +--------------------------------------------------------------+
  |  DRIVING SIDE  (adapters call in)                            |
  |                                                              |
  |  HTTP multipart  -->  UploadIngestionAdapter          --+    |
  |  Keka API        -->  [pull runner + Keka DocumentSource]-+   |
  |  Tenant S3       -->  [pull runner + S3 DocumentSource]  -+   |
  |  Azure Blob      -->  [pull runner + Azure DocumentSource]-+  |
  +----------------------------------------------------------|---+
                                                              v
              +===================================================+
              |  PORT (inbound):  DocumentIngestionService         |
              |      ingest(IngestionRequest) -> IngestionResult   |
              |  -- the application use case, owns:                |
              |     identity, validation, checksum, dedup,         |
              |     retention decision, row write, dispatch        |
              +============+==========================+============+
                           |                          |
        PORT (outbound):   |                          |  PORT (outbound):
        OriginalDocumentStore                         |  ProcessingDispatcher
          MinioOriginalStore  (today)                 |    InProcessDispatcher (today)
          NoRetentionStore    (privacy tenants)       |    CeleryDispatcher    (later)
          TenantS3Store       (deferred)              |
                           |                          v
                           v            existing pipeline, unchanged
                    tenant_{tid}.documents  --> OCR > spans > chunks > embeddings
                                                > extraction > retrieval > chat
```

Three ports. Not four, not one.

### 4.2 The three ports

**Port 1 — `DocumentIngestionService` (inbound / driving).** The application use case. One method:

```python
# src/document_service/ingestion/contracts.py   (illustrative — NOT implementation)

async def ingest(self, request: IngestionRequest) -> IngestionResult: ...
```

Every adapter calls this. It is the only thing that may create a `documents` row. It owns: platform id generation, extension and size validation, checksum computation, duplicate identification, the retention decision, the row write, and processing dispatch. It owns **no** knowledge of HTTP, Keka, S3, or Azure.

**Port 2 — `DocumentContent` (outbound / driven, supplied by the adapter).** How the use case obtains bytes without knowing the source:

```python
class DocumentContent(Protocol):
    async def open(self) -> AsyncIterator[bytes]: ...   # re-openable, not a one-shot buffer
    declared_media_type: str | None
    declared_size_bytes: int | None
```

`open()` being **re-openable** is a load-bearing decision, not a style choice — see §9.3.

**Port 3 — `OriginalDocumentStore` (outbound / driven).** Where original bytes go, *if anywhere*:

```python
class OriginalDocumentStore(Protocol):
    async def put(self, tenant_id: str, document_id: str, ext: str,
                  content: DocumentContent) -> StorageReference | None: ...
    async def open(self, ref: StorageReference) -> AsyncIterator[bytes]: ...
```

Today's only implementation wraps the existing `MinioStorageClient` unchanged. `NoRetentionStore` returns `None` and is what makes the privacy requirement expressible. This port exists **now**, with one real implementation, purely so that "do not copy this tenant's documents into platform MinIO" is a configuration value rather than a fork of the pipeline.

**Port 4 — `ProcessingDispatcher`** is a one-line seam (`InProcessDispatcher` = today's `asyncio.create_task`; `CeleryDispatcher` later). Included because §10 makes it necessary anyway and it costs nothing.

### 4.3 What is deliberately *not* in this change

- **`DocumentSource` (the pull-side port: `check_connection` / `discover` / `fetch`).** Its contract is specified in EDS §7 and does not need re-deriving. It is *not built here*. Upload does not implement it. When it lands, its runner calls `DocumentIngestionService.ingest()` like any other adapter.
- The sync engine, `data_sources` / `sync_runs` / `external_documents` / `sync_run_errors` tables, credential resolution, scheduling. All EDS. All later.
- Any port over PostgreSQL, pgvector, chunking, embedding, extraction, retrieval, or chat.

### 4.4 Naming

| Brief's name | Recommended | Reason |
|---|---|---|
| `DocumentIngestion` | **`DocumentIngestionService`** (module `src/document_service/ingestion/`) | Matches the `document_service/services/*` convention. |
| `PlatformUploadAdapter` | **`UploadIngestionAdapter`** — and it is simply the existing route, thinned | It adapts HTTP to the port; it is not a "platform" concept. |
| `DocumentSource` | **keep `DocumentSource`** for the deferred pull port | Aligns with the brief. Note EDS calls it `SourceConnector`; one of the two names must win before implementation. **`Open Decision` OD-N1.** |
| `source_instance_id` | **`source_id`**, with the configured connection row in a `document_sources` table | EDS already fixed on `source_id` + `data_sources`. Introducing a third vocabulary for the same concept is avoidable debt. **`Open Decision` OD-N2** (`data_sources` vs `document_sources`; the latter is more honest now that Path B connectors also exist — see §13). |

---

## 5. Validating the proposed normalization model against the repository

The brief's hypothesis, field by field, checked against what the code actually requires.

| Field | Verdict | Evidence |
|---|---|---|
| `id` platform UUID | **Confirmed necessary** | `documents.py:96`; every derived table references it. Never reuse an external id — soft delete (`documents.py:307`) would otherwise permanently block re-ingest. |
| `tenant_id` | **Confirmed necessary** | Schema routing (`_schema`), MinIO prefix (`storage.py:33`), every downstream query. |
| `origin` | **Keep, but derived** | Useful as a cheap portal filter. It is a function of `source_type`, so it must be written by the use case, never accepted from an adapter. EDS also proposes it. |
| `source_type` | **Confirmed necessary** | The discriminator that selects adapter code. Must be the *only* provider-aware column. |
| `source_instance_id` | **Necessary — rename to `source_id`** | See §4.4. |
| `external_id` | **Necessary, nullable** | See §6.2 on where uniqueness lives. |
| `filename` | **Confirmed necessary and load-bearing** | Drives `is_allowed_file` (`ocr_worker.py:60`), the extension, the storage key, the `subject.filename` denormalisation (`worker.py:151`), portal display, and the chat filename-defect path (`sql_generator.py`, `_FILENAME_DEFECT_PREFIX`). |
| `content_type` | **Necessary — and must be promoted from decorative to authoritative** | Today it is stored but *never read*: `process_document`'s `content_type` parameter is dead (`ocr_worker.py:160, 271`) and the branch comes from the object key (`:197`). |
| `file_size` | **Confirmed necessary** | 50 MB cap (`documents.py:88`). |
| `checksum` | **Confirmed necessary, platform-computed** | `content_hash.py`; dedup at `documents.py:105`. A provider-supplied hash is a *hint* and belongs in `source_version`, never in `checksum`. |
| `source_version` | **Necessary, nullable** | Cheapest change detection when a provider has one (S3 ETag/versionId, Azure ETag). NULL for upload and for Keka. |
| `source_created_at` / `source_modified_at` | **Necessary, nullable — and must never be defaulted to ingest time** | EDS §8.2 is right: a wall-clock default is indistinguishable from a real modification and silently defeats the comparison the field exists for. |
| `purpose` | **MISSING from the brief's model — must be added** | Decides embedding (`ocr_worker.py:234`) and extraction eligibility (`extraction.py:183`). Not derivable from any source. |
| `status` | **Confirmed necessary** | Existing state machine. `deleted` is a soft delete. |
| `storage_reference` | **Necessary, nullable — semantics revised** | Today `blob_path` is an *input* the route invents (`documents.py:98`). It must become an *output* of `OriginalDocumentStore.put()`, and `NULL` must mean "original not retained by the platform", not "broken row". |
| `origin_metadata` | **Necessary, JSONB, opaque** | Read by the owning adapter and by humans debugging. Read by the generic layer: never. |
| `created_at` / `updated_at` | Present already | `002`, `003`. |
| — | **`ingested_by` MISSING from the brief's model** | `uploaded_by` exists (`030`) and drives the non-admin list filter (`documents.py:169`). A fetched document has no human uploader. Either the column becomes nullable with a source-attribution fallback, or C4/OD-9 must be answered. Not optional: leaving it produces documents that are invisible in the portal but answerable in chat. |
| — | **`retention_mode` — recommended addition** | `platform_blob` \| `source_only`. Makes the privacy posture readable on the row instead of inferable from `storage_reference IS NULL`. `Open Decision` OD-N3. |

**Verdict on the hypothesis: sound, with three gaps** — `purpose`, actor attribution, and the redefinition of `storage_reference` from input to outcome.

### 5.1 The durable identity claim

The brief proposes `(source_instance_id, external_id)`. **Agreed**, for the reasons EDS §12 gives: it survives renames, content changes, and re-discovery, where filename, checksum, and source type alone do not. Where this document differs from EDS is only *where the uniqueness constraint lives* — see §6.2.

---

## 6. The canonical contract

### 6.1 In-process contract (the port's payload)

```python
# illustrative — NOT implementation

@dataclass(frozen=True)
class SourceRef:
    source_type: str                 # 'platform_upload' | 'keka' | 's3' | 'azure_blob' | ...
    source_id: str                   # the configured connection for this tenant
    external_id: str | None = None   # opaque, stable within source_id; None for ad-hoc upload
    source_version: str | None = None
    source_created_at: datetime | None = None
    source_modified_at: datetime | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)   # opaque, never read generically

@dataclass(frozen=True)
class IngestionRequest:
    tenant_id: str                   # from trusted context only — never from an adapter payload
    filename: str
    content: DocumentContent         # re-openable byte access, NOT bytes
    purpose: Literal['query', 'training']
    source: SourceRef
    declared_media_type: str | None = None
    declared_size_bytes: int | None = None
    actor: Actor                     # Human(user_id) | SourceSystem(source_id)
    retention: RetentionPolicy       # resolved by the use case from tenant config, not by the adapter

@dataclass(frozen=True)
class IngestionResult:
    document_id: str
    status: str                      # 'pending' | 'unchanged'
    checksum: str
    duplicate_of: str | None
    storage_reference: str | None
```

### 6.2 Persistence — staged deliberately

**Phase 1 (this change): additive columns on `documents`, no new tables.**

```sql
ALTER TABLE tenant_template.documents
  ADD COLUMN IF NOT EXISTS origin             VARCHAR(16)  NOT NULL DEFAULT 'platform_upload',
  ADD COLUMN IF NOT EXISTS source_type        VARCHAR(32)  NOT NULL DEFAULT 'platform_upload',
  ADD COLUMN IF NOT EXISTS source_id          VARCHAR      NULL,
  ADD COLUMN IF NOT EXISTS external_id        VARCHAR(512) NULL,
  ADD COLUMN IF NOT EXISTS source_version     VARCHAR(255) NULL,
  ADD COLUMN IF NOT EXISTS source_created_at  TIMESTAMPTZ  NULL,
  ADD COLUMN IF NOT EXISTS source_modified_at TIMESTAMPTZ  NULL,
  ADD COLUMN IF NOT EXISTS origin_metadata    JSONB        NULL,
  ADD COLUMN IF NOT EXISTS retention_mode     VARCHAR(20)  NOT NULL DEFAULT 'platform_blob';
```

All additive and defaulted, following the `030`/`034` pattern: apply to `tenant_template`, then loop over `tenant\_%` schemas. New tenants inherit via the `pg_tables` clone (`tenant_service.py:52`). No foreign keys — cloned schemas cannot carry them (`Confirmed`, EDS R6).

**No unique index on `(source_id, external_id)` in phase 1.** This is where EDS §6.3 and the brief pull in opposite directions, and both are partly right:

- EDS is correct that a unique constraint on a *soft-deleted* table permanently blocks re-ingest, that a discovered-but-not-yet-fetched object has no `documents` row to live on, and that content-addressed reuse is many-to-one.
- The brief is correct that provenance belongs on the document — every consumer that wants to show or filter by origin would otherwise need a join.

The resolution is that these are two different facts. **Provenance** (where this document came from) is document metadata and lives on `documents` from phase 1. **Sync identity and bookkeeping** (what exists over there, what state is it in, when was it last seen) is a ledger, and lands with the pull runner as EDS's `external_documents`, carrying the `UNIQUE (source_id, external_id)`. Phase 1 therefore ships provenance only, and can ship without answering any sync question. `Inferred`

**Phase 1 also does not touch** `document_text_spans`, `document_chunks`, `extracted_entities`, `document_entities`, `extraction_runs`, or any `public` table.

### 6.3 What must never enter the contract

Restating the brief's list because it is exactly right, with the enforcement point named:

| Forbidden in the canonical contract | Correct home |
|---|---|
| Cloud credentials, Keka tokens, connection strings | Secret store, resolved by ref at run time (AGENTS.md invariant 3) |
| Temporary or pre-signed download URLs | Inside the adapter, for the lifetime of one `DocumentContent` |
| Bucket names, container names, MinIO paths as *required* fields | `storage_reference`, nullable, written by `OriginalDocumentStore` |
| PostgreSQL schema names, pgvector table names, index details | The persistence layer |

`origin_metadata` is the pressure valve, and it has one rule: **the generic layer never reads inside it.** Nothing mechanically enforces that (EDS R11); it is a review invariant.

---

## 7. What belongs in `DocumentSource` — and what does not

For the deferred pull port. Stated now because the phase-1 contract has to be shaped so this can land without reopening it.

**Belongs in a `DocumentSource` adapter:**
authentication and token lifecycle; base URLs, buckets, containers, subdomains; pagination and continuation tokens; rate limiting and transport retry; construction of the opaque `external_id`; extraction of `source_version` and source timestamps from provider headers; deriving a media type when the provider supplies none; mapping provider errors to the generic taxonomy; enumeration scoping; provider metadata capture; producing a `DocumentContent` handle.

**Explicitly does NOT belong:**
any database session or SQL; any knowledge of MinIO, `blob_path`, or `storage_reference`; any knowledge of pgvector, chunking, embeddings, extraction, or retrieval; computing the checksum (the platform does, over the bytes it actually read — `content_hash.py`); choosing `purpose` (application policy); choosing retention (tenant policy); deciding whether a document is new or changed (the runner's job, per EDS §5 — a `sync()` method on the adapter would have every provider reimplement idempotency differently and wrongly); writing anything, anywhere; resolving its own credentials from a ref (it receives resolved values, so it has no API with which to ask for another tenant's — EDS §14.3); knowing its own `source_id` beyond opaque echo.

**The one-sentence test:** if an adapter needs a database session, a storage client, or a `tenant_id`-free code path, the boundary has been drawn in the wrong place.

---

## 8. Platform upload becomes the first adapter

Behaviour identical. The route keeps its URL, its status codes, its response body, and its existing tests.

```python
# documents.py — after (illustrative, ~15 lines instead of ~85)

@router.post("", status_code=201)
async def upload_document(file: UploadFile = File(...), purpose: str = Form("query"),
                          request: Request = None,
                          service: DocumentIngestionService = Depends(...)):
    _validate_purpose_for_role(purpose, request.state.role)        # HTTP/role policy stays here
    result = await service.ingest(IngestionRequest(
        tenant_id           = get_tenant_id(request),
        filename            = file.filename or "",
        content             = UploadFileContent(file),             # the adapter's DocumentContent
        purpose             = purpose,
        source              = SourceRef(source_type='platform_upload',
                                        source_id=platform_upload_source_id(tenant_id)),
        declared_media_type = file.content_type,
        actor               = Human(request.state.user_id),
        retention           = resolve_retention(tenant_id),
    ))
    return {...}                                                   # unchanged response shape
```

What moves into the use case: extension allowlist, size cap, checksum, duplicate lookup, id generation, storage write, row insert, dispatch. What stays in the route: JWT/tenant resolution, the role-to-purpose policy (`documents.py:63-79`), multipart mechanics, HTTP status mapping.

**Upload gets a real `source_id`, not a NULL.** Each tenant has exactly one implicit `platform_upload` source. This is the difference between "upload is an adapter" and "upload is the default case plus a nullable column", and it is why `source_id` is not nullable in spirit even though phase 1 declares it nullable for migration safety. `Inferred`

Upload does **not** implement `DocumentSource`. It has nothing to enumerate.

---

## 9. How the other sources plug in later

### 9.1 Keka

Per EDS §21, unchanged by this document: a `KekaDocumentSource` inside `providers/keka/` owning OAuth, `GET /hris/employees`, `GET /hris/employees/documents`, the attachment-URL round trip, `{employeeId}:{documentId}:{attachmentId}` as the opaque `external_id`, extension-derived content types (Keka supplies none — `Confirmed`), and the 50/min per-endpoint bucket. Keka supplies no version and no modified timestamp, so `source_version` and `source_modified_at` are NULL and change detection falls through to checksum — which is exactly why those fields are nullable rather than defaulted.

Outside `providers/keka/`, Keka is one string in a `source_type` column. **No Keka-specific pipeline exists**, because the pull runner ends at `DocumentIngestionService.ingest()` — the same call the upload route makes.

### 9.2 S3 / Azure Blob

| | S3 | Azure Blob |
|---|---|---|
| `external_id` | `bucket/key` (plus versionId when versioning is on) | `container/blob` |
| `filename` | basename of the key | basename of the blob name |
| `content_type` | object metadata | blob headers |
| `file_size` | object size (pre-download size gate) | blob size |
| `source_version` | versionId or ETag | ETag |
| `source_modified_at` | LastModified | Last-Modified |
| content access | authenticated `GetObject` stream | authenticated download stream |

Both are strictly *easier* than Keka: they have versions and timestamps, so cheap change detection works and no download-to-compare is needed. Neither requires a new field on the contract designed in §6 — which is the test the contract has to pass, and does. `Inferred`

**Note the trap the brief already flags:** tenant S3 as a *source* and tenant S3 as *blob storage* are different concerns that happen to share an SDK. `S3DocumentSource` implements `DocumentSource`. `TenantS3OriginalStore` implements `OriginalDocumentStore`. They are separate classes with separate configuration, even for the same bucket. Merging them is the single most likely way this design decays.

### 9.3 The consequence for `DocumentContent` that must be decided now

Today the bytes are read twice: once by the route (`documents.py:87`) and again by the worker from MinIO (`ocr_worker.py:186`). If the platform does not retain the original, **the second read has no source** — unless the adapter can be asked to open the content again.

Two options, and the choice constrains every future adapter:

| Option | Cost |
|---|---|
| **A. `DocumentContent` is a one-shot buffer** (EDS §8.5: `fetch() -> bytes`) | Reprocessing a non-retained document is impossible without a full re-sync. Retention effectively becomes mandatory, and the privacy requirement dies quietly. |
| **B. `DocumentContent` is re-openable** — it holds a source-scoped locator the adapter can resolve on demand | The adapter must be reachable at processing time, so credentials must be resolvable outside the original request. Slightly more machinery. **Recommended.** |

**B is the load-bearing choice**, and it must be made in phase 1 even though only the upload adapter exists — because the upload adapter's `DocumentContent` is trivially re-openable *only if the bytes were retained*, which is the honest and correct constraint to encode: **a non-retained document can only be reprocessed by re-fetching from its source.** Phase 1 should therefore keep buffering upload bytes in memory for the first pass (today's behaviour, bounded by the 50 MB cap) while typing the port as re-openable. `Open Decision` OD-N4.

---

## 10. Keeping the processing pipeline unchanged

The pipeline stays untouched **except for four changes, three of which are pre-existing defect fixes that EDS already identified independently.**

| # | Change | Why it is required now | Pre-existing defect? |
|---|---|---|---|
| 1 | `process_document` takes `(document_id, tenant_id)` and resolves content via the ports; the OCR branch keys off the **document's media type**, not `blob_path.split(".")` (`ocr_worker.py:197`) | Without it, no-retention ingestion is structurally impossible and `content_type` stays a dead parameter | Partly — the dead parameter is (`ocr_worker.py:160, 271`) |
| 2 | `UPDATE ... status='processing'` becomes conditional (`WHERE status='pending'`) | At-least-once dispatch double-OCRs | **Yes** (EDS R1) |
| 3 | Delete existing spans and chunks before reprocessing | Re-ingest duplicates every span and chunk | **Yes** (EDS R1) |
| 4 | `trigger_ocr` becomes the injectable `ProcessingDispatcher` | Bulk backfill inside the web process is unsafe | **Yes** (EDS R2) |

**Unchanged, verified against code rather than assumed:** `extract_text_pdf` / `extract_text_image` / `extract_text_pdf_as_image` bodies; `chunking.py`; `EmbeddingService`; the `document_text_spans` and `document_chunks` writes and their pgvector cast; `extraction_service/**` in its entirety; `shared/retrieval/**`; `chat_api/**`; `annotation_service/**`; `model_serving/**`; `training_service/**`; `gateway/services/tenant_service.py`; every `middleware/tenant_context.py`; the portal.

Change 1 has a knock-on worth stating plainly: it is the fix that makes `content_type` authoritative, and it is therefore also the moment to decide what to do about the `002`/`003` column drift (P3) — because a design that promotes `content_type` while `sql_generator.py:24` still advertises `mime_type` to the LLM is internally inconsistent. Recommendation: fix the drift in the same change, as a narrow, separately-verifiable task. `Open Decision` OD-N5.

---

## 11. Storage and privacy — decided now vs deferred

### 11.1 The four concerns, kept apart

| # | Concern | Today | Port that exists after this change | Port deferred |
|---|---|---|---|---|
| 1 | Document **source** | upload only | `DocumentIngestionService` + `SourceRef` | `DocumentSource` (pull) |
| 2 | Original **blob** storage | MinIO, hardcoded (`documents.py:117`, `ocr_worker.py:185`) | **`OriginalDocumentStore`** (MinIO + NoRetention) | tenant S3 / Azure implementations |
| 3 | **Relational** persistence | platform PostgreSQL, raw schema-qualified SQL, one global engine | *(none — deliberately)* | tenant database |
| 4 | **Vector/index** storage | pgvector in the same tenant schema | *(none — deliberately)* | tenant vector store |

Concerns 3 and 4 get **no port now**. Building one would be exactly the "refactor for architectural purity" the brief forbids, and there is no second implementation to validate it against. What matters is that they stay *reachable*, and the evidence says they do: every relational write goes through `_schema(tenant_id)` plus `get_engine()` (P1), so a future `resolve_engine(tenant_id)` is a localised substitution rather than a rewrite. Retrieval is similarly funnelled through `retriever.py`. Neither is made harder by this change.

### 11.2 Decisions that must be made now for tenant-owned infrastructure to remain possible

1. **`storage_reference` is an outcome, not an input, and NULL is legitimate.** If the storage key stays an input invented before storage runs (`documents.py:98`), no adapter can ever decline to store.
2. **Nothing downstream may parse `storage_reference`.** `ocr_worker.py:197` does exactly this today and must stop. This is the single change without which the privacy requirement is unreachable.
3. **`DocumentContent` is re-openable** (§9.3), so processing is not silently dependent on platform retention.
4. **Retention is resolved by the use case from tenant configuration**, never chosen by an adapter and never inferred from the source type. A tenant may forbid retention for uploads too.
5. **Derived data is recognised as tenant data in the model now**, even though it stays in platform PostgreSQL. `retention_mode` describes originals only; a future `derived_residency` is a *different* field. Conflating them would make "originals stay with the tenant, derived data is ours" — the likely first real policy — unrepresentable.
6. **Checksum is always platform-computed over bytes the platform actually read.** A non-retaining tenant still gets dedup and change detection.
7. **Readiness must not assert MinIO unconditionally** (`main.py:84`) once a no-retention tenant exists. Note now; change when the second store lands.

### 11.3 Explicitly deferred

Tenant blob adapters; tenant relational adapters; tenant vector adapters; cross-store consistency and orphan GC; per-tenant secret resolution (EDS §14 — no credentials exist in phase 1, so `CredentialProvider` is not needed yet); residency policy as a product surface; and any answer to "what happens to derived data when a tenant revokes residency consent". That last one is a genuine gap in both documents and should be raised with product before the first privacy-sensitive tenant, not before this change.

---

## 12. Reconciliation with `external-data-source-architecture.md`

| Topic | EDS says | This document says | Resolution |
|---|---|---|---|
| The ingestion seam | P0: extract `ingest_document()` from the route | Same, plus: it is a *port* with a typed request, and upload is an *adapter* | Compatible; a refinement, not a contradiction |
| Adapter interface | `SourceConnector` with `check_connection` / `discover` / `fetch` | Agreed — but pull-only, and upload must not implement it | **Revision.** EDS implies one connector abstraction; upload cannot join it honestly |
| Where bytes come from | `fetch() -> bytes` | Re-openable `DocumentContent` | **Revision**, forced by the no-retention requirement, which EDS did not have |
| Storage | `ingest_document()` writes MinIO directly | `OriginalDocumentStore` port; MinIO is one implementation | **Revision**, same cause |
| Identity | `external_documents` ledger, `UNIQUE (source_id, external_id)` | Agreed for sync state; provenance columns on `documents` in phase 1 | **Compatible** — different facts, different homes (§6.2) |
| `documents` columns | `origin`, `source_id` | Those plus `source_type`, `external_id`, `source_version`, source timestamps, `origin_metadata`, `retention_mode` | **Extension** |
| OCR fixes | R1, R2 in P0 | Same, plus the `blob_path`-parsing fix | **Extension** |
| Naming | `data_sources`, `SourceConnector` | `document_sources`, `DocumentSource` | **Open — OD-N1/N2.** Must be settled before either is implemented |
| Everything sync | Fully designed | Out of scope | **Deferred to EDS** |

EDS remains the authority for anything past the seam. This document supersedes EDS only on the four rows marked **Revision**, and only because the residency requirement and the "upload is an adapter" requirement postdate it.

---

## 13. Path B — direct structured-data query — and why it must stay separate

```
A.  Keka/S3/Azure raw docs -> DocumentSource -> IngestionRequest -> OCR/NER/chunk/embed
                           -> platform or tenant stores -> chatbot
B.  Tenant AWS/RDS/Aurora  -> tenant query connector -> chatbot
```

**They must not share an abstraction, and the reason is structural, not stylistic:** Path A produces `documents` rows and derived data whose lifecycle the platform owns. Path B produces *rows the platform never stores*, over a schema the platform does not control, at query time. Nothing in Path B has a document id, a checksum, a purpose, a status, or a `storage_reference`. Forcing a tenant database behind `DocumentSource` would require inventing all six.

The correct seam for Path B is on the **retrieval** side, alongside the existing tool surface — `chat_api/graph/nodes.py` already dispatches `structured_retrieval` with a scope, and `shared/entity_views.resolve_query_surface` already assembles approved schema context for `sql_generator`. A tenant query connector is a *third retrieval tool*, registered per tenant, not a document source.

Its safety requirements, restating the brief with the existing enforcement points named:

1. The LLM never holds a connection. It receives **approved schema context only** — allowed tables, views, columns, relationships, business definitions, example queries — which is precisely the shape `WHITELISTED_TABLES` (`sql_generator.py:20-26`) and `QuerySurface` already have for the platform's own schema.
2. The LLM **proposes**; the platform **validates and executes**. Existing machinery: single-statement, read-only, allowlisted relations and columns, mandatory `LIMIT` (`DEFAULT_LIMIT = 100`), `MAX_SQL_LENGTH`, and the bounded retry loop with typed defect classes.
3. Execution runs through a tenant-specific connector on a **read-only credential** with its own timeout and row cap, resolved by secret ref — never a raw credential in config or in a database row.
4. Per AGENTS.md invariant 4, generated SQL and result values are never logged and never placed on spans.

Concretely: Path B reuses `sql_generator`'s *validation discipline* and none of `document_service`. `Confirmed` that the discipline exists; `Inferred` that it generalises to a foreign schema — that generalisation is its own design exercise and is out of scope here.

---

## 14. Migration plan

Each phase is independently landable and independently verifiable. Phase 1 is the only one that touches existing behaviour.

| Phase | Content | Verification |
|---|---|---|
| **1. Ingestion seam** | `src/document_service/ingestion/`: `DocumentIngestionService`, `IngestionRequest`/`IngestionResult`, `SourceRef`, `DocumentContent`, `OriginalDocumentStore` (+ `MinioOriginalStore`), `ProcessingDispatcher` (+ `InProcessDispatcher`). Route becomes `UploadIngestionAdapter`. Pipeline fixes 1–4 (§10). No new tables, no external concepts. | Every existing `tests/test_document_ingestion.py` and `tests/test_document_content_hash.py` case passes **unmodified** — this is the regression gate. New: double-dispatch is a no-op; reprocess does not duplicate spans; media type drives the OCR branch. |
| **2. Provenance columns** | The additive migration in §6.2, applied to `tenant_template` plus the `DO $$` loop. Upload writes `source_type='platform_upload'` and its per-tenant `source_id`. Portal and list attribution answer C4/OD-9. | Migration applies to a seeded multi-tenant DB; a newly provisioned tenant inherits the columns via the `pg_tables` clone; existing rows keep working on defaults. |
| **3. Retention port proof** | A second `OriginalDocumentStore` implementation (`NoRetentionStore`) plus a fake re-openable source, exercised end to end: OCR to spans to chunks to retrieval, with `storage_reference IS NULL`. | **This is the phase that proves the privacy requirement is real** rather than aspirational. No provider code involved. |
| **4+** | Hand off to EDS P1–P10: `DocumentSource` contract, sync engine, `data_sources`/`external_documents`, credentials, Keka, S3/Azure. | Per EDS §25. |

**Hard rule for phase 4+:** if adding the first pull source requires changing anything in `src/document_service/ingestion/`, the boundary was drawn wrong. Stop and revisit rather than special-case. (EDS makes the same commitment at its P5.)

### 14.1 Risks

| # | Risk | Severity | Mitigation |
|---|---|---|---|
| R1 | Phase 1 regresses the only document entry point in the platform | **High** | Existing tests must pass unmodified; response shape frozen; no behaviour change shipped alongside the extraction |
| R2 | The `blob_path`-parsing fix changes the OCR branch for real documents (a `.pdf` whose declared type is `application/octet-stream`) | **High** | Resolution order: declared media type, then filename extension, then sniff. Extension remains the fallback, so today's behaviour is preserved |
| R3 | Ports built with one implementation encode today's assumptions | Medium | Phase 3 exists precisely to falsify this before any provider work |
| R4 | Duplicate spans and chunks on reprocess (EDS R1) | **High** | Fixed in phase 1, before anything can dispatch twice |
| R5 | The `002`/`003` column drift (P3) is entrenched by a change that promotes `content_type` | Medium | OD-N5 — fix in the same change or file it explicitly |
| R6 | The upload/pull split invites a "just add `discover()` to upload" simplification later | Medium | Stated invariant plus review; upload has nothing to enumerate |
| R7 | Externally-ingested documents invisible in the portal but answerable in chat (C4 / EDS R4) | Medium | Must be answered in phase 2, not deferred to the first provider |
| R8 | `origin_metadata` becomes a de-facto generic field | Low | Review invariant; nothing mechanically prevents it (EDS R11) |
| R9 | Scope creep into concerns 3 and 4 | Medium | §11.1 states the boundary; no port for PostgreSQL or pgvector in any phase of this plan |

### 14.2 Required OpenSpec artifacts

Per repo convention (`proposal.md`, `design.md`, `specs/<capability>/spec.md`, `tasks.md`, `verification.md`; `openspec/config.yaml` schema `spec-driven-verified`) and AGENTS.md invariants 1–2.

**Change `document-ingestion-source-boundary`** (phases 1–3):

- `proposal.md` — why, and non-goals stated explicitly: no full-platform hexagonal migration, no pull sources, no tenant storage adapters.
- `design.md` — the three ports, the push/pull split and its justification, the re-openable-content decision, the provenance-versus-ledger split, and the reconciliation table in §12.
- `specs/document-ingestion/spec.md` — **delta** to the existing capability. Modified requirements: *Document Upload* (externally unchanged, restated as adapter-over-port), *Async OCR Processing* (media type is authoritative; reprocess is idempotent; dispatch is injectable). Added: *Ingestion Source Provenance*, *Original Document Retention*. The existing spec's "SHALL store the file in MinIO at path ..." is a **breaking-language change** and must be restated as "SHALL store the original through the configured original-document store, when retention is enabled".
- `specs/document-source-boundary/spec.md` — **new** capability: the port contract, what a source may and may not do, and the identity rule.
- `tasks.md`, `verification.md` — every acceptance criterion needs an executable artifact that fails when its `THEN` clause is violated (invariant 2).

Not required now: any `secret-hygiene` delta (no credentials in phases 1–3), any `retrieval-core` or `chat-api` delta, any `infrastructure` delta.

An **ADR** is warranted — the push/pull split, and the decision to port original-blob storage while deliberately *not* porting relational and vector storage, are exactly the kind of decision ADR-001 exists to record. Proposed: `docs/adr/011-document-ingestion-source-boundary.md`.

---

## 15. Is this an isolated improvement, or a full hexagonal migration?

**Isolated. Emphatically.** The evidence is in §3: everything from `document_text_spans` onward is already source-independent. OCR, chunking, and embedding are already pure functions of bytes and text. Extraction selects on `status` and `purpose`. Retrieval selects on `purpose`. Chat consumes chunks and entities. None of them can tell an upload from a fetch today, and none of them will need to.

The coupling is confined to roughly **130 lines in two files** — `documents.py:58-139` and `ocr_worker.py:160-200` — and of those, one line (`ocr_worker.py:197`, the OCR branch parsed out of the MinIO object key) is doing most of the damage.

A full-platform hexagonal migration would mean ports over PostgreSQL, pgvector, Celery, MLflow, model serving, LangGraph, and retrieval. This change **requires none of them**, and proposes none of them. Where the brief's longer-term ambitions (tenant database, tenant vector store) would eventually need such seams, §11.1 shows they remain reachable through existing choke points and are made no harder by this work.

Three ports, one extracted module, one thinned route, one additive migration, and four small pipeline fixes — three of which are defect fixes the platform needs regardless.

---

## 16. Open decisions requiring approval before implementation

| ID | Decision | Recommendation |
|---|---|---|
| **OD-N1** | `DocumentSource` (brief) versus `SourceConnector` (EDS) as the pull-port name | `DocumentSource` — the brief is the newer intent; update EDS |
| **OD-N2** | `document_sources` versus EDS's `data_sources` for the configured-connection table | `document_sources` — Path B connectors are also "data sources"; the narrower name stays true |
| **OD-N3** | Does `retention_mode` exist as a column, or is retention inferred from `storage_reference IS NULL`? | Explicit column — inference makes a policy indistinguishable from a failure |
| **OD-N4** | Is `DocumentContent` re-openable (§9.3)? | Yes. Without it, retention is de-facto mandatory |
| **OD-N5** | Fix the `002`/`003` column drift (`mime_type`/`file_size_bytes` versus `content_type`/`file_size`) in this change, or file it separately? | Fix here, as its own task — this change makes `content_type` authoritative while `sql_generator.py:24` still advertises `mime_type` to the LLM |
| **OD-N6** | Actor attribution for non-human ingestion, and the portal visibility rule (C4 / EDS OD-9) | Make non-upload documents visible tenant-wide; align the list filter with what retrieval already does |
| — | Inherited and still open: EDS OD-1 (disappearance), OD-2 (content dedup), OD-5 (auto-extraction) | Block phases 4+, not phases 1–3 |

---

## 17. Summary

Documents enter this platform through exactly one door, and that door is a FastAPI route that also happens to be the ingestion use case, the storage client, the persistence layer, and the job dispatcher. Everything downstream of it is already source-agnostic.

The proposal is three ports and nothing else: **`DocumentIngestionService`** (the application use case every adapter calls), **`DocumentContent`** (re-openable byte access supplied by the adapter), and **`OriginalDocumentStore`** (where originals go, if anywhere). Platform upload becomes the first adapter over that port, with a real `source_id` rather than a NULL. The pull-side `DocumentSource` port is specified but deliberately not built, because upload cannot implement it honestly and building it now would shape it around a provider that does not exist yet.

Two decisions carry the privacy requirement, and both must be made in phase 1 even though only one adapter exists: **`storage_reference` becomes an outcome that may legitimately be NULL**, and **nothing downstream may parse it** — which means `ocr_worker.py:197` must stop selecting the OCR branch by splitting a MinIO object key. Without those two, "do not copy this tenant's documents into platform MinIO" is not a configuration value, it is a fork of the pipeline.

Relational and vector storage get **no port**, now or in this plan. They stay reachable through the `_schema(tenant_id)` plus `get_engine()` choke point and through `retriever.py`, and they are made no harder by this change. Path B — direct structured query against a tenant database — is a retrieval tool, not a document source, and shares nothing with this seam but the safety discipline already present in `sql_generator`.

Nothing here has been implemented. No code changed, no migration created, no OpenSpec change opened.
