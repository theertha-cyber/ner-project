# External Data Source Architecture

> **Status:** Architecture / Design (no code written, no migrations created, no connector implemented)
> **Scope:** Provider-agnostic external document ingestion. Keka is the first provider; the architecture must not be shaped by Keka alone.
> **Evidence convention:** `Confirmed` = verified in this repo's code/migrations, or established in `docs/integrations/keka-research.md` as Confirmed. `Inferred` = reasoned from confirmed facts. `Open Decision` = requires human/product approval before implementation. `Unknown` = not established; needs verification.
> **Authoritative inputs:** `external-data-source-ingestion-source-of-truth.md`, `docs/integrations/keka-research.md`, the existing codebase.
> **Precedence:** ADR > PROJECT.md > AGENTS.md > docs/ (per `AGENTS.md` §4). This document is a `docs/` artifact and yields to all three.

---

## 1. Problem

Documents enter the platform through exactly one door: `POST /api/v1/documents`, a multipart upload handled inline in `src/document_service/api/v1/documents.py:50`. That handler validates the file, hashes it, writes it to MinIO, inserts a `tenant_{tid}.documents` row, and fires OCR. Everything downstream — OCR, text spans, chunking, embeddings, extraction, RAG — hangs off that single row. `Confirmed`

There is no concept of a document that the platform fetched rather than received. Specifically: `Confirmed`

| Missing capability | Evidence |
|---|---|
| No external source identity on documents | `tenant_template.documents` has `id, tenant_id, filename, mime_type, file_size_bytes, checksum, storage_uri, status, ocr_applied_flag, error_message, created_at` (migration `002`) plus `content_type, file_size, blob_path, updated_at` (`003`), `purpose` (`022`), `uploaded_by` (`030`). No `source_id`, no `external_id`, no source timestamps. |
| No connector layer | No provider/connector/sync symbols anywhere in `src/`. |
| No synchronization state | No cursor, no run history, no per-document sync outcome. |
| No scheduler | `grep beat_schedule\|crontab\|periodic src/` returns nothing. Celery exists (training, extraction) but nothing periodic. |
| No system-initiated ingestion path | The only ingest path requires an `UploadFile` and a request-scoped JWT. |

The task is to add external sources **without** giving each provider its own path through the platform, and without the extraction/RAG layers ever learning that providers exist.

---

## 2. Architectural Goals

1. **One document pipeline.** An externally fetched document and a user-uploaded document become the same `documents` row and take the identical downstream path.
2. **Provider knowledge stops at the connector.** No Keka concept — employee, attachment, subdomain, `kekaapi` scope — appears in the ingestion engine, document service, extraction service, or RAG layer.
3. **No capability assumptions.** The generic layer must work for a provider with no timestamps, no versions, no webhooks, and no deletion signal, because that is exactly what Keka is. Providers that have more must be able to use it without the engine special-casing them.
4. **Tenant isolation by construction, not by discipline.** A connector instance must be structurally incapable of reaching another tenant's credentials or data.
5. **Resume-safe and idempotent.** A sync that crashes mid-run resumes; a sync of unchanged content does no work and creates no rows.
6. **Operationally legible.** An administrator can answer "is this source working, when did it last sync, what did it do, what failed" from persisted state.
7. **Smallest coherent footprint.** New tables and one new worker — not a new microservice.

---

## 3. Non-Goals

- Implementing the Keka connector (this document defines its boundary only).
- Any UI. The source-of-truth doc is explicit that UI comes after reliable sync state exists.
- Write-back to providers (`POST /hris/employees/documents` exists but is out of scope). `Confirmed`
- Using Keka MCP as a production surface. Research settled this: MCP is a research/dev tool. `Confirmed`
- Replacing or redesigning OCR, chunking, embeddings, extraction, or RAG.
- Document versioning/history as a product feature (see §13 and §24).
- Multi-provider rollout. One connector, validated, then reuse.

---

## 4. Existing Pipeline

All `Confirmed` from code.

```
POST /api/v1/documents (multipart, JWT)
  │  documents.py:50 — role/purpose gate, extension allowlist, 50MB cap
  │  compute_content_hash(bytes)                     content_hash.py
  │  advisory duplicate lookup by checksum           documents.py:98
  │  MinioStorageClient.upload_file()                storage.py:32
  │      key = tenants/{tenant_id}/documents/{doc_id}.{ext}
  │  INSERT tenant_{tid}.documents (status='pending')
  │  trigger_ocr()                                   ocr_worker.py:228
  ▼
process_document()                                   ocr_worker.py:117
  │  status → 'processing'
  │  PyMuPDF text, falling back to pdf2image+Tesseract; Tesseract for images
  │  INSERT document_text_spans
  │  status → 'processed'
  │  if purpose == 'query':  chunk → embed → INSERT document_chunks
  ▼
Extraction (explicitly triggered, never automatic)
  │  POST /api/v1/extract-batch                      extraction.py:129
  │  eligibility: status='processed' AND purpose='query'   extraction.py:155
  │  Celery task run_batch_extraction, queue 'extraction'  worker.py:181
  │  already-extracted skip keyed on model_version
  ▼
RAG   retriever.py:70,111 — dense+sparse over document_chunks WHERE purpose='query'
```

Facts that materially constrain the design:

| Fact | Location | Consequence |
|---|---|---|
| The upload route **is** the ingestion service. There is no reusable ingest function. | `documents.py:50-142` | An ingestion seam must be extracted before anything can reuse it. |
| OCR is dispatched with `asyncio.create_task`, in the API process | `ocr_worker.py:228` | Fire-and-forget, lost on restart, unbounded concurrency. Acceptable for human-paced uploads; not for a 2,000-document backfill. |
| `process_document` sets `status='processing'` unconditionally and inserts spans without deleting prior spans | `ocr_worker.py:133,167` | Running it twice on one document **duplicates text spans**. Any at-least-once dispatch or any re-ingest-on-change needs a guard. |
| Only `purpose='query'` documents are chunked/embedded, and only those are extraction-eligible | `ocr_worker.py:191`, `extraction.py:155` | `purpose` is the switch that decides whether an external document ever reaches RAG or extraction. |
| Checksum dedup is **advisory** — returns `duplicate_of`, never rejects or merges | `documents.py:94-108` | Existing semantics are "identify, don't merge". External ingestion must decide deliberately whether to keep that (see §12). |
| Tenant schemas are cloned from `tenant_template` with `CREATE TABLE … (LIKE … INCLUDING DEFAULTS INCLUDING CONSTRAINTS INCLUDING INDEXES INCLUDING GENERATED)` | `tenant_service.py:52-60` | `LIKE` does **not** copy foreign keys. Per-tenant tables have no FKs regardless of what the template declares. No design may rely on FK cascade. |
| Schema-change pattern: alter `tenant_template`, then `DO $$` loop over `tenant\_%` schemas | migrations `030`, `034` | Every new tenant-scoped table follows this or existing tenants silently lack it. |
| `create_service_token(tenant_id, ttl)` already exists for user-less server-to-server calls | `auth.py:60` | System-initiated ingestion needs no new auth primitive. |
| `list_documents` filters `uploaded_by = :user_id` for any role other than `tenant_admin` | `documents.py:161` | External documents (no uploader) will be invisible to `business_user` in the list — while still retrievable by RAG, which filters only on `purpose='query'` (`retriever.py:70`). A visibility inconsistency, flagged in §24. |
| Deleting a document hard-deletes chunks/spans/entities and soft-deletes the row (`status='deleted'`) | `documents.py:275-312` | An existing soft-delete convention already exists; deletion handling should align to it rather than invent a state. |
| Retry defaults are `0.5s → ×2 → 10s`, 30s total | `config.py` | Far shorter than Keka's 60-second rate-limit refill. Reusing these for a connector would burn the budget and give up. |
| Deployed processes | `docker-compose.yml` | gateway, chat_api, document_service, extraction_service, model_serving, annotation_service, training_service, analytics_service, portal, `celery_worker` (training), `celery_worker_extraction`. No beat scheduler. |

---

## 5. Proposed Architecture

```
                        ┌───────────────────────────────────────┐
   scheduler (beat) ───▶ │        Sync Engine (generic)          │
   manual trigger  ───▶ │  lease → discover → decide → fetch     │
                        │  → ingest → record → reconcile         │
                        └───────┬─────────────────────┬─────────┘
                                │                     │
                  ConnectorContext                    │ IngestRequest
                  (tenant-bound, no DB)               │
                                ▼                     ▼
                     ┌────────────────────┐   ┌───────────────────────┐
                     │ SourceConnector    │   │ document_service      │
                     │  (provider code)   │   │  ingest_document()    │
                     │  discover()        │   │   hash → MinIO → row  │
                     │  fetch()           │   │   → dispatch OCR      │
                     │  check_connection()│   └───────────┬───────────┘
                     └─────────┬──────────┘               │
                               │ HTTP                     ▼
                          Provider API            existing pipeline
                                                  OCR → spans → chunks
                                                  → extraction → RAG
```

Three boundaries carry the whole design:

**Boundary 1 — Connector ⇄ Engine.** The connector answers two questions: *what exists over there* (`discover`) and *give me these bytes* (`fetch`). It owns authentication, pagination, rate limiting, provider error mapping, and identity construction. It holds no database session and no storage client. `Inferred` — this is the design choice, and it is what makes provider isolation structural rather than conventional.

**Boundary 2 — Engine ⇄ Ingestion.** The engine hands the document service `(tenant_id, filename, bytes, content_type, purpose, origin, source_id, external_id)` and gets back a `document_id`. It does not write to `documents`, MinIO, or any derived table itself.

**Boundary 3 — Ingestion ⇄ Pipeline.** Unchanged. The `documents` row is the pipeline's entry contract and stays so.

Deliberately **not** in the design:

- No `sync()` method on the connector. If each connector implemented its own sync, each would reimplement checkpointing, idempotency, and failure isolation — differently, and wrongly. Sync is one algorithm parameterised by capabilities.
- No provider-specific tables. `data_sources`, `sync_runs`, `external_documents`, `sync_run_errors` have no provider columns beyond a `provider` discriminator and an opaque JSONB.
- No second extraction or RAG path.

---

## 6. Domain Model

