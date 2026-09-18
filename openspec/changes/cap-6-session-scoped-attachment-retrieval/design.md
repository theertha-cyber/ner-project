## Context

CAP-2 shipped the composer UX for staging files, CAP-3 shipped a `documents.conversation_id` column and an attachment-bearing turn contract, and CAP-4 extended the ingestion allow-list to `.csv`. What none of them did is connect an attachment's **content** to the answer.

Today `_persist_attachments` (`src/chat_api/api/v1/chat.py:113-131`) writes a `documents` row with `filename`, `mime_type`, `file_size_bytes` and `conversation_id` — and nothing else. There is no content-store write, no checksum, no `document_text_spans`, no `document_chunks`. That insert also bypasses `DocumentIngestionService`, whose module docstring states it is "The one code path permitted to create a `documents` row" (`src/document_service/ingestion/service.py:1`), so the row it writes is missing `checksum`, `blob_path`, `purpose`, `retention_mode`, `source_type` and every provenance column that the rest of the platform assumes present.

Retrieval is tenant-wide. `DenseRetriever` and `SparseRetriever` (`src/shared/retrieval/retriever.py:65-116`) filter `document_chunks` by tenant schema and `purpose = 'query'`; the only narrowing available is `metadata_filter`, reachable exclusively through the `scope` argument the LLM chooses (`src/shared/retrieval/tools/document_tools.py:14-32`). Migration 040's own docstring already asserts the intended rule — conversation-linked documents are "exactly what keeps them out of conversation-scoped retrieval" — but no code implements it.

There is a second retrieval channel. The relational path generates SQL over a whitelist that includes `document_chunks.chunk_text` and `documents.filename` (`src/chat_api/services/sql_generator.py:20-26`), so attachment text is reachable there too and needs the same rule.

The driving use case is HR screening: a recruiter opens a new session, attaches a job description, and asks the assistant to evaluate resumes (already in the tenant library) against it. That requires the JD to be indexed *and* to stay confined to its session.

## Goals / Non-Goals

**Goals:**

- Make a chat attachment's content genuinely retrievable: extracted, chunked, embedded, citable.
- Confine a conversation-owned document's content to its own conversation across **every** retrieval channel — vector, full-text, hybrid, and generated SQL.
- Keep tenant-library documents (no conversation owner) visible in every conversation, exactly as today.
- Make the confinement non-bypassable: not by user message text, not by a model-selected tool scope, not by a `metadata_filter`.
- Route attachments through the single sanctioned ingestion path so they carry the same provenance, checksum, retention and content-store guarantees as any other document.
- Let the turn that carries a JD be answered from that JD.
- Leave text-only chat sends byte-for-byte unchanged.

**Non-Goals:**

- PostgreSQL Row-Level Security. Considered and rejected below; it would change the security posture of every write path in the platform.
- NER entity extraction of chat attachments into `document_entities` / `extracted_entities`. Ingestion produces spans and chunks; extraction runs are a separate, explicitly triggered pipeline and stay out of scope.
- Sharing an attachment between conversations, moving one into the tenant library, or any cross-conversation promotion.
- Drag-and-drop, resumable upload, upload progress at the byte level, or any change to the accepted file set (CAP-4 settled it).
- Changing the Documents-library exclusion or the conversation hard-delete path — both already key off `documents.conversation_id` and `hard_delete_documents` already removes `document_chunks`, so they cover the new rows unchanged.

## Currently-In-Force ADRs

| ADR | Decision Summary | Constraint on This Design |
|-----|-----------------|--------------------------|
| ADR-001 | Per-tenant PostgreSQL schemas; isolation enforced at gateway, connection, ORM and storage layers | Conversation scoping is a second, narrower boundary *inside* a tenant schema. It must compose with tenant isolation, never replace or weaken it; every new predicate runs within the already tenant-scoped schema. |
| ADR-007 | Full RAG pipeline over three sources (structured SQL, pgvector document search, model inference), with guardrails including tenant-scoped data sources | Both the vector path and the SQL path are answer channels, so a scoping rule that covers only one of them is incomplete. The rule is a guardrail and must sit with the other non-bypassable guardrails, not in model-facing arguments. |
| ADR-011 | Chat attachments are conversation-owned `documents` rows; retrieval and deletion are conversation-scoped; deletion hard-deletes rows, spans, chunks and blobs | Directly governing. An attachment must be conversation-owned from the moment its row exists, its derived chunks must carry that ownership, and the retrieval half of the ADR — never implemented — is what this change delivers. |
| ADR-012 | CSV support is a branch in the existing ingestion pipeline | Routing attachments through `DocumentIngestionService` means CSV attachments get the CSV branch for free; no CSV-specific handling belongs in the chat path. |
| ADR-013 | Single-environment dev/local deployment via docker compose with recreate rollout | The migration must be a forward-only Alembic revision applied by the existing startup path; no blue/green or dual-write staging is available. |

