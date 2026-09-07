## Context

Every document in the platform enters through one function. `POST /api/v1/documents` (`documents.py:58`) validates the file, generates the id, invents the MinIO object key, hashes the bytes, looks for a byte-identical earlier upload, writes to MinIO, inserts the `tenant_{tid}.documents` row, commits, and fires OCR via `asyncio.create_task`. The OCR worker (`ocr_worker.py:160`) then re-reads the bytes from MinIO and chooses between PyMuPDF text extraction and Tesseract OCR by splitting the object key on a dot (`ocr_worker.py:197`).

Everything downstream is already infrastructure-neutral, which is what makes a small boundary possible. `extract_text_pdf`, `extract_text_image`, and `extract_text_pdf_as_image` are pure `bytes → spans`. `chunk_text` is pure. `EmbeddingService.embed_batch` is pure. The extraction worker selects on `status='processed' AND purpose='query'` and reads `document_text_spans`. Retrieval filters on `purpose='query'`. Rank fusion happens in Python. None of them can tell an upload from a fetch.

Two constraints shape everything below. `AGENTS.md` invariant 3: no secret may be hardcoded in source, configuration, or committed `.env`, and secret-class settings carry no defaults. `AGENTS.md` invariant 4: log the shape of data, never the data, and metric labels must come from finite declared sets.

Three architecture documents are the authoritative inputs: `tenant-pluggable-data-architecture.md` (the five-boundary frame and the conclusion that only two are worth building now), `document-ingestion-source-boundary.md` (the push/pull split), and `external-data-source-architecture.md` (the pull-side sync design, deferred here).

## Goals / Non-Goals

**Goals:**

- One application-owned ingestion entry point that every source calls, with platform upload as its first adapter and no privileged path around it.
- An honest, complete content lifecycle: how the worker obtains bytes at first processing, on retry, and on reprocess, for retained and non-retained documents alike.
- Original-blob storage becomes a selectable boundary so that "do not keep this tenant's originals" is configuration rather than a fork of the pipeline.
- The processing pipeline stops depending on the storage key for anything.
- Reprocessing is idempotent, and repeated dispatch is a no-op.
- Per-tenant adapter selection becomes explicit, typed, auditable control-plane state holding secret references only.
- The later boundaries — pull sources, tenant PostgreSQL, index, business-database querying — remain reachable without reopening what is written here.

**Non-Goals:**

- No pull-source connectors and no sync engine. The pull-side `DocumentSource` contract is specified in `external-data-source-architecture.md` and deliberately not built here.
- No tenant-hosted PostgreSQL and no per-tenant connection routing beyond introducing the resolver seam.
- No index or vector boundary, and **no change to the `Retriever` protocol** — removed from this change on the grounds that it unblocks nothing in scope and touches the chat path.
- No tenant business-database querying, no semantic schema contract, no generated-SQL validation work.
- No ports over PostgreSQL, pgvector, SQLAlchemy, Celery, MLflow, or model serving. No repository-per-table. No generic database abstraction.
- No abstraction of the runtime-generated entity tables, the analytics materialized views, or the least-privilege SQL execution role. They are PostgreSQL by design.
- No customer-facing self-service configuration.
- No change to any externally observable behaviour of `POST /api/v1/documents`.

## Currently-In-Force ADRs

Supersession graph: ADR-008 partially supersedes ADR-002; ADR-009 and ADR-010 each partially supersede clauses of ADR-006. No ADR is superseded in a way that affects this design. ADRs 002, 006, 008, 009, and 010 concern the model and training planes and place no constraint on it.

| ADR | Decision Summary | Constraint on This Design |
|-----|-----------------|--------------------------|
| ADR-001 Tenant Data Isolation via Separate Database Schemas | Tenant content lives in per-tenant PostgreSQL schemas; isolation is enforced by construction | New tenant-scoped state stays in `tenant_{tid}`; new platform-scoped state stays in `public`. The integration profile is control-plane and belongs in `public`. Nothing may reach tenant data without the tenant id that entered from the JWT. |
| ADR-003 Per-Tenant Model Serving Topology | Model serving is isolated per tenant | Untouched. The model plane, including MinIO usage for model artifacts, must not be swept into the content-store boundary. |
| ADR-004 OpenSpec Spec-Driven Development Governance | Every feature traceable from spec to executable evidence | Every acceptance criterion needs an executable verification artifact that fails when its THEN clause is violated. |
| ADR-007 Chatbot Architecture with Full RAG and Guardrails | Tenant-scoped RAG with citations and guardrails, P95 under 10s | Retrieval is out of scope. The one chat-adjacent effect is the visibility rule in Decision 7, which makes listing agree with what retrieval already returns. |