Four new tenant-scoped tables. Placement in `tenant_{tid}` (not `public`) follows ADR-001 and matches `documents`: isolation by schema is enforced by construction, whereas a `public` table with a `tenant_id` column is enforced by every author remembering a `WHERE` clause. `Inferred`

Trade-off accepted: the scheduler cannot do one global query for due sources. It enumerates `public.tenants` (which already exists) and fans out per tenant. Cost is bounded by tenant count, not document count. `Inferred`

### 6.1 `data_sources` — the configured connection

| Field | Type | Notes |
|---|---|---|
| `id` | VARCHAR PK | |
| `tenant_id` | VARCHAR NOT NULL | Redundant with the schema; kept for parity with `documents`. |
| `provider` | VARCHAR(50) NOT NULL | `'keka'`. Discriminator that selects the connector from the registry. The **only** provider-aware column in the generic schema. |
| `display_name` | VARCHAR(255) | Administrator-facing. |
| `status` | VARCHAR(20) | `pending_verification` \| `active` \| `paused` \| `error` \| `disabled` |
| `config` | JSONB NOT NULL | **Non-secret** provider connection metadata and ingestion options: base URL/subdomain, document-type filter, employment-status filter, page size. Shape validated by the connector, opaque to the engine. |
| `credential_ref` | VARCHAR(255) NOT NULL | **Locator, never a secret.** See §14. |
| `sync_enabled` | BOOLEAN | |
| `sync_interval_minutes` | INTEGER | |
| `ingest_purpose` | VARCHAR(20) | `query` (default) \| `training`. Decides whether ingested documents reach RAG and extraction (`ocr_worker.py:191`). |
| `extraction_policy` | VARCHAR(20) | `manual` (default) \| `automatic`. See §5/§18 and Open Decision OD-5. |
| `deletion_policy` | VARCHAR(20) | `flag_only` (default) \| `archive` \| `soft_delete`. See §13. |
| `last_successful_sync_at` | TIMESTAMPTZ | Denormalised for cheap status display. |
| `last_sync_run_id` | VARCHAR | Denormalised. |
| `created_by`, `created_at`, `updated_at` | | |

Lifecycle: `pending_verification → active → (paused | error) → disabled`. Created by a tenant admin; verified by a `check_connection()` call before it is allowed to become `active`. `Inferred`

**Sync state does not live here** — only *derived summary* fields do. The authoritative state is on `sync_runs` (per attempt) and `external_documents` (per object). Answering §1's question directly: synchronization state belongs to the **sync run** for progress and to the **external document** for identity; it belongs to the data source only as a cached summary, and to the connector never — connectors are stateless between calls, which is what makes them retry-safe. `Inferred`

### 6.2 `sync_runs` — one row per synchronization attempt

| Field | Type | Notes |
|---|---|---|
| `id`, `tenant_id`, `source_id` | | |
| `trigger` | VARCHAR(20) | `scheduled` \| `manual` \| `event` (future webhook) |
| `mode` | VARCHAR(20) | `full` \| `incremental`. `full` == "engine passes `cursor=None`". |
| `status` | VARCHAR(20) | `pending` \| `running` \| `completed` \| `partially_failed` \| `failed` \| `interrupted` \| `cancelled` |
| `started_at`, `completed_at` | TIMESTAMPTZ | |
| `heartbeat_at` | TIMESTAMPTZ | Liveness for the stale-run reaper (§12). |
| `cursor_start`, `cursor_end` | JSONB | Opaque connector checkpoints. The engine persists and replays them; it never reads inside. |
| `discovered_count` | INTEGER | Refs yielded by discovery. |
| `unchanged_count` | INTEGER | Identity known, content identical. No work done. |
| `ingested_count` | INTEGER | New external identities ingested. |
| `updated_count` | INTEGER | Known identity, content changed, re-ingested. |
| `failed_count` | INTEGER | Item-level failures. |
| `missing_count` | INTEGER | Previously seen, absent from a complete enumeration (§13). |
| `error_code`, `error_summary` | VARCHAR / TEXT | Run-level termination reason. Provider-neutral code plus human text. |

Lifecycle: `pending → running → {completed, partially_failed, failed, interrupted, cancelled}`. Terminal states are never re-entered; a resume creates a **new run** that inherits `cursor_end` from the previous one. `Inferred`

### 6.3 `external_documents` — the identity ledger

The most important table. It is what the source-of-truth doc's `ExternalDocument` becomes once persisted.

| Field | Type | Notes |
|---|---|---|
| `id` | VARCHAR PK | |
| `tenant_id`, `source_id` | | |
| `external_id` | VARCHAR(512) NOT NULL | **Opaque.** Connector-generated. Never parsed by the engine. |
| `partition_key` | VARCHAR(255) NULL | Opaque enumeration-scope token (§13). Keka: employee id. Engine compares for equality only. |
| `document_id` | VARCHAR NULL | The `documents` row this currently maps to. NULL while discovered-but-not-ingested or permanently failed. |
| `checksum` | VARCHAR(64) NULL | SHA-256 of the last successfully ingested bytes. The content-change boundary. |
| `external_version` | VARCHAR(255) NULL | Opaque provider version token (ETag, revision, hash) when the provider has one. NULL for Keka. |
| `filename` | VARCHAR(255) | Last observed name. Metadata, not identity. |
| `content_type` | VARCHAR(255) | As resolved by the connector. |
| `size_bytes` | BIGINT NULL | |
| `source_created_at` | TIMESTAMPTZ NULL | Nullable **by design** — Keka exposes none. |
| `source_modified_at` | TIMESTAMPTZ NULL | Nullable by design. Never synthesised from wall-clock (see §8). |
| `state` | VARCHAR(20) | `discovered` \| `ingested` \| `failed` \| `missing` \| `archived` |
| `first_seen_at`, `last_seen_at` | TIMESTAMPTZ | `last_seen_at` drives reconciliation-based deletion. |
| `last_synced_run_id` | VARCHAR | |
| `failure_count`, `failure_code`, `failure_message` | | Item-level durable failure state. |
| `provider_metadata` | JSONB | Provider-specific extras. Opaque. Never read by the engine or anything downstream. |

**Unique constraint: `(source_id, external_id)`.** `Confirmed` as the right boundary — it is the only key that survives filename changes, content changes, and re-discovery.