## Decisions

### Decision 1: Attachment-bearing turns are `multipart/form-data`; text-only turns stay JSON

**Choice:** The chat routes read `Content-Type`. A JSON request is parsed into the existing `ChatRequest` exactly as today. A `multipart/form-data` request supplies the message and conversation id as form fields and the files as upload parts. CAP-3's metadata-only `AttachmentInput` array leaves the send contract.

**Rationale:** The content has to arrive for any of this to work, and file bytes belong in a multipart body. Branching inside the existing routes — rather than adding parallel endpoints — means the portal keeps one URL per path, and a text-only send takes the identical code path it takes today, so every archived CAP-2/CAP-3 test remains valid without modification. Metadata-only attachments were never more than a placeholder: a `filename` and a `file_size_bytes` cannot be retrieved against.

**Alternatives considered:**
- Base64 the content into the existing JSON body — ruled out: a 33% size penalty on a path already bounded at 50MB, and it holds the whole file in memory as a string before decoding.
- Separate upload endpoint called before the send, with the turn referencing returned document ids — ruled out: it creates a window in which an ingested attachment exists with no conversation owner. Those rows would be indexed and, having a null `conversation_id`, would be indistinguishable from tenant-library content and therefore retrievable from every conversation. Closing that hole needs a staging flag, an adoption step, and an orphan-cleanup job — three mechanisms to solve a problem the single-request design does not have.
- Parallel `/chat/multipart` endpoints — ruled out: duplicates the conversation-resolution, streaming, persistence and guardrail logic of two already-large handlers.

### Decision 2: Attachments are ingested through `DocumentIngestionService`, which gains `conversation_id`

**Choice:** `_persist_attachments` is deleted. The chat turn builds a `NormalizedDocument` per file and calls `DocumentIngestionService.ingest()`. `NormalizedDocument` gains a `conversation_id: str | None` field, which `_insert_row` writes into the `documents` row. The source is the reserved `platform_upload` source with `ContentAcquisition.SINGLE_USE`, `purpose='query'`, and the actor is the authenticated human user.

**Rationale:** The ingestion service is documented as the only sanctioned creator of `documents` rows, and `tests/test_ingestion_boundary.py` exists to enforce that boundary. CAP-3's direct insert was already a violation; fixing it here is cheaper than building a second, parallel document-creation path that would need its own checksum, retention, content-store and dispatch logic. Putting `conversation_id` on `NormalizedDocument` rather than passing it around the worker means ownership is set in the same statement that creates the row — there is no window where the row exists unowned.

**Alternatives considered:**
- Keep the direct insert and add a content-store write beside it — ruled out: duplicates ingestion's responsibilities and re-breaks the boundary the test guards.
- Set `conversation_id` in a follow-up `UPDATE` after ingest returns — ruled out: between the insert and the update the row is unowned, and the processing dispatch may already have written chunks that inherit the wrong (null) ownership.

### Decision 3: `document_chunks` carries a denormalized `conversation_id`

**Choice:** Add a nullable `conversation_id` to `document_chunks`, written by the processing worker from the parent document, exactly as `purpose` already is (`src/document_service/services/ocr_worker.py:32-46`). Retrieval filters on the chunk column; it never joins `documents`.

**Rationale:** `purpose` established this pattern for precisely this reason — the retrieval SQL is a hot path with an `hnsw` index scan and an `ORDER BY` on a vector distance, and introducing a join to `documents` to resolve ownership would sit between the index and the ranking. Denormalization keeps the predicate a plain indexed column comparison. It also keeps the filter expressible inside the SQL-path inline views of Decision 5, which rewrite a single table reference and have no join to add to.