## Decisions

### Decision 1: One inbound ingestion contract; the pull-side source contract is separate and deferred

**Choice:** One application use case accepts a normalized document and is the only code permitted to create a `documents` row. Every adapter calls it. The pull-side abstraction (`check_connection` / `discover` / `fetch`) is a different contract, written in `external-document-sources`, that upload does not implement.

**Rationale:** Upload is a push source — bytes arrive unbidden, over HTTP, once. Keka, S3, and Azure are pull sources — the platform enumerates, decides what is new, then fetches. A single interface both satisfy would force upload to implement "list everything you have" and "check the connection", neither of which it can answer honestly. Two stub methods on the first adapter is the standard signal of a merged abstraction.

**Alternatives considered:**
- One `DocumentSource` interface implemented by upload and every fetcher — ruled out because upload's `discover()` can only be a lie, and the first pull source would then be tempted to change the interface rather than fit it.
- Future sources post to the upload route over HTTP with a service token — ruled out: it re-uploads every byte, inherits the multipart and 50 MB shape, and lands bulk OCR in the API process.

### Decision 2: Content acquisition is a declared capability, and retention mode is the recorded resolution

**Choice:** A source declares itself `single_use` (bytes exist only during the submitting call) or `reopenable` (the adapter can be asked again later). The ingestion operation combines that declaration with the tenant's configured retention preference and records the outcome as the document's `retention_mode`, one of `platform_blob`, `ephemeral`, or `source_only`. The worker resolves bytes from that recorded value and nothing else.

**Rationale:** This is the gap an earlier draft left open. It promised that OCR could process a document with a NULL storage reference but never said where the bytes come from after the HTTP request ends. For a browser upload there is no source to re-ask: the connection is gone. So exactly three resolutions exist, and each has to be named:

| Retention mode | Where bytes come from | When it applies |
|---|---|---|
| `platform_blob` | Durable content store, using the recorded reference | Default. Any source. |
| `ephemeral` | Working content store, until the working copy is deleted | A `single_use` source whose tenant does not want a durable original — i.e. platform upload with no retention |
| `source_only` | The originating source adapter, re-asked on demand | A `reopenable` source whose tenant permits no platform copy at all. Modelled now, executable when pull sources land |

The combination `single_use` content with `source_only` retention is impossible and is rejected at ingestion rather than discovered at processing time.

**The honest consequence, stated rather than hidden:** under `ephemeral` retention the bytes **do** transit platform-operated storage for the duration of processing. "No retention" means no durable original, not "the bytes never touch our infrastructure". A tenant that cannot permit that transit cannot use platform upload at all and must wait for a reopenable source. This is recorded as approval item A1.

**Alternatives considered:**
- Process synchronously inside the upload request when retention is off — ruled out: OCR of a 50 MB scanned PDF takes minutes; it would change the API's latency contract and hold a worker for the duration.
- Hold the bytes in process memory and hand them to the in-process task — ruled out: it works only for the in-process dispatcher, dies with the process, leaves the document `pending` forever, and makes retry impossible. It would also make the design untestable in the way that matters, because it cannot survive the queued dispatcher that `external-document-sources` needs.
- Pass bytes or a storage path through the dispatch payload — ruled out: dispatch must be replayable from persisted state, and a payload carrying content cannot survive a restart or a queue.
- Treat a test-only in-memory reopenable source as proof that no-retention works — explicitly ruled out. It proves the boundary compiles, not that a production worker can obtain bytes. The verification for `ephemeral` runs against a real working store.

### Decision 3: The content store has three operations, and the storage reference is an outcome

**Choice:** One boundary — put, open, delete — with the MinIO client as the default adapter behind two configured instances, durable and working. The store returns the reference; nothing predicts it. A NULL reference is a valid state.

**Rationale:** Today the route computes the key before storage runs (`documents.py:98`) and passes it to both the row and the worker. While the key is an input, no adapter can decline to store, because something downstream already holds a path it expects to resolve. `delete` is required by ephemeral retention and by document deletion; adding it now avoids a second revision of the contract.

**Alternatives considered:**
- A separate working-store boundary with its own contract — ruled out as two boundaries for one concern. The lifecycle difference is configuration (an expiry policy and a delete call), not shape.
- Keep the key as an input and let a no-retention adapter ignore it — ruled out: the worker would still receive a path resolving to nothing, converting a policy into a runtime failure.