**Why a separate table instead of `source_id`/`external_id` columns on `documents`** (the research doc's recommendation, deliberately revisited):

1. An external document exists before a `documents` row does — discovered, download failed, retrying. Columns on `documents` cannot represent that state without inventing phantom document rows.
2. `documents` is soft-deleted (`status='deleted'`, `documents.py:307`). A unique index on `documents(source_id, external_id)` would permanently block re-ingesting an external object after a delete.
3. Sync bookkeeping (`last_seen_at`, `failure_count`, `partition_key`, provider metadata) is not document metadata. Putting it on `documents` pollutes the table every other service reads.
4. Content-addressed reuse (§12) makes the relationship many-to-one: several external identities can legitimately map to one `documents` row.

`documents` still gets two thin, additive columns — `origin` (`'upload'` \| `'external'`, default `'upload'`) and `source_id` (NULL for uploads) — purely so the portal and existing list queries can filter and attribute without joining. Provenance lives on `documents`; identity and sync state live on `external_documents`. `Inferred`

### 6.4 `sync_run_errors` — failure detail

| Field | Notes |
|---|---|
| `id`, `tenant_id`, `run_id`, `source_id` | |
| `external_id` | NULL for run-level errors. |
| `phase` | `auth` \| `discovery` \| `fetch` \| `ingest` \| `reconcile` |
| `error_code` | Provider-neutral: `AUTH_FAILED`, `RATE_LIMITED`, `PROVIDER_UNAVAILABLE`, `ITEM_UNAVAILABLE`, `UNSUPPORTED_CONTENT`, `TOO_LARGE`, `INGEST_FAILED`, `INTERNAL` |
| `error_message` | Sanitised. Never contains credentials or raw provider payloads. |
| `attempt`, `occurred_at` | |

**No per-run, per-document success table.** A `sync_run_items` table would be O(runs × documents) — a 2,000-document source syncing hourly writes ~48M rows/year to say "unchanged". Current per-document state lives on `external_documents`; only failures get their own rows. Trade-off: no per-run historical audit of which specific documents were unchanged. Accepted; the counters carry that. `Inferred`

### 6.5 Entities that were evaluated and rejected

| Candidate | Verdict |
|---|---|
| `SyncState` as its own table | Rejected. Cursor belongs on `sync_runs` (per-attempt, resumable); summary belongs on `data_sources`. A third table would need synchronising with both. |
| `ExternalDocumentIdentity` as a separate entity | Rejected. `(source_id, external_id)` on `external_documents` *is* the identity. Splitting it adds a join and no invariant. |
| `Provider` / `ProviderRegistry` table | Rejected. Providers are code, not data. A registry row cannot make a connector exist. In-code registry keyed by the `provider` string. |
| `Employee` / subject entity | Rejected as generic. Keka-specific. Lives in `partition_key` (opaque) and `provider_metadata`. See OD-6. |

---

## 7. Connector Contract

```python
# src/external_ingestion/contracts.py   (illustrative — not implementation)

@dataclass(frozen=True)
class ConnectorCapabilities:
    change_detection: Literal["version", "source_timestamp", "content_hash"]
    deletion_signal:  Literal["events", "reconciliation", "none"]
    supports_incremental: bool
    supports_event_ingest: bool = False
    max_requests_per_minute: int | None = None

@dataclass(frozen=True)
class ConnectorContext:
    tenant_id: str
    source_id: str
    config: Mapping[str, Any]
    credentials: Mapping[str, str]   # already resolved, already tenant-bound
    run_id: str
    deadline: datetime | None

@dataclass(frozen=True)
class ExternalDocumentRef:            # discovery output — metadata only, no bytes
    external_id: str
    filename: str
    partition_key: str | None = None
    external_version: str | None = None
    source_modified_at: datetime | None = None
    source_created_at: datetime | None = None
    size_bytes: int | None = None
    content_type: str | None = None
    deleted: bool = False             # only meaningful when deletion_signal == "events"
    provider_metadata: Mapping[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class DiscoveryBatch:
    refs: Sequence[ExternalDocumentRef]
    cursor: Mapping[str, Any] | None  # opaque; engine persists verbatim
    enumeration_complete_for: Sequence[str] = ()   # partition_keys fully enumerated

@dataclass(frozen=True)
class FetchedContent:
    content: bytes
    content_type: str
    filename: str
    external_version: str | None = None

class SourceConnector(Protocol):
    provider: ClassVar[str]
    capabilities: ClassVar[ConnectorCapabilities]

    async def check_connection(self, ctx: ConnectorContext) -> ConnectionStatus: ...
    def discover(self, ctx: ConnectorContext,
                 cursor: Mapping[str, Any] | None) -> AsyncIterator[DiscoveryBatch]: ...
    async def fetch(self, ctx: ConnectorContext,
                    ref: ExternalDocumentRef) -> FetchedContent: ...
```

Three methods. Each of the capabilities the brief listed maps onto them without a dedicated method:

| Required capability | Where it lives | Why not its own method |
|---|---|---|
| authenticate | Inside the connector, triggered lazily by `discover`/`fetch`; surfaced only through `check_connection` and `AuthenticationError` | A public `authenticate()` invites the engine to sequence auth, which differs per provider (OAuth client-credentials, refresh, API key, mTLS). Tokens are in-memory and per-context; nothing outside the connector may hold one. |
| discovery | `discover()` | |
| pagination | Inside `discover()`, expressed as successive batches | Page numbers vs. continuation tokens vs. delta tokens are not a shared shape. Keka alone uses both (`pageNumber` for lists, `continuationToken` for retry logs). `Confirmed` |
| retrieval | `fetch()` | |
| identity | `ExternalDocumentRef.external_id`, constructed by the connector | |
| change detection | `capabilities.change_detection` + optional `external_version` / `source_modified_at` on the ref | Declared as a capability, applied by the engine's ladder (§10). |
| synchronization | **Engine, not connector** | The single most important boundary choice. See §5. |
| provider errors | Typed exception hierarchy the connector raises | |
| retry | Split: transport retry in the connector, item/run retry in the engine (§16) | |

`cursor=None` means "enumerate everything" — this is how the engine requests a full sync without a `mode` parameter on the interface. A connector with no incremental capability ignores the cursor entirely and always enumerates. `Inferred`

**Connector invariants** (enforceable in review, and by the fact that nothing else is injected):

1. A connector receives no database session, no storage client, and no `tenant_id`-free code path.
2. A connector is stateless across calls except for an in-memory auth token scoped to one `ConnectorContext`.
3. A connector never raises a raw HTTP/library exception across the boundary — everything maps to `ConnectorError` subtypes.
4. A connector never persists anything.

**Error taxonomy** (generic, in `src/external_ingestion/errors.py`):

```
ConnectorError
├── ConfigurationError      — malformed config; run fails, source → 'error', no retry
├── AuthenticationError     — bad/expired/revoked credentials; run fails fast
├── AuthorizationError      — authenticated but lacking scope/privilege
├── RateLimitError          — carries retry_after; engine yields
├── TransientProviderError  — 5xx, timeouts, connection resets; retryable
├── PermanentProviderError  — 4xx that will not resolve by retrying
└── ItemUnavailableError    — this one object failed; run continues
```

---

## 8. ExternalDocument Contract

The source-of-truth doc proposes `source_id, external_id, filename, content, content_type, modified_at, checksum`. Evaluated against Keka, it is **not sufficient**, and one of its fields is actively harmful.

### 8.1 Required — generic contract

| Field | Phase | Why it must exist |
|---|---|---|
| `external_id` | discovery | Identity. Nothing works without it. Must be derivable *before* download, or change detection cannot avoid downloads. |
| `filename` | discovery | Drives the extension → the storage key (`storage.py:33`), the allowlist check (`ocr_worker.py:56`), and the OCR branch (`ocr_worker.py:154`). |
| `content` | fetch | The bytes. |
| `content_type` | fetch | The pipeline requires it; Keka never supplies it, so the **connector** must resolve it (extension mapping) rather than the engine guessing. Confirmed absent in Keka. |
| `checksum` | computed by the engine | See 8.4. |

`source_id` is deliberately **not** on the connector-facing contract: the engine already knows which source it is running, and letting the connector state it invites mismatch. It is stamped by the engine on persist.

### 8.2 Optional generic metadata (nullable, never required)

| Field | Rationale | Keka |
|---|---|---|
| `external_version` | Cheapest possible change detection when a provider has one. | NULL |
| `source_modified_at` | Second-cheapest change detection. | NULL — `Confirmed` absent from `EmployeeDocumentDto` |
| `source_created_at` | Provenance and display only. | NULL |
| `size_bytes` | Pre-download size gate against the 50MB cap. | NULL |
| `partition_key` | Scope token for reconciliation-based deletion (§13). | employee id |
| `deleted` | Only meaningful for `deletion_signal == "events"`. | unused |

**`modified_at` must be nullable, and must never be defaulted to sync time.** The research doc proposes `modified_at = sync_time` as a fallback. Rejected: a timestamp that changes on every sync is indistinguishable from a genuine modification, so it is worse than NULL — it would defeat the very comparison the field exists for, and it silently converts "we don't know" into "it changed just now". NULL is honest and forces the change-detection ladder (§10) to fall through to checksum, which is the correct behaviour. `Inferred` — this is a deliberate deviation from the research recommendation.

### 8.3 Provider-specific metadata

Everything else goes in `provider_metadata` JSONB: Keka's `documentId`, `employeeId`, `attachmentId`, `documentTypeId`, custom `attributes[]`. Written by the connector, stored by the engine, read by **nothing** in the generic layer. Its only legitimate consumers are the connector itself (on a later run) and troubleshooting.

Deliberately **not** promoted to generic columns: employee association, document type. Both are HR-domain concepts. Promoting them would be the clearest possible instance of Keka leaking into the generic model. See OD-6 if per-employee filtering becomes a product requirement.

### 8.4 Checksum — who computes it

The **engine** computes SHA-256 over the fetched bytes using the existing `compute_content_hash` (`content_hash.py`), the same function the upload path uses. One algorithm, one authority, and external documents become directly comparable with uploaded ones. `Confirmed` reusable.

A provider-supplied hash, when one exists, is a *hint* and belongs in `external_version` — not in `checksum`, because it may use a different algorithm, cover different bytes, or be a revision counter.

### 8.5 Content transfer

`fetch()` returns `bytes`. The platform already caps documents at 50MB (`documents.py:81`), so full-buffering is bounded and matches existing behaviour. Streaming is a later optimisation that changes the connector signature only. `Inferred`

---

## 9. DataSource Lifecycle

```
   (admin creates)
        │
        ▼
 pending_verification ──check_connection fails──▶ error
        │                                          │
   check_connection ok                        (admin fixes creds/config)
        │                                          │
        ▼                                          ▼
      active ◀──────────── resume ──────────── paused
        │  │                                       ▲
        │  └── auth/config failure ──▶ error ──────┘
        │
   admin disables
        ▼
    disabled   (no scheduling; state and documents retained)
```

- `active` is the only state the scheduler picks up, and only when `sync_enabled` is true.
- `error` is set by the engine on `AuthenticationError`, `AuthorizationError`, or `ConfigurationError` — failures that will not resolve by waiting. Transient and rate-limit failures leave the source `active` and mark the *run*, not the source.
- Deleting a data source is **not** modelled as a cascade. Removing a source must not delete tenant documents. Recommended: `disabled` + retained `external_documents` rows. Deleting the ingested documents is a separate, explicit administrator action. `Open Decision` — OD-4.
- `data_sources` has no FK to anything (the `LIKE` clone drops FKs anyway, `tenant_service.py:58`), so referential integrity is application-enforced. `Confirmed`

---

## 10. Synchronization Model

### 10.1 The generic algorithm

```
1. LEASE      insert sync_runs(status='running'); the partial unique index (§12)
              rejects a second concurrent run for the same source.
2. RESOLVE    credentials ← CredentialProvider.resolve(tenant_id, credential_ref)
              ctx ← ConnectorContext(tenant_id, source_id, config, credentials, run_id)
3. VERIFY     connector.check_connection(ctx)   → AuthenticationError ends the run fast
4. DISCOVER   for batch in connector.discover(ctx, cursor):
5.   DECIDE     for ref in batch.refs:   change-detection ladder ↓
6.   FETCH      only when the ladder says "unknown" or "changed"
7.   INGEST     document_service.ingest_document(...) in one transaction with the
                external_documents upsert; OCR dispatched after commit
8.   RECORD     counters; failures → sync_run_errors, external_documents.state='failed'
9.   CHECKPOINT persist batch.cursor + heartbeat_at  ← the resume point
10. RECONCILE if capabilities.deletion_signal == 'reconciliation' and the run
              enumerated completely: sweep last_seen_at (§13)
11. FINALIZE  status ← completed | partially_failed | failed; update data_sources summary
```

### 10.2 Change-detection ladder

Applied per ref, in order, stopping at the first rung the provider supports:

| Rung | Condition | Cost | Providers |
|---|---|---|---|
| 0 | No `external_documents` row for `(source_id, external_id)` | — | **new**, always fetch |
| 1 | `capabilities.change_detection == "version"` and `ref.external_version == stored.external_version` | zero downloads | delta/ETag providers |
| 2 | `change_detection == "source_timestamp"` and `ref.source_modified_at <= stored.source_modified_at` | zero downloads | timestamped providers |
| 3 | Fetch, compute SHA-256, compare with `stored.checksum` | one download | **Keka**, and any provider whose rungs 1–2 are NULL |

Keka lands on rung 3 with no special-casing anywhere in the engine — because rungs 1 and 2 are guarded on nullable capability declarations, not assumed. This is the direct answer to "have we assumed every provider has timestamps": the ladder is written so that the *absence* of both is a supported configuration, not a degraded one.

### 10.3 Provider strategies the model must (and does) accommodate

| Provider shape | How it uses the contract |
|---|---|
| **Keka** (no doc timestamp, no delta, no webhook) | `discover` uses employee `lastModified` to choose which employees to list, packs its progress into the opaque cursor, yields refs per employee, marks each fully-listed employee in `enumeration_complete_for`. Engine sees only refs + cursor. |
| **Delta-API provider** | `discover` treats the cursor as a delta token; `enumeration_complete_for` is empty on incremental runs; engine schedules periodic `cursor=None` runs for reconciliation. |
| **Webhook + reconciliation** | Event ingress creates a `trigger='event'` run with a scoped hint; the same engine loop runs. Requires `supports_event_ingest`. Future. |
| **Full-scan provider** | Ignores the cursor; every run enumerates completely; reconciliation available every run. |

None of these requires an engine change. That is the test the abstraction has to pass.

### 10.4 The Keka cost problem this model exposes

Rung 3 means: to detect a change, every attachment must be downloaded, every sync. The research doc's own arithmetic — a 500-employee tenant with ~2,000 attachments against 50 requests/minute/endpoint — makes an exhaustive content check take **~80 minutes of pure rate-limited request time** (2,000 attachment-URL calls + 2,000 downloads, at best 50/min on the URL endpoint). Hourly full checks are not viable. `Inferred` from confirmed limits.

Consequence, which the research did not state: the architecture needs two run intensities.

- **Shallow run** (frequent): discover, ingest genuinely new `external_id`s, do **not** re-fetch known ones. Catches additions — which for HR documents is the dominant change mode.
- **Deep run** (infrequent, e.g. nightly/weekly): apply rung 3 to known documents; also the only run that can reconcile deletions.

Expressed generically as `data_sources.deep_check_interval_minutes` and a per-run flag, not as a Keka setting. Providers on rungs 1–2 set it to zero because every run is already cheap. `Inferred` — cadence values are `Open Decision` OD-7.

---

## 11. Sync State and Runs

The three levels the brief asks about, kept deliberately separate:

| Level | Table | Answers | Cardinality |
|---|---|---|---|
| Source | `data_sources` | Is it configured? Is it enabled? Is it healthy? When did it last succeed? | 1 per source |
| Run | `sync_runs` | What happened on this attempt? Where did it get to? What are the counts? Why did it stop? | 1 per attempt |
| Document | `external_documents` (+ `sync_run_errors` for failures) | What is this external object's current identity, content hash, mapped document, and state? | 1 per external object |

Collapsing any two loses something concrete: merging source and run destroys history (no "recent synchronizations" list); merging run and document either creates the O(runs × documents) table rejected in §6.4 or loses per-document current state on the next run.

The brief's questions map directly:

| Question | Answered by |
|---|---|
| What source is being synchronized? | `sync_runs.source_id` where `status='running'` |
| When did the sync start? | `sync_runs.started_at` |
| What is happening now? | `sync_runs.status` + `heartbeat_at` + live counters |
| Last successful sync? | `data_sources.last_successful_sync_at`; authoritative: latest `sync_runs` with `status='completed'` |
| What cursor exists? | `sync_runs.cursor_end` of the latest run |
| Discovered / ingested / unchanged / updated / failed | `sync_runs.*_count` |
| Why did they fail? | `sync_run_errors` joined to `external_documents.external_id` |

Counters are incremented in the same transaction that records the item outcome, so they cannot drift from `external_documents` even if the run dies mid-batch. `Inferred`

---

## 12. Identity and Idempotency

### 12.1 The Keka composite identity

`{employeeId}:{documentId}:{attachmentId}` — **appropriate**, on four grounds: it is stable, unique within the source, derivable at discovery without downloading, and it identifies the *attachment*, which is the thing that actually becomes a file. `Confirmed` that a Keka document may carry multiple attachments.

It is constructed **inside the Keka connector**. The engine treats it as an opaque string: never split, never parsed, never pattern-matched. The only property the engine relies on is equality.

Consequence to accept: the identity is a Keka-defined format, so if Keka ever changes employee or document ids, identities break and documents re-ingest as new. Mitigation is not available at the architecture level; it is a provider risk. `Inferred`

### 12.2 Uniqueness

`UNIQUE (source_id, external_id)` on `external_documents`, within the tenant schema. Tenant isolation is already structural (separate schema), so tenant does not need to be in the key — but `tenant_id` is stored for parity and for defensive `WHERE` clauses.

### 12.3 Identity vs. checksum — two different questions

| Key | Question it answers | Used for |
|---|---|---|
| `(source_id, external_id)` | "Is this the same external object?" | Deciding new vs. known; the idempotency boundary |
| `checksum` | "Are these the same bytes?" | Deciding changed vs. unchanged; content-level dedup |

Neither substitutes for the other. Same identity + different checksum = modified. Different identity + same checksum = duplicate content (see 12.6).

### 12.4 Filename changes

Filename is metadata. Same `external_id`, same checksum, new name → update `external_documents.filename` and `documents.filename`; no re-fetch beyond the one the ladder already required, no re-OCR, no re-embed, no re-extract. Counted as `unchanged`. `Inferred`

Edge case: if the *extension* changes (`.pdf` → `.png`) with identical bytes, the stored blob key and OCR branch would disagree with the new name. Rare; treat as a content change (re-ingest under a new blob key). Flagged rather than silently mishandled.

### 12.5 Content changes

New checksum for a known identity → **update in place**:

1. Upload new bytes to a **new** MinIO key (blob keys are per-`document_id`; a new object avoids read-during-rewrite races). `Inferred`
2. Delete derived rows for the document — `document_chunks`, `document_text_spans`, and extraction outputs — mirroring exactly what the existing delete endpoint already does (`documents.py:291-305`). **This is mandatory**, not optional: `process_document` inserts spans without deleting prior ones (`ocr_worker.py:167`), so re-OCR without a purge silently duplicates every span and every chunk.
3. Update the `documents` row (checksum, size, blob_path, filename, `status='pending'`), update `external_documents` (checksum, version, `last_synced_run_id`), re-dispatch OCR.
4. Extraction re-runs under the existing model-version skip logic, because its prior extraction rows are gone.

Alternative considered and rejected for v1: a new `documents` row per version with `superseded_by`. It preserves history and keeps chat citations pointing at the bytes that were actually cited — genuinely better — but it multiplies rows, requires every consumer to learn about supersession, and there is no product requirement for document history. `Open Decision` OD-3.

### 12.6 A document gains another attachment

New `attachmentId` → new `external_id` → rung 0 → ingested as a new document. No special case anywhere. This is the payoff for choosing attachment-level rather than document-level identity.

### 12.7 Content-addressed reuse (many identities → one document)

A realistic Keka case: one company policy PDF attached to 200 employees. Attachment-level identity gives 200 distinct `external_id`s with **one** checksum. Naively that is 200 storage objects, 200 OCR runs, 200 embedding batches, and 200 extraction jobs for identical text.

Recommended: when a fetched checksum matches an existing `documents` row in the same tenant that is not `status='deleted'`, point the new `external_documents` row at that existing `document_id` instead of creating a second document. Counted as `ingested` (new identity) with zero downstream work.

This **diverges from the existing upload behaviour**, which identifies duplicates but never merges them (`documents.py:94`). The divergence is defensible — uploads are human-paced and a user may legitimately want their own copy; sync is machine-paced and 200 copies are pure waste — but it changes what "delete this document" means when several external identities reference it. `Open Decision` OD-2. If rejected, the fallback is one document per identity, and the cost is real.

### 12.8 Concurrency invariants

| Invariant | Mechanism |
|---|---|
| At most one active run per source | `CREATE UNIQUE INDEX … ON sync_runs (source_id) WHERE status IN ('pending','running')`. Declarative, survives process restart, visible in state — unlike an advisory lock or an in-memory guard. |
| A crashed run does not block forever | `heartbeat_at` updated at each checkpoint; a reaper marks runs stale beyond a threshold as `interrupted`, freeing the slot. |
| No duplicate document rows for one identity | `UNIQUE (source_id, external_id)` + `INSERT … ON CONFLICT DO UPDATE`; the document row is only created inside the same transaction as the successful upsert. |
| No duplicate OCR | OCR dispatch happens **after** commit and is at-least-once, so `process_document` needs a guard: `UPDATE documents SET status='processing' WHERE id=:id AND status='pending' RETURNING id`, and return early on no row. Today the update is unconditional (`ocr_worker.py:133`). This is a small, required change to existing code. |
| No conflicting cursors | Only the run holding the lease writes `cursor_end`; a second run cannot exist to conflict. |
| No duplicate downloads within a run | Discovery yields each `external_id` once per run; the engine deduplicates within a batch defensively. |

### 12.9 What a second sync of an unchanged document does, exactly

1. `discover` yields the ref (one list API call, shared across many documents).
2. Engine looks up `(source_id, external_id)` → row exists, `state='ingested'`.
3. Ladder: rungs 1 and 2 are NULL for Keka → rung 3 → fetch bytes, compute SHA-256.
4. Hash equals `stored.checksum` → **stop**.
5. Writes: `external_documents.last_seen_at`, `last_synced_run_id`; `sync_runs.unchanged_count += 1`.
6. Does **not** write: MinIO, `documents`, `document_text_spans`, `document_chunks`, `extracted_entities`. Does not dispatch OCR or extraction.

On a shallow run (§10.4), step 3 is skipped entirely and the document is counted as unchanged without a download.

---

## 13. Deletion Handling

### 13.1 The three provider classes

| `deletion_signal` | Provider tells us | Engine behaviour |
|---|---|---|
| `events` | Explicit tombstones (`ref.deleted=True`) | Mark `state='missing'` immediately, deterministically. |
| `reconciliation` | Nothing, but discovery enumerates completely | After a **complete** enumeration, anything not seen is presumed gone. |
| `none` | Nothing, and enumeration is partial | Never infer deletion. Absence is not evidence. |

### 13.2 Reconciliation, scoped correctly

Reconciliation is only sound over a scope that was genuinely fully enumerated. An incremental Keka run visits only employees whose `lastModified` changed — a document belonging to an unvisited employee is absent from the run and is emphatically **not** deleted.

Mechanism: `DiscoveryBatch.enumeration_complete_for` carries opaque partition keys the connector fully enumerated. After a run that ended `completed` (not `partially_failed` — item failures make absence ambiguous), the engine sweeps:

```sql
UPDATE external_documents
   SET state = 'missing', missing_detected_at = now()
 WHERE source_id = :source_id
   AND partition_key = ANY(:completed_partitions)
   AND last_seen_at < :run_started_at
   AND state = 'ingested'
```

Keka's connector reports each employee it fully listed. A full run reports all of them, so a full run reconciles globally; an incremental run reconciles only within the employees it touched. Correct in both cases, with no employee concept in the engine — `partition_key` is compared for equality and never interpreted. `Inferred`

### 13.3 What happens to the document — the product decision

The architecture provides the mechanism and **does not choose the behaviour**. `data_sources.deletion_policy` selects among:

| Policy | Effect | Reversible | Notes |
|---|---|---|---|
| `flag_only` (proposed default) | `external_documents.state='missing'`; `documents` untouched; count surfaced on the run | Yes | Nothing disappears from RAG or extraction. Safest under a provider with no deletion signal. |
| `archive` | Additionally excludes the document from retrieval | Yes | Needs a retrieval-visible flag; `retriever.py:70,111` filters only on `purpose='query'`, so this requires a change to a query the RAG layer owns — the one place where deletion policy touches shared code. |
| `soft_delete` | Sets `documents.status='deleted'`, matching the existing delete endpoint | Partially — that endpoint hard-deletes chunks/spans/entities (`documents.py:291-305`) | Loses derived data; a document that reappears must be fully reprocessed. |
| `hard_delete` | Not offered | No | Deleting tenant data on inferred absence from a provider with no documented deletion signal is not a defensible default. |

**`Open Decision` OD-1 — the single most important product question in this document: what should the platform do when an external document disappears?** No existing product requirement answers it. The default is deliberately the least destructive option.

### 13.4 Reappearance

An object that reappears (`state='missing'` → seen again) returns to `ingested`, with the checksum ladder deciding whether its content also changed. No new identity, no duplicate document. `Inferred`

---

## 14. Credential Boundary

### 14.1 Three separate things

| Concept | Where it lives | Example |
|---|---|---|
| **Configuration** | `data_sources.config` JSONB — tenant-visible, editable, non-secret | page size, document-type filter, employment-status filter, `ingest_purpose` |
| **Connection metadata** | `data_sources.config` — identifies *which* provider tenant | Keka subdomain, `production` vs `sandbox` base URL |
| **Credentials** | **Never in the database.** `data_sources.credential_ref` holds a locator only | `client_id`, `client_secret`, `api_key`, and any issued token |

AGENTS.md invariant 3 forbids secrets in source, config files, or committed `.env`, and forbids default values for secret-class settings. Putting a Keka `client_secret` in a JSONB column would violate its spirit outright and would also expose secrets to every admin API that returns a data source. `Confirmed` (invariant) / `Inferred` (application).

### 14.2 The interface

```python
class CredentialProvider(Protocol):
    async def resolve(self, tenant_id: str, credential_ref: str) -> Mapping[str, str]: ...
```

- **v1: `EnvCredentialProvider`.** `credential_ref` like `env:keka_acme` resolves `NER_EXTSRC_KEKA_ACME_CLIENT_ID`, `…_CLIENT_SECRET`, `…_API_KEY`. Env-only, no defaults, per AGENTS.md.
- **Later: `SecretsManagerCredentialProvider`.** `credential_ref` becomes `vault://…` or an ARN. **No connector changes** — the connector receives a resolved mapping and never learns where it came from. That is the whole point of the indirection.

### 14.3 Rules

1. Credentials are resolved by the **engine**, once per run, and passed into the immutable `ConnectorContext`.
2. A connector never calls the credential provider and never sees a `credential_ref`. It therefore cannot request another tenant's credentials — it has no API with which to ask.
3. Resolution takes `tenant_id` **and** `credential_ref`, and the ref was read from that tenant's own schema. A ref belonging to another tenant is not reachable.
4. Issued tokens live in connector memory for the duration of one context. Never persisted, never logged.
5. Errors and log lines are sanitised; `sync_run_errors.error_message` must never carry a token or raw auth payload.

**Deviation to flag:** AGENTS.md's fail-fast-at-startup rule cannot fully apply. Credential refs are per-tenant rows created at runtime, so the process cannot enumerate required env vars at boot. Failure surfaces at `resolve()` time as `ConfigurationError`, moving the source to `error` with an administrator-visible message. `Inferred` — worth explicit acknowledgement rather than a silent exception to an invariant.

---

## 15. Tenant Isolation

`tenant_id` enters once, from the job payload, and is never re-derived:

```
scheduler enumerates public.tenants
   └─▶ enqueue sync_source(tenant_id, source_id)
         └─▶ engine loads data_sources FROM tenant_{tenant_id}   ← wrong id ⇒ not found
               └─▶ credential_ref read from that row only
                     └─▶ CredentialProvider.resolve(tenant_id, credential_ref)
                           └─▶ ConnectorContext(tenant_id, …, credentials)  [frozen]
                                 └─▶ connector: no DB, no storage, one tenant's creds
                                       └─▶ ingest_document(tenant_id, …)
                                             ├─▶ MinIO key tenants/{tenant_id}/documents/…
                                             └─▶ INSERT tenant_{tenant_id}.documents
```

| Layer | Isolation mechanism | Status |
|---|---|---|
| DataSource | Row lives in `tenant_{tid}` schema; cross-tenant read requires naming another schema explicitly | `Confirmed` pattern (ADR-001) |
| Connector execution | `ConnectorContext` is frozen, constructed only by the engine, carries exactly one `tenant_id` | `Inferred` |
| Credential lookup | Two-argument resolve; ref sourced from the tenant's own row | `Inferred` |
| Sync jobs | `tenant_id` in the task payload; loading the source is the authorisation check | `Inferred` |
| Document identity | `(source_id, external_id)` unique **within** a tenant schema; two tenants may legitimately hold the same external id | `Inferred` |
| Document persistence | Schema-qualified SQL built from the same `tenant_id`; MinIO prefix `tenants/{tenant_id}/` | `Confirmed` (`storage.py:33`) |
| API surface | New data-source endpoints sit behind `TenantContextMiddleware`, which derives `tenant_id` from the JWT and never from the body | `Confirmed` |

**Can two tenants share credentials?** Only if an operator points two `credential_ref`s at the same secret. The architecture cannot prevent that, and should not — a single Keka tenant genuinely could be shared. It *can* make it visible: `credential_ref` is stored plainly and auditable. `Inferred`

**Can documents cross tenants?** Not without naming another tenant's schema in SQL, which nothing in the design does, or writing outside the MinIO prefix, which `upload_file` does not permit (`storage.py:33` builds the key from `tenant_id`). `Confirmed`

---

## 16. Error and Retry Model

### 16.1 Ownership

| Concern | Owner | Behaviour |
|---|---|---|
| Per-endpoint rate limiting (50/min) | **Connector** | Client-side token bucket **per endpoint**, because Keka's bucket is per endpoint. Pre-emptive throttling, not just 429 reaction. |
| 429 handling | Connector, then engine | Connector honours `Retry-After` for short waits; a long wait becomes `RateLimitError` and the engine ends the run cleanly at the last checkpoint rather than blocking a worker slot for minutes. |
| Token refresh | Connector | One transparent refresh on 401; a second 401 is `AuthenticationError`. |
| Transport retries (timeouts, 5xx, reset) | Connector | Bounded exponential backoff with jitter. **Must not reuse the platform defaults** (0.5s→10s, 30s total, `config.py`) — 30s total is under Keka's 60s refill window. Needs `NER_EXTERNAL_SYNC_*` settings. |
| Temporary download URL expiry | Connector | Re-request the attachment URL, then re-download; only then `ItemUnavailableError`. |
| Single-item failure | **Engine** | Record and continue. `external_documents.state='failed'`, `failure_count += 1`, row in `sync_run_errors`. Run ends `partially_failed`. |
| Pagination failure mid-run | Engine | Stop at the last committed checkpoint; run ends `interrupted`; the next run resumes from `cursor_end`. |
| Auth / authorization / config failure | Engine | Fail the run immediately; set `data_sources.status='error'`. Continuing is pointless and burns rate limit. |
| Run-level crash / restart | Engine + reaper | `heartbeat_at` goes stale → reaper marks `interrupted` → lease freed → next run resumes. |
| Job-queue retry | **Queue, minimally** | Celery `acks_late` (already the extraction pattern, `celery_app.py:17`) gives redelivery. The engine must therefore tolerate re-entry: it does, because the lease index rejects a duplicate active run and item processing is an upsert. |

### 16.2 Two retry horizons, deliberately distinct

- **Within a run**: transport-level only, seconds. Bounded so one bad item cannot consume the run.
- **Across runs**: the real retry mechanism. A failed item stays `state='failed'` with `failure_count`; the next run retries it. After `max_item_attempts`, it is skipped and remains visible in `sync_run_errors` rather than retried forever. `Inferred`

This is why the engine does **not** block on rate limits. A sync that gives up cleanly at a checkpoint and resumes in 15 minutes is strictly better than a worker sleeping for 40 minutes — and it is the only shape that survives an application restart.

### 16.3 Application restart mid-sync

| Moment of restart | State on disk | Recovery |
|---|---|---|
| After checkpoint, before next batch | Run `running`, `cursor_end` current | Reaper → `interrupted`; next run resumes at cursor. Zero re-download of ingested items (ladder says unchanged). |
| Blob uploaded, transaction not committed | Orphan MinIO object; no `documents` row | Object is keyed by an unused UUID and unreferenced. Harmless; a GC sweep is a future nicety. |
| Committed, OCR not dispatched | `documents.status='pending'` | Next run sees identity known + checksum equal, but a `pending` document with no spans; the engine re-dispatches OCR for `pending` documents it owns. |
| Mid-OCR | `status='processing'` | Same failure mode as today for uploads. Not made worse; a stuck-processing sweep is a known existing gap. |

---

## 17. Service Boundaries

Mapped onto the existing topology, with the smallest number of new components.

| Responsibility | Owner | New? |
|---|---|---|
| `data_sources` persistence + admin API | **document_service** — it already owns the tenant document schema; a separate service would need cross-service writes to `documents` | New router `src/document_service/api/v1/data_sources.py` |
| Connector execution + sync engine | **New Celery worker** `celery_worker_sync`, running `src/external_ingestion/` | New container, existing pattern (mirrors `celery_worker_extraction`) |
| Scheduling | **Celery beat** container | New container; nothing periodic exists today `Confirmed` |
| Sync state persistence | Tenant schema, written by the sync worker directly | — |
| Document ingestion | **document_service** — `services/ingestion.py`, extracted from the route handler and imported by the sync worker | New module, no new service |
| OCR execution | Existing `process_document` (`ocr_worker.py:117`), unchanged body, newly reachable via a Celery task | New task wrapper only |
| Extraction execution | Existing `celery_worker_extraction`, unchanged | — |
| RAG | Existing chat_api, unchanged | — |

**No new microservice.** A "data source service" would own no data the document service doesn't already own, and would have to reach across a service boundary to write `documents` — the exact coupling the split is meant to avoid. `Inferred`

### 17.1 How the sync worker reaches ingestion

Two options were weighed:

| Option | Verdict |
|---|---|
| **A. HTTP** `POST /api/v1/documents` with `create_service_token(tenant_id)` (`auth.py:60`) | Clean boundary; auth primitive already exists. But it re-uploads every byte over HTTP, inherits the multipart/50MB shape, and lands OCR back on `asyncio.create_task` in the API process — the worst place for a 2,000-document backfill. |
| **B. Shared module** — worker imports `document_service.services.ingestion` and writes to the same DB and MinIO | **Recommended.** No byte double-hop, transactional control over the `documents` + `external_documents` upsert pair, and OCR can be dispatched to a queue. Consistent with existing practice: `ocr_worker.py:14` already imports `chat_api.services.embedding_service` across a service line. |

Option B's honest cost: `documents` gains a second writing process. That is already the norm here (`extraction_service` API and its Celery worker both write `extraction_runs`), and both processes are the same logical service split by execution model. Recorded as a trade-off (§23), not hidden.

### 17.2 OCR dispatch

`trigger_ocr` (`ocr_worker.py:228`) fires `asyncio.create_task` — in-process, non-durable, unbounded. Fine for human-paced uploads; unsafe for bulk sync.

Proposal: a `document_processing` Celery task that calls the **same** `process_document` coroutine (`asyncio.run` inside a sync task, as the extraction worker already does with sync SQLAlchemy). `ingest_document()` takes an injectable dispatcher: the upload route keeps today's behaviour, external ingestion uses the queue. Same pipeline, different dispatcher — no second pipeline. Migrating uploads to the queue too is a strictly better follow-up but is not required by this work. `Open Decision` OD-8.

---

## 18. Data Flow

### 18.1 New external document

```
beat → sync_source(tenant, source)
  lease sync_runs(running) ─ unique partial index guards concurrency
  resolve credentials → ConnectorContext(frozen, one tenant)
  connector.check_connection()
  connector.discover(cursor) ──▶ DiscoveryBatch(refs, cursor, complete_for)
    ref: external_id unknown  → rung 0
    connector.fetch(ref) ──▶ bytes + content_type
    engine: compute_content_hash(bytes)
    ┌── one transaction ────────────────────────────────────────┐
    │ MinIO put  tenants/{tid}/documents/{doc_id}.{ext}          │
    │ INSERT documents(status='pending', origin='external',      │
    │                  source_id, purpose=source.ingest_purpose) │
    │ UPSERT external_documents(state='ingested', checksum, …)   │
    │ sync_runs.ingested_count += 1                              │
    └────────────────────────────────────────────────────────────┘
  after commit: enqueue document_processing(doc_id)
  checkpoint cursor + heartbeat
  ...
  finalize run; update data_sources summary
  if extraction_policy == 'automatic': enqueue run_batch_extraction(new+updated ids)

document_processing → process_document()  [unchanged]
  → text spans → status 'processed' → (purpose='query') chunks + embeddings
  → eligible for extraction and retrievable by RAG, identically to an upload
```

### 18.2 Unchanged document

`discover → known identity → ladder rung 3 (or skipped on a shallow run) → checksum equal → touch last_seen_at, unchanged_count += 1 → stop.` No storage write, no document write, no OCR, no embedding, no extraction. (§12.9)

### 18.3 Modified document

`discover → known identity → checksum differs → purge chunks/spans/entities → new blob → update documents(status='pending') → update external_documents → re-dispatch OCR → re-extraction under existing model-version logic.` (§12.5)

### 18.4 Disappeared document

`complete enumeration of its partition → last_seen_at < run.started_at → state='missing' → deletion_policy decides (default: flag only, documents untouched) → missing_count on the run.` (§13)

---

## 19. Database Changes Required

Every change follows the established pattern — apply to `tenant_template`, then a `DO $$` loop over `tenant\_%` schemas — or existing tenants silently miss it (`030`, `034`). `Confirmed`

**Four new tenant-scoped tables:** `data_sources`, `sync_runs`, `external_documents`, `sync_run_errors` (§6).

**Two additive columns on `documents`:**

```sql
ALTER TABLE tenant_template.documents
  ADD COLUMN IF NOT EXISTS origin    VARCHAR(16) NOT NULL DEFAULT 'upload',
  ADD COLUMN IF NOT EXISTS source_id VARCHAR NULL;
```

Additive and defaulted, so every existing query, the portal, and the RAG layer keep working untouched.

**Indexes:**

| Index | Purpose |
|---|---|
| `UNIQUE (source_id, external_id)` on `external_documents` | The idempotency boundary |
| `(source_id, state)`, `(source_id, partition_key, last_seen_at)` on `external_documents` | Reconciliation sweep and admin queries |
| `UNIQUE (source_id) WHERE status IN ('pending','running')` on `sync_runs` | At most one active run per source |
| `(source_id, started_at DESC)` on `sync_runs` | Recent-runs listing |
| `(run_id)` on `sync_run_errors` | Failure listing |
| `(origin, source_id)` on `documents` | Filtering external documents |

**No foreign keys.** `CREATE TABLE … (LIKE … INCLUDING CONSTRAINTS)` does not copy FKs, so cloned tenant schemas would silently lack any FK declared on the template (`tenant_service.py:58`). Relying on FK cascade would work in `tenant_template` and nowhere else. Integrity is application-enforced, consistent with how the existing tenant tables actually behave. `Confirmed`

**No changes** to `document_text_spans`, `document_chunks`, `extracted_entities`, `document_entities`, `extraction_runs`, or any `public` table.

---

## 20. Existing Components Reused

Verified against code, not assumed.

| Component | File | Change |
|---|---|---|
| MinIO storage client | `document_service/services/storage.py` | **None.** `upload_file(tenant_id, doc_id, ext, data)` already fits. |
| Content hashing | `document_service/services/content_hash.py` | **None.** Same SHA-256 for both origins. |
| OCR / text extraction | `ocr_worker.py:117` `process_document` | **Body unchanged.** Two small guards required (below). |
| Chunking | `src/shared/retrieval/chunking.py` | **None.** |
| Embeddings | `chat_api/services/embedding_service.py` | **None.** |
| Extraction API + worker | `extraction_service/**` | **None.** External documents become eligible purely by being `status='processed'` + `purpose='query'` (`extraction.py:155`). |
| RAG retrieval | `shared/retrieval/retriever.py`, `chat_api/services/rag_orchestrator.py` | **None.** `document_chunks` rows are byte-identical in shape regardless of origin. |
| Tenant provisioning | `gateway/services/tenant_service.py` | **None** — new tables are picked up automatically by the `pg_tables` loop over `tenant_template` (`tenant_service.py:52`). |
| Auth / tenant middleware | `shared/auth.py`, `document_service/middleware/tenant_context.py` | **None.** `create_service_token` already exists. |
| Portal document pages | `src/portal/**` | **None** for this phase. |

**Required small changes to existing code** — listed explicitly rather than filed under "unchanged":

1. `documents.py:50` — extract the ingest body into `services/ingestion.py`; the route becomes a thin HTTP adapter. Behaviour identical.
2. `ocr_worker.py:133` — make the `processing` transition conditional (`WHERE status='pending'`) so at-least-once dispatch cannot double-OCR.
3. `ocr_worker.py` — delete existing spans/chunks for a document before re-processing it, so re-ingest-on-change cannot duplicate spans.
4. `ocr_worker.py:228` — `trigger_ocr` becomes an injectable dispatcher (asyncio for uploads, Celery for sync).

Items 2 and 3 are latent defects in the current pipeline that external ingestion would expose; they are not new requirements invented by this design.

---

## 21. Keka Implementation Mapping

Everything below lives in `src/external_ingestion/providers/keka/` and nowhere else.

| Generic concept | Keka realisation | Evidence |
|---|---|---|
| `provider` | `"keka"` | — |
| Authentication | OAuth2 client-credentials: `POST {login.keka.com\|login.kekademo.com}/connect/token`, form-encoded `grant_type=kekaapi`, `scope=kekaapi`, `client_id`, `client_secret`, `api_key`; header `user-agent: Mozilla` | `Confirmed` |
| `config` | subdomain/base URL, environment (`production`\|`sandbox`), optional `documentTypeId` filter, `employmentStatus` filter, page size | `Confirmed` |
| `credential_ref` | `env:keka_<tenant-slug>` → `client_id`, `client_secret`, `api_key` | design |
| `discover()` | `GET /hris/employees` (paged, optional `lastModified` filter) → per employee `GET /hris/employees/documents` (paged) → one ref per **attachment** | `Confirmed` |
| Pagination | `pageNumber`/`pageSize` (default 100, max 200); `nextPageReference == null` ends | `Confirmed` |
| Opaque cursor | `{employee_page, last_employee_modified_watermark, last_employee_id}` — engine stores it verbatim | design |
| `partition_key` | `employeeId` | design |
| `external_id` | `"{employeeId}:{documentId}:{attachmentId}"` | `Confirmed` (ids) / design (composite) |
| `filename` | `attachment.name` | `Confirmed` |
| `content_type` | Derived from the filename extension **inside the connector** — Keka exposes none | `Confirmed` absent |
| `external_version` | `None` | `Confirmed` absent |
| `source_modified_at` | `None` — **not** sync time (§8.2) | `Confirmed` absent |
| `fetch()` | `GET /hris/employees/documents/attachment?employeeId&documentId&attachmentId` → `data.fileURL` (temporary) → download bytes | `Confirmed` |
| `capabilities` | `change_detection="content_hash"`, `deletion_signal="reconciliation"`, `supports_incremental=True`, `supports_event_ingest=False`, `max_requests_per_minute=50` | `Confirmed` (limit, gaps) / `Inferred` (mapping) |
| Rate limiting | Per-endpoint token bucket at 50/min, `Retry-After` on 429 `rateLimitExceeded` | `Confirmed` |
| Employee metadata, document type, custom attributes | `provider_metadata` JSONB only | design |
| MCP | Not used in production. Research/dev tool | `Confirmed` |
| Webhooks | Not used. No documented document event; no subscription API | `Confirmed` |

Open Keka unknowns carried forward from the research (all non-blocking, none of which the generic design depends on): whether the document DTO ever exposes timestamps; whether MIME/size are obtainable; whether the full webhook catalogue contains a document event; whether the temporary `fileURL` requires the bearer token. `Unknown`

---

## 22. Future Provider Extensibility

A new provider requires: one connector class, one registry entry, one credential-ref convention. It requires **no** change to the engine, the schema, `documents`, OCR, chunking, embeddings, extraction, or RAG.

| Provider shape | Capability declaration | Engine change |
|---|---|---|
| ETag/revision store (e.g. object storage) | `change_detection="version"`, `deletion_signal="reconciliation"` | None — rung 1 activates |
| Delta-API provider | `change_detection="version"`, `supports_incremental=True`; cursor is the delta token | None; engine schedules periodic `cursor=None` runs for reconciliation |
| Webhook provider | `supports_event_ingest=True`; an event endpoint enqueues `trigger='event'` runs | One new ingress endpoint; the sync loop itself is unchanged |
| Timestamped repository | `change_detection="source_timestamp"` | None — rung 2 activates |
| Provider with true tombstones | `deletion_signal="events"`; sets `ref.deleted` | None |

The extensibility claim rests on one property: the engine reads `capabilities` and nullable fields, never a provider name. If any `if provider == …` appears outside the registry, the abstraction has failed and the review in §25 should catch it.

---

## 23. Trade-offs

| Decision | Chosen | Alternative | Cost accepted |
|---|---|---|---|
| Identity storage | Separate `external_documents` table | Columns on `documents` (research doc's recommendation) | One extra table and a join for provenance queries. Bought: pre-ingestion states, survivable soft-delete, many-to-one content reuse, no sync bookkeeping on the core table. |
| Sync ownership | Engine owns sync; connector owns discovery/fetch | `connector.sync()` | Connectors cannot express a truly exotic sync shape without an engine change. Bought: idempotency, checkpointing, and failure isolation implemented once and correctly. |
| Per-document run history | Current state on `external_documents` + failures only | `sync_run_items` table | No per-run record of which documents were unchanged. Bought: avoids ~48M rows/year for one 2,000-document source. |
| Table placement | Tenant schemas | `public` with `tenant_id` | Scheduler fans out per tenant instead of one global query. Bought: isolation by construction (ADR-001). |
| Ingestion transport | Shared module import | HTTP with service token | `documents` gains a second writing process. Bought: no byte double-hop, transactional `documents` + `external_documents` write, queued OCR. |
| Content dedup | Reuse the document when checksum matches (proposed) | One document per external identity | Deletion semantics become ref-counted. Bought: no 200× duplicate OCR/embedding/extraction for a shared HR document. **Open — OD-2.** |
| Change on Keka | Download-to-compare, with shallow/deep run split | Download everything every run | Deep runs are slow and rate-limited; a change can go unseen until the next deep run. Bought: viable sync cadence. **Cadence open — OD-7.** |
| Modified documents | Update in place | New row per version with supersession | No document history; a chat citation may point at replaced content. Bought: one stable `document_id`, no consumer changes. **Open — OD-3.** |
| Deletion default | `flag_only` | Auto soft-delete | Storage and stale RAG content accumulate for genuinely deleted documents. Bought: no destructive action inferred from a provider with no deletion signal. **Open — OD-1.** |
| Extraction | `manual` default, `automatic` opt-in | Always extract after sync | An admin must trigger extraction after the first sync. Bought: no accidental 5,000-document GPU run. **Open — OD-5.** |
| Scheduling | Celery beat | Cron/external scheduler | One more container. Bought: same broker, same code, no new infrastructure class. |

---

## 24. Open Decisions

| ID | Decision | Why it is a product decision, not an architectural one | Recommendation |
|---|---|---|---|
| **OD-1** | What happens when an external document disappears from the provider? | Data-retention policy with legal/HR implications. Keka provides no deletion signal, so absence is inference, not fact. No existing product requirement covers it. | Default `flag_only`; make the policy per-source and configurable. |
| **OD-2** | Do byte-identical external documents share one `documents` row? | Changes what "delete" means and diverges from the existing "identify, never merge" upload behaviour (`documents.py:94`). | Share, for the 200-employees-one-policy case. Requires ref-count-aware deletion. |
| **OD-3** | Update in place, or version documents on content change? | Affects chat citation semantics and whether history is a product feature. | Update in place for v1. |
| **OD-4** | What happens to ingested documents when a data source is deleted? | Deleting a connection should probably not delete tenant data — but that is a policy call. | Disable, retain everything; deletion is a separate explicit action. |
| **OD-5** | Automatic extraction after sync — default, opt-in, or per-source? | Direct GPU/compute cost, and the platform's existing governance deliberately makes extraction explicit. | Per-source, defaulting to `manual`. |
| **OD-6** | Should employee association become a first-class platform concept? | If HR-document-per-person filtering is a product requirement, `provider_metadata` is the wrong home — but promoting it now would leak an HR concept into a generic model with no requirement behind it. | Keep in `provider_metadata` until a requirement exists. |
| **OD-7** | Shallow/deep run cadence, and the acceptable staleness window for content changes | "How long may a modified Keka document go unnoticed?" is an SLA question. | Frequent shallow, nightly deep, as a starting point. |
| **OD-8** | Should user uploads also move to queued OCR? | Improves durability platform-wide but touches the existing upload path. | Yes, as a separate follow-up change. |
| **OD-9** | Should `business_user` see externally ingested documents in the document list? | Today `list_documents` filters `uploaded_by = :user_id` for non-admins (`documents.py:161`), so external documents (no uploader) would be invisible to them — yet RAG will happily retrieve their chunks, since retrieval filters only on `purpose='query'` (`retriever.py:70`). The inconsistency is real and needs a policy answer. | Make external documents visible tenant-wide; align the list filter with retrieval. |
| **OD-10** | Who provisions and rotates per-tenant Keka credentials? | Operational process, and Keka's API is a paid add-on whose keys only a Global admin can issue (`Confirmed`). | Document in tenant onboarding before the first production source. |

---

## 25. Implementation Sequence

Derived from the architecture's dependency order, not from the template in the brief. The template's Phase 2 ("generic connector + ingestion contract") is split, because the **ingestion seam** is a prerequisite for everything and is independently valuable, while the **connector contract** is pure types with no runtime dependency.

| Phase | Content | Depends on | Independently verifiable |
|---|---|---|---|
| **P0** | **Ingestion seam.** Extract `ingest_document()` from the upload route; make the OCR dispatcher injectable; add the conditional `processing` transition and the pre-reprocess purge (§20 items 1–4). No new tables, no external concepts. | — | Existing upload tests must pass unchanged; new tests for double-dispatch and re-process. |
| **P1** | **Schema foundation.** Migration: 4 tables + 2 `documents` columns + indexes, in `tenant_template` and looped over existing tenant schemas. | P0 (not strictly, but keeps the surface small) | Migration applies to a seeded multi-tenant DB; a newly provisioned tenant inherits every table via the `pg_tables` clone. |
| **P2** | **Contracts.** `SourceConnector` protocol, `ConnectorCapabilities`, `ExternalDocumentRef`, `DiscoveryBatch`, `FetchedContent`, error taxonomy, `CredentialProvider` + `EnvCredentialProvider`, connector registry. Types and a fake connector only. | P1 | A fake in-memory connector exercises the whole contract. |
| **P3** | **Sync engine + state.** Lease, discovery loop, change-detection ladder, fetch, ingest, counters, checkpointing, reaper, item-failure isolation, reconciliation sweep. Driven entirely by the fake connector. | P0, P1, P2 | Idempotency, resume-after-crash, concurrent-run rejection, and unchanged-is-a-no-op are all testable with **zero provider code**. This is the phase that proves the abstraction. |
| **P4** | **Data source API + worker wiring.** CRUD for `data_sources`, `check_connection` endpoint, manual sync trigger, `celery_worker_sync` + beat containers, per-tenant fan-out scheduling. | P3 | Fake-provider source configured, scheduled, and synced end to end. |
| **P5** | **Keka connector.** Auth, pagination, per-endpoint throttling, identity construction, content-type derivation, error mapping, capability declaration. Tested entirely against mocked Keka responses. | P2 (contract only — deliberately not P3) | Contract-conformance tests; no engine changes permitted in this phase. **If a change to P2/P3 proves necessary here, the abstraction was wrong — stop and revisit rather than special-case.** |
| **P6** | **Keka end-to-end against a sandbox.** Backfill, incremental, deep/shallow cadence, rate-limit behaviour, resume, reconciliation. | P4, P5, sandbox access (OD-10) | The research doc's verification plan (§18 there) runs as-is. |
| **P7** | **Extraction policy.** `extraction_policy` honoured; automatic mode enqueues `run_batch_extraction` for new/updated ids; re-extraction on content change. | P3, P6 | External documents extract exactly once per model version; unchanged ones do not re-extract. |
| **P8** | **Observability + admin API surface.** Run history, counters, failure listing, source health — as API, not UI. | P4 | Every §11 question answerable from persisted state. |
| **P9** | **UI.** Per the source-of-truth doc's explicit sequencing: UI last, on top of reliable state. | P8 | — |
| **P10** | **Hardening.** Orphan-blob GC, stuck-`processing` sweep, the §26 review re-run against the built system, load test at the largest realistic tenant. | P6–P9 | — |

Two ordering claims worth stating plainly:

- **P5 depends on P2, not P3.** The Keka connector is written against types alone. If it needs the engine to change, that is the loudest possible signal that the abstraction leaked.
- **P0 comes before the schema.** The ingestion seam is the only change to existing behaviour, it carries the real regression risk, and it is worth landing and verifying alone.

---

## 26. Critical Review

Answering the brief's eighteen challenges against this design.

**1. Are we creating abstractions that exist only because of Keka?**

Two are suspect, examined honestly:

- `partition_key` (§13.2) exists because Keka's discovery is employee-scoped and incremental runs enumerate only part of the source. **Kept** — but note the generalisation is real: any provider with partial enumeration (folder-scoped, delta-scoped) needs exactly this to reconcile safely, and without it reconciliation is simply unsound. The alternative — reconciling only on full runs — is strictly weaker.
- The shallow/deep run split (§10.4) exists because Keka forces download-to-compare. **Kept**, because it is expressed as a cost parameter (`deep_check_interval_minutes`), and any rung-3 provider needs it. Providers on rungs 1–2 set it to zero and never notice.

`ConnectorCapabilities` itself is **not** Keka-driven: it exists precisely so the engine never asks "which provider is this".

**2. Are we leaking Keka concepts into the generic layer?**

No employee, attachment, document type, subdomain, or `kekaapi` scope appears in any generic type, table column, or engine code path. `external_id` and `partition_key` are opaque strings compared only for equality; `cursor` and `provider_metadata` are JSONB the engine never reads inside. The `provider` discriminator names Keka but selects code rather than branching behaviour.

Residual risk: nothing mechanically *prevents* an engine author from parsing `external_id`. Mitigation is a stated invariant plus review. `Inferred`

**3. Are we duplicating the existing document pipeline?**

No. Both origins call one `ingest_document()` and one `process_document()`. The only fork is the OCR **dispatcher** (asyncio vs Celery), which changes when the same function runs, not what it does. Extraction and RAG have no origin-aware code at all — external documents are eligible and retrievable purely by virtue of `status='processed'` and `purpose='query'`.

**4. Are we making synchronization state provider-specific?**

No columns for provider concepts. The two provider-shaped fields are explicitly opaque (`cursor`, `provider_metadata`) and one is a discriminator (`provider`). A different provider stores a different cursor shape in the same column.

**5. Can another provider implement the connector without touching extraction/RAG?**

Yes — §22. The connector produces bytes plus metadata; the ingestion seam produces a `documents` row; everything downstream keys off that row. There is no reachable code path from a connector to `document_chunks`, `extracted_entities`, or the retriever.

**6. Can a connector be retried safely?**

Yes. Connectors are stateless between calls and persist nothing, so re-invocation is free of side effects on our side. Engine-level safety comes from the lease, the `(source_id, external_id)` upsert, and the checksum comparison — not from connector behaviour. The one non-idempotent step is the provider-side `GET`, which is read-only.

**7. Can synchronization resume after a crash?**

Yes, at batch granularity — §16.3. Cursor and heartbeat are committed at each checkpoint; the reaper frees a stale lease; the next run resumes from `cursor_end`. Work lost is bounded by one batch, and re-processing that batch is a no-op via the ladder. **Gap:** an orphan MinIO object can be left if the process dies between the blob put and the commit. Harmless (unreferenced, UUID-keyed) but it accumulates. GC is deferred to P10 and is named here rather than glossed.

**8. Can two tenants ever share credentials or documents?**

Documents: no — separate schemas, and MinIO keys are built from `tenant_id` inside `upload_file`. Credentials: only if an operator deliberately points two `credential_ref`s at one secret, which is a legitimate configuration and is visible in the data. No code path lets a connector reach a ref it was not handed.

**9. Can the system distinguish changed from unchanged?**

Yes, at the strongest level any provider supports (§10.2). For Keka this is byte-level SHA-256 — the most reliable rung, obtained at the highest cost. On shallow runs the answer is deliberately deferred, which is an explicit staleness trade-off (OD-7), not an undetected gap.

**10. Have we assumed timestamps, webhooks, or delta APIs anywhere?**

No. `source_modified_at`, `source_created_at`, and `external_version` are all nullable; the ladder's timestamp and version rungs are guarded on capability declarations. The research doc's `modified_at = sync_time` fallback was **rejected** as actively harmful (§8.2). Webhooks appear only as an unimplemented capability flag. Deletion assumes nothing — `deletion_signal="none"` is a first-class, supported case.

**11. Are we adding complexity Keka does not need?**

Audit of every generic mechanism:

| Mechanism | Keka needs it today? | Verdict |
|---|---|---|
| `external_documents` table | Yes | Keep |
| `sync_runs` + counters | Yes (the source-of-truth doc requires operational visibility) | Keep |
| `sync_run_errors` | Yes ("which documents failed") | Keep |
| Change-detection ladder | Only rung 3 | Keep — rungs 1–2 are ~10 lines and are the difference between a generic and a Keka-shaped engine |
| `partition_key` | Yes, for correct reconciliation | Keep |
| `deletion_policy` enum | Only `flag_only` today | **Ship `flag_only` first**; add other policies when OD-1 is answered. Do not build all four speculatively. |
| `external_version` | No (always NULL) | Keep — one nullable column, and its absence would force a schema change for provider two |
| `supports_event_ingest` | No | Keep as a flag; **build no webhook machinery** |
| `CredentialProvider` indirection | Yes (env today, vault later) | Keep — this is the interface AGENTS.md invariant 3 pushes toward |
| Shallow/deep runs | Yes (rate limits force it) | Keep |
| Content-addressed reuse | Probably (shared HR documents) | **Gated on OD-2** — do not build before the decision |

Two items are therefore explicitly deferred rather than built: the full `deletion_policy` matrix, and webhook ingestion.

**12. Which decisions are actually product decisions?**

Ten, catalogued in §24. The three that block implementation: OD-1 (disappearance behaviour), OD-2 (content dedup), OD-5 (extraction policy). The rest can be defaulted and revisited.

### Problems found during this review

| # | Problem | Severity | Where |
|---|---|---|---|
| R1 | `process_document` inserts spans without purging and transitions status unconditionally — at-least-once dispatch or re-ingest **duplicates every span and chunk**. A pre-existing defect that external ingestion would expose immediately. | **High** | §12.8, §20; fixed in P0 |
| R2 | OCR via `asyncio.create_task` in the API process is non-durable and unbounded — unusable for a 2,000-document backfill. | **High** | §17.2; queued dispatch in P0 |
| R3 | Keka change detection requires downloading everything, every run; ~80 minutes of rate-limited traffic for a 2,000-attachment tenant. Neither the research nor the source-of-truth doc surfaced the cadence consequence. | **High** | §10.4; shallow/deep split, OD-7 |
| R4 | `list_documents` hides documents from non-admins by `uploaded_by`, while RAG retrieves their chunks regardless — external documents would be invisible in the UI yet answerable in chat. | **Medium** | OD-9 |
| R5 | Attachment-level identity multiplies shared documents (one policy PDF × 200 employees = 200 OCR + 200 embedding runs) unless content-addressed reuse is adopted. | **Medium** | §12.7, OD-2 |
| R6 | `LIKE … INCLUDING CONSTRAINTS` does not copy foreign keys, so tenant schemas have none. Any design relying on FK cascade would work in `tenant_template` and silently fail everywhere else. | **Medium** | §19 |
| R7 | AGENTS.md's fail-fast-at-startup secret rule cannot apply to runtime-created per-tenant credential refs; failure necessarily surfaces at resolve time. An acknowledged deviation, not a silent one. | **Medium** | §14.3 |
| R8 | Platform retry defaults (30s total) are shorter than Keka's 60s rate-limit refill; reusing them guarantees give-up-before-recovery. | **Medium** | §16.1 |
| R9 | Orphan MinIO objects accumulate if a process dies between blob upload and commit. Harmless individually; needs GC. | **Low** | §16.3, P10 |
| R10 | `documents` gains a second writing process (API + sync worker). Consistent with the existing extraction pattern, but it is real coupling. | **Low** | §17.1 |
| R11 | Nothing mechanically prevents engine code from parsing `external_id` or reading `provider_metadata`; the opacity invariant is review-enforced only. | **Low** | §26.2 |
| R12 | The `mode='full'` vs `cursor=None` equivalence is a convention, not a type. A connector could ignore `cursor=None` and return a partial enumeration, silently breaking reconciliation. Worth a contract test in P2. | **Low** | §10.3 |

---

## 27. Summary

**Proposed architecture.** A generic sync engine drives a thin, stateless connector through three methods — `check_connection`, `discover`, `fetch` — and hands the resulting bytes to a single extracted ingestion function that the existing upload route also uses. Provider-specific behaviour (auth, pagination, rate limits, identity construction, content-type derivation) lives entirely inside the connector; the engine owns everything stateful (leasing, checkpointing, change detection, idempotency, failure isolation, reconciliation). Downstream — OCR, spans, chunks, embeddings, extraction, RAG — is untouched and origin-blind.

**Major schema changes.** Four new tenant-scoped tables (`data_sources`, `sync_runs`, `external_documents`, `sync_run_errors`), two additive nullable/defaulted columns on `documents` (`origin`, `source_id`), and the `UNIQUE (source_id, external_id)` constraint that is the system's idempotency boundary. No foreign keys, because cloned tenant schemas cannot carry them. No changes to any derived table.

**Major new components.** One package (`src/external_ingestion/`: contracts, engine, state, credentials, registry, tasks), one extracted module (`document_service/services/ingestion.py`), one Celery task wrapping the existing OCR function, one admin API router, and two containers (a sync worker and a beat scheduler). No new microservice.

**Keka boundary.** Everything Keka — OAuth token flow, `GET /hris/employees`, `GET /hris/employees/documents`, the attachment URL round-trip, `{employeeId}:{documentId}:{attachmentId}`, extension-based content types, the 50/min per-endpoint bucket, `nextPageReference` pagination — sits inside `providers/keka/`. Outside it, Keka appears as one string in a `provider` column.

**Biggest risks.** (1) Keka's absent document timestamps force download-to-compare, making exhaustive change detection rate-limit-bound at ~80 minutes for a large tenant — the shallow/deep split manages it but does not eliminate the staleness window. (2) Two latent defects in the current OCR path (duplicate spans on reprocess, non-durable dispatch) must be fixed before any bulk ingestion. (3) Attachment-level identity multiplies shared HR documents unless content dedup is adopted. (4) Deletion is inferred, never observed, so any destructive default would be acting on a guess.

**Requires human approval before implementation.** OD-1 (what happens when an external document disappears), OD-2 (whether byte-identical external documents share one document row), and OD-5 (whether extraction runs automatically after sync) block implementation. OD-3, OD-4, and OD-9 shape it and have recommended defaults. OD-6, OD-7, OD-8, and OD-10 can be deferred past the first working sync.

**Nothing in this document has been implemented.** No code changed, no migration created, no connector written.