**Alternatives considered:**
- Join `document_chunks` to `documents` in the retriever — ruled out: cost on the hot path, and it cannot be expressed in the single-table inline-view rewrite the SQL path needs.
- A separate `conversation_chunks` association table — ruled out: a second source of truth for a fact the document already owns, and it would need its own cleanup in the hard-delete path.

### Decision 4: The conversation predicate is mandatory and comes from request context

**Choice:** `Retriever.retrieve` gains a `conversation_id` parameter supplied by the caller's authenticated context, carried on `ToolContext`. Every implementation appends `AND (conversation_id IS NULL OR conversation_id = :conversation_id)` — and, when no conversation is supplied, `AND conversation_id IS NULL`. It is a sibling of the existing `purpose = 'query'` restriction: outside `metadata_filter`, unreachable from tool arguments, and not removable by any caller.

**Rationale:** This is the isolation guarantee, so it cannot depend on the model choosing to pass a scope — an LLM that omits, forgets, or is talked out of a `scope` argument would silently leak one session's JD into another. The existing spec already words the `purpose` rule as "SHALL NOT be optional or controllable by the caller" and there is already a scenario asserting a chat query cannot bypass it; conversation scoping gets the same treatment and the same shape of test. Keeping it out of `metadata_filter` matters because `metadata_filter` is derived from `scope`, which is model-controlled: a mechanism that can only narrow is safe to expose, and one that could widen is not.

**Alternatives considered:**
- Express it as a `metadata_filter` entry — ruled out: `metadata_filter` is populated from the model-chosen `scope`, so the guarantee would live in model-controlled data.
- Add a `conversation` scope type to the `semantic_retrieval` tool — ruled out: same failure mode. A scope the model may omit is not a boundary. The tool's `scope` keeps its current meaning — narrowing *within* what is already visible.
- PostgreSQL Row-Level Security with a per-transaction `current_setting` — genuinely attractive, since it would cover both channels with no per-query predicate. Ruled out here: RLS applies to every statement against `documents` and `document_chunks`, including ingestion's own writes, the extraction pipeline, analytics and the hard-delete path, so adopting it is a platform-wide security-posture change that needs its own change and its own ADR. Recorded under Open Questions.

### Decision 5: The SQL path is scoped by reusing the existing inline-view rewrite

**Choice:** Add `apply_conversation_scope(sql, conversation_id)` alongside `apply_document_scope` (`src/chat_api/services/sql_generator.py:644-686`), rewriting every reference to a conversation-bearing whitelisted table into an inline view: `FROM document_chunks c` → `FROM (SELECT * FROM document_chunks WHERE conversation_id IS NULL OR conversation_id = :conv) c`. It runs unconditionally on every validated statement, after validation and before execution.

**Rationale:** `documents` and `document_chunks` are both whitelisted with content-bearing columns (`filename`, `chunk_text`), so the relational path is a real second channel for the same leak and a rule applied only to the vector path would be theatre. The inline-view mechanism already exists, is already trusted for a security-relevant constraint, and its docstring records exactly why this shape was chosen: the scope "survives aggregation, grouping, and `LIMIT`", unlike a post-execution row filter or a natural-language instruction to the generating model. Reusing it means no new rewriting machinery and no second correctness argument.

**Alternatives considered:**
- Append a `WHERE` clause to the generated statement — ruled out for the reason its own docstring gives: it does not survive aggregation, subqueries or `LIMIT`.
- Filter rows after execution — ruled out: `LIMIT 100` runs first, so a truncated result becomes a wrongly empty one.
- Remove `document_chunks` and `documents` from the SQL whitelist — ruled out: it would break existing relational answers that legitimately query library documents.

### Decision 6: Attachment processing is awaited, with a bounded wait and honest degradation

**Choice:** After ingesting, the turn awaits each attachment reaching `processed` (spans, chunks and embeddings written) before retrieval runs, bounded by a timeout. An attachment that fails or exceeds the bound does not fail the turn: the answer proceeds without it and the response states that the attachment was not available.