### Decision 4: The OCR branch keys off media type, and dispatch carries only identity

**Choice:** Processing is dispatched with document id and tenant id. The worker loads the document, resolves bytes by recorded retention mode, and selects the extractor from the resolved media type — declared type, then filename extension, then content sniff.

**Rationale:** The key-parsing line is what blocks every later option, and `content_type` is currently a dead parameter on both `process_document` and `trigger_ocr`, so the declared type has no authority today. Dispatching identity only makes a job replayable from persisted state, which is the precondition for the queued dispatcher that bulk sync will need. The three-step resolution preserves current behaviour exactly, because the extension remains the fallback and is what is used today.

**Alternatives considered:**
- Keep parsing the key and have no-retention adapters synthesise a fake key with the right extension — ruled out as exactly the shim that makes an abstraction decorative.
- Trust the declared media type alone — ruled out: uploads frequently arrive as `application/octet-stream`, which would change behaviour for real existing documents.

### Decision 5: Reprocessability is bounded by retention mode, and the purge follows the resolve

**Choice:** A `platform_blob` document is reprocessable for its lifetime; an `ephemeral` document only until its working copy is deleted; a `source_only` document only while its source can be asked. A reprocess whose bytes are unresolvable fails explicitly, leaves derived data intact, and does not mark the document `failed`. The purge of existing spans and chunks happens only after bytes are successfully resolved.

**Rationale:** Purge-then-fetch would destroy a document's derived data whenever the bytes turn out to be gone — turning a recoverable state into permanent loss. Ordering the operations is the whole mitigation. Stating the bound is equally important: silently pretending every document is reprocessable would make the first expired working copy look like a bug rather than the documented consequence of a retention choice.

**Alternatives considered:**
- Keep the working copy until an explicit reprocess window closes — ruled out for this change as an unbounded retention decision dressed up as a cache; the expiry is the tenant's privacy guarantee.
- Mark such a document `failed` — ruled out: the document processed successfully once, and its spans, chunks, and citations remain valid.

### Decision 6: Provenance on `documents`; sync bookkeeping deferred to a ledger

**Choice:** Add provenance and retention columns to `documents`, additive and defaulted, with **no unique constraint** on the external identity, and persist the storage reference in the existing `blob_path` column rather than adding a second column for the same value. Sync state — what exists at the source, when it was last seen, failure counts — belongs to the ledger introduced by `external-document-sources`.

**Rationale:** Provenance is document metadata that every consumer wanting to display or filter by origin would otherwise have to join for. Sync identity is bookkeeping, and deferring it sidesteps three problems that only exist once pull sources are real: a discovered-but-not-yet-fetched object has no `documents` row; `documents` is soft-deleted, so a unique index would permanently block re-ingesting a re-appearing object; and content-addressed reuse makes the relationship many-to-one. Introducing a `storage_reference` column now would create a fourth name for one value and widen the very drift that `document-metadata-column-reconciliation` exists to close.

**Alternatives considered:**
- Full external-identity ledger now — ruled out as scope that cannot be exercised, since no pull source exists to write to it.
- Rename `blob_path` here — ruled out: the rename must land with the `002`/`003` reconciliation and the chatbot query-surface changes it implies, which are out of scope.

### Decision 7: Platform upload uses a reserved, deterministic `source_id`; visibility follows the actor kind

**Choice:** `source_id` for platform upload is the reserved literal `platform-upload`, identical for every tenant, stable for the life of a tenant, never issued to a configured source, and requiring no extra table or backfill of generated identifiers. Separately, every document records the kind of actor that ingested it, and the non-administrative list filter applies **only** to human-ingested documents.

**Rationale:** A generated per-tenant identifier would need a table, a backfill, and a lookup on every upload, to express a fact that is constant. A reserved literal is deterministic by construction and reads correctly in a log line. On visibility: `list_documents` filters non-admins by `uploaded_by` (`documents.py:169`) while retrieval filters only on `purpose` (`retriever.py:70`), so a system-ingested document would be invisible in the portal yet answerable in chat. Deciding it now — visible tenant-wide — closes the inconsistency before any source can create one.

**Alternatives considered:**
- A per-tenant UUID row in a `document_sources` table — deferred to `external-document-sources`, which needs that table anyway for real sources. Creating it now to hold one constant row per tenant is table-shaped ceremony.
- NULL `source_id` for uploads — ruled out: it re-creates "upload is the default case plus a nullable column", which is what making upload an adapter is meant to end.
- Hide system-ingested documents from non-admins — ruled out: retrieval would still cite them, which is a worse failure than showing them.

### Decision 8: Integration profiles are typed, staged, control-plane, and defaults-only executable

**Choice:** One profile per tenant in `public`, with a closed per-adapter set of configuration keys and types, secret material only in declared reference fields matching a `<scheme>://<path>` grammar, a status model of `draft → validated → active → paused → error → retired`, and only the platform default adapters executable. Any other selection may be recorded but cannot be activated.

**Rationale:** ADR-001 puts tenant content in tenant schemas; a profile is platform configuration the platform must read even when a tenant's infrastructure is unreachable. A typed schema is what makes "no raw secrets" enforceable: a value is rejected because it fails a declared shape, not because a heuristic guessed it looked like a credential — heuristics both miss real secrets and reject innocent strings. `validated` exists so activation cannot precede a readiness check; `error` exists so an unresolvable reference degrades one tenant's configuration rather than an unrelated request path. Defaults-only execution is what keeps this change a foundation: the profile can express the target architecture without implying that any of it works yet.

**Alternatives considered:**
- Free-form JSONB configuration with credential-shaped-value detection — ruled out: unenforceable, and it invites exactly the leak the requirement exists to prevent.
- Profile rows in the tenant schema — ruled out: the platform could not read configuration for a tenant whose store is down, and adapter selection is not tenant content.
- Environment variables per tenant — ruled out: cannot express per-tenant selection without a deploy, and rotation would require one.

### Decision 9: Relational persistence gets a resolver seam, not a repository abstraction

**Choice:** Engine acquisition moves behind a single resolver that still returns today's process-global engine, and the ten copies of `_schema(tenant_id)` collapse into one shared helper. Nothing else.

**Rationale:** The derived-data layer does not merely use PostgreSQL — it writes it. `entity_views.py` generates `CREATE TABLE IF NOT EXISTS` and `ALTER TABLE … ADD COLUMN IF NOT EXISTS` at runtime from tenant entity definitions; `relational_projection.py` emits `ON CONFLICT … DO UPDATE SET … GREATEST(…)`; migration `011` creates four materialized views per tenant schema through `DO $$` loops; `024` adds a generated `tsvector` column and an HNSW index; `tenant_service.py` clones schemas via `pg_tables`; `sql_execution_role.py` creates a `NOLOGIN` role assumed with `SET LOCAL ROLE`. A vendor-neutral abstraction over that would need a DDL generator, an upsert generator, a view generator, and a privilege model per engine, and would deliver nothing until a non-PostgreSQL customer exists. The tenant-selectable version of this concern is *relocation* — the same schema and migrations pointed at a customer-managed PostgreSQL — which is connection routing, and belongs to `tenant-postgresql-data-plane`.

**Alternatives considered:**
- Repository interfaces per aggregate — ruled out as a large, risky refactor with no second implementation to validate it.
- Doing nothing at all — ruled out: the resolver is a two-line seam that makes the later change a substitution rather than a sweep of 44 call sites.

### Decision 10: Naming is reconciled once, across all four documents

**Choice:**

| Concept | Chosen term | Rejected | Note |
|---|---|---|---|
| Pull-side source port | `DocumentSource` | `SourceConnector` | `external-data-source-architecture.md` uses the rejected term and carries a reconciliation note. |
| Configured-source table | `document_sources` | `data_sources` | Narrower and still true now that structured-data connectors also exist. Created by `external-document-sources`. |
| `source_id` | Identifier of a configured document source within one tenant; reserved value `platform-upload` | `source_instance_id` | One term, one meaning, everywhere. |
| Stored bytes locator | `storage_reference` in the application contract | `blob_path` | `blob_path` names only the existing physical column until `document-metadata-column-reconciliation` renames it. |

**Rationale:** Three documents were written at different times and seeded two vocabularies for the same concepts. Left alone, the codebase inherits both. The rejected terms are annotated at the head of the documents that use them rather than by rewriting a 1 091-line design.

## Risks / Trade-offs