**Rationale:** `InProcessDispatcher` fires `asyncio.create_task(process_document(...))` and returns immediately (`src/document_service/ingestion/dispatcher.py:21-26`). Left alone, the first turn's retrieval would race the embedding write and almost always lose — the JD would appear to be ignored, which is precisely the reported symptom this change exists to remove. Awaiting is what makes "attach a JD and ask about it in one message" work at all. The bound and the fallback exist because a large scanned PDF can take longer than a user will wait, and a turn that hangs or that silently answers from nothing is worse than one that says the attachment was not ready.

**Alternatives considered:**
- Fire-and-forget, and let the *next* turn see the attachment — ruled out: it makes the natural interaction (attach and ask in one message) quietly wrong.
- Block indefinitely until processing completes — ruled out: an OCR-heavy document would hold the request open past any gateway timeout with no user-visible explanation.
- Answer optimistically and retro-correct — ruled out: it would emit a cited answer built without the document the user just supplied.

## Risks / Trade-offs

- [Inline processing adds the attachment's extraction and embedding time to the first turn's latency] → Bounded by Decision 6's wait and by the existing 50MB ingestion cap; the expected payload (a job description) is small, and degradation is explicit rather than silent.
- [`multipart/form-data` on the streaming endpoint is a contract change for any non-portal caller sending attachments] → The only shipped caller is the portal, the metadata-only contract it replaces could not retrieve anything, and text-only JSON sends are untouched, so the blast radius is limited to attachment-bearing calls that previously had no working behaviour. Marked **BREAKING** in the proposal.
- [Chunks written before migration 041 have a null `conversation_id` and stay visible everywhere] → Correct by construction: every pre-existing chunk belongs to a tenant-library document, which is exactly the content that should remain visible in every conversation. Asserted by a scenario.
- [A tenant whose integration profile sets `source_only` retention will have chat attachments rejected, because a browser upload is `SINGLE_USE` and `_resolve_retention` raises `IncompatibleRetention`] → Pre-existing platform behaviour, now reachable from chat; surface it as a clear client error naming the retention conflict rather than a 500.
- [The SQL rewrite must cover every whitelisted table that can expose attachment content, and a future whitelist addition could silently escape it] → The scope-column map is defined next to the whitelist, and a test asserts every whitelisted table carrying a `conversation_id` column is present in it.
- [Attaching the same file to two conversations creates two document rows, since `_find_duplicate` identifies duplicates without merging them] → Intended: shared rows could not carry two owners, and merging would break the hard-delete guarantee. Storage cost is accepted.
- [Conversation scoping and tenant scoping could be confused, and a regression in one might be masked by the other] → Tests assert the conversation rule inside a single tenant schema, so a passing conversation test cannot be satisfied by tenant isolation alone.

## Migration Plan

1. Alembic revision `041` adds `document_chunks.conversation_id` (nullable `VARCHAR`) to `tenant_template` and to every already-provisioned `tenant_%` schema, following the loop-with-`to_regclass`-guard shape of migrations 022, 034 and 040. Nullable with no backfill: existing chunks are library content and null is their correct value. No foreign key on the chunk column — ownership is already enforced by `documents.conversation_id`'s FK, and a second cascade path would complicate `hard_delete_documents`.
2. Deploy backend and portal together via the ADR-013 docker compose recreate. The ordering constraint is only that the migration precedes the new retriever SQL; an old portal against a new backend still works, because text-only JSON sends are unchanged and the composer's previous metadata-only send is the one path that changes shape.
3. Rollback is `alembic downgrade` of `041` plus a revert of the service images. Dropping the column returns retrieval to tenant-wide behaviour; no data is lost, because attachment documents, spans and chunks remain and simply become library-visible again until the column returns.

## Open Questions

- None blocking implementation.
- For a future change, not this one: whether conversation scoping should migrate to PostgreSQL Row-Level Security so that every current and future query path inherits it without per-call-site enforcement. That would supersede the enforcement mechanism chosen in Decisions 4 and 5 — though not ADR-011's ownership model — and belongs in its own change with its own ADR, since it alters the security posture of every write path in the platform. No in-force ADR needs revisiting for the design as specified here.