- [This change touches the platform's only document entry point; a regression breaks all ingestion] → Externally observable behaviour frozen: same URL, status codes, response body. The gate is that every existing case in `tests/test_document_ingestion.py` and `tests/test_document_content_hash.py` passes **unmodified**, evidenced by a clean `git diff` on both files.
- [Ephemeral retention writes bytes to platform storage, which a reader may mistake for "no retention means nothing is stored"] → Stated explicitly in the spec text, in the proposal, and as approval item A1. The working store is separately configured with an independent expiry so the guarantee does not depend on application correctness.
- [The working copy is deleted but the document row still names it, or is not deleted at all and accumulates] → Deletion is tied to reaching a terminal state and the reference is nulled in the same step; the store's own expiry is the backstop for an abandoned copy. Verified on both the success and failure paths.
- [Purge-before-resolve would destroy derived data when bytes are gone] → Ordering fixed in the spec: resolve, then purge. Verified by a scenario asserting spans and chunks survive an unresolvable reprocess.
- [Changing the OCR branch from key-parsing to media type could reroute real documents, e.g. a PDF uploaded as `application/octet-stream`] → Three-step resolution with the filename extension retained as fallback, which is exactly today's behaviour. Verified per resolution step, including the octet-stream case.
- [The `_schema` consolidation touches ten modules at once] → Pure mechanical substitution with identical output, landed as its own task before any behavioural work so a bisect separates it cleanly.
- [A recorded-but-unsupported adapter selection is mistaken for a supported one] → Activation is refused with a reason naming the unsupported selection, and ingestion always uses executable adapters regardless of what is recorded.
- [Integration profiles introduce credential handling before any credential exists] → Only reference storage, typed validation, and the resolution seam ship here; no live secret is resolved because every executable profile selects platform adapters.
- [`AGENTS.md` fail-fast-at-startup cannot apply to runtime-created per-tenant references] → Acknowledged deviation rather than a silent exception: absence surfaces at resolution time and moves the profile to `error` with an operator-visible message.
- [Provenance columns without a unique constraint permit duplicate external identities] → Accepted deliberately. Nothing writes an external identity until pull sources exist, and the ledger that owns uniqueness arrives with them.
- [Readiness asserts MinIO unconditionally, which becomes wrong for a `source_only` tenant] → Out of scope here because MinIO serves every executable profile, including the working store. Flagged so `external-document-sources` does not inherit a false probe.

## Migration Plan

Five steps, each independently landable and revertable.

1. **Hygiene, no behaviour change.** One shared `schema_for_tenant`; engine acquisition behind a resolver returning today's global engine. Full suite passes with no test edits.
2. **Content-store boundary.** Put, open, delete; MinIO adapter for the durable instance; working instance configured with an independent expiry.
3. **Ingestion seam.** Extract the use case; upload route becomes the adapter; content-acquisition declaration; retention resolution; dispatch by identity; media-type branch; conditional `processing` transition; resolve-then-purge.
4. **Schema and control plane.** Additive migration on `tenant_template.documents` plus the `DO $$` loop; the integration-profile table in `public`; profiles backfilled to platform defaults; visibility rule applied.
5. **Prove the lifecycle.** Ephemeral end to end against a real working store: ingest, OCR, spans, chunks, retrieval, working copy deleted, reference NULL, durable store untouched. Plus the retry and the expired-reprocess cases.

**Deployment:** migrations are additive and defaulted, so an older application version runs unchanged against the new schema. Deploy migrations first, then the application. The working store must exist and have its expiry policy configured before step 3 is enabled for any tenant.

**Rollback:** steps 1, 2, 3, and 5 revert by reverting code. Step 4's migration has a downgrade dropping the added columns and the profile table; because nothing reads them until step 5, rolling the application back without rolling the migration back is also safe.

**Ordering constraint:** step 3 must not be split across releases. A half-extracted use case with the route still writing storage directly would give `documents` two writers with different retention behaviour.

## Open Questions

No implementation-blocking design questions remain. Three items need human agreement rather than further design, and are carried in the proposal as A1–A3:

- **A1 — Working-store transit acceptability.** Under `ephemeral` retention the bytes transit platform-operated storage for the duration of processing. Requires product and security agreement before the first privacy-constrained tenant is onboarded.
- **A2 — Working-store expiry duration.** An operational value bounded below by the slowest realistic OCR run.
- **A3 — Tenant-wide visibility of system-ingested documents.** Decided here so listing and chat citation agree; confirm with product, since it widens what a `business_user` sees.

**ADRs to revisit:** none are contradicted. A new ADR recording the push/pull split, the three retention modes, and the deliberate decision to bound original-blob storage while *not* bounding relational or vector persistence would be warranted as an addition rather than a supersession.
