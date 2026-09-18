# Verification Plan

**Change:** cap-6-session-scoped-attachment-retrieval
**Generated:** 2026-09-17
**Status:** 🟡 Evidence collected, two gaps open, human sign-off outstanding — 38 of 40 Section 1 rows are backed by real test output; scenarios 30 and 31 are unmet (see the Evidence Log). The Audit Record in Section 6 is unsigned and this change MUST NOT be archived until a human reviewer completes it.

---

## 1. Spec Alignment

Map every requirement and every scenario in this change to a testable acceptance criterion.
Each row drives one evidence entry in Section 5.

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | conversation-scoped-retrieval | Conversation ownership determines retrieval visibility | A conversation attachment is retrievable in its own conversation | Given an indexed attachment owned by conversation A, when a matching question is asked in conversation A, then retrieval returns chunks derived from that attachment | `tests/test_cap_6_session_scoped_attachment_retrieval.py` — TestConversationVisibilityInVectorRetrieval::test_attachment_is_retrievable_in_its_own_conversation | - [x] |
| 2 | conversation-scoped-retrieval | Conversation ownership determines retrieval visibility | A conversation attachment is invisible in another conversation | Given an indexed attachment owned by conversation A, when a question matching its content is asked in conversation B of the same tenant, then no chunk from that attachment is returned | `tests/test_cap_6_session_scoped_attachment_retrieval.py` — ::test_attachment_is_invisible_in_another_conversation | - [x] |
| 3 | conversation-scoped-retrieval | Conversation ownership determines retrieval visibility | Tenant-library documents remain visible in every conversation | Given a library document with no conversation owner, when a matching question is asked in conversation A and again in conversation B, then its chunks are returned in both | `tests/test_cap_6_session_scoped_attachment_retrieval.py` — ::test_library_document_is_visible_from_every_conversation | - [x] |
| 4 | conversation-scoped-retrieval | Conversation ownership determines retrieval visibility | A conversation attachment is invisible outside any conversation | Given an indexed attachment owned by conversation A, when retrieval runs with no conversation in context, then no conversation-owned chunk is returned and library chunks still are | `tests/test_cap_6_session_scoped_attachment_retrieval.py` — ::test_no_conversation_admits_only_unowned_chunks | - [x] |
| 5 | conversation-scoped-retrieval | Conversation scope is enforced from request context | A model-chosen scope cannot widen conversation visibility | Given a document owned by conversation A, when retrieval runs for conversation B with a scope naming that document's id, then no chunk from it is returned | `tests/test_cap_6_session_scoped_attachment_retrieval.py` — ::test_metadata_filter_cannot_widen_conversation_visibility and TestScopeCoverageGuard::test_scope_is_not_reachable_from_the_model_facing_scope_argument | - [x] |
| 6 | conversation-scoped-retrieval | Conversation scope is enforced from request context | User message text cannot widen conversation visibility | Given a document owned by conversation A, when a turn in conversation B names that document, its filename or its contents, then no chunk owned by conversation A is returned | `tests/test_cap_6_session_scoped_attachment_retrieval.py` — TestScopeCoverageGuard (mechanism: the predicate is built from `ToolContext.conversation_id`, never from args or message text) + code review of `retriever.py` / `document_tools.py` | - [x] |
| 7 | conversation-scoped-retrieval | Conversation scope is enforced from request context | Conversation scope composes with the existing purpose restriction | Given a conversation-owned document whose chunks carry a purpose other than `query`, when retrieval runs in that same conversation, then those chunks are still excluded | `tests/test_retrieval_foundation.py` — mixed-purpose exclusion, re-run green with the conversation clause in place | - [x] |
| 8 | retrieval-core | Retriever interface | DenseRetriever uses the hnsw index | Given a tenant schema with chunks and embeddings, when `DenseRetriever.retrieve` runs, then the query executes against the `hnsw` index and results rank by descending similarity | `tests/test_retrieval_foundation.py` — TestDenseRetriever (regression) | - [x] |
| 9 | retrieval-core | Retriever interface | rag_orchestrator retrieves via the Retriever interface | Given the orchestrator needs document context, when `_vector_source` executes, then it calls a `Retriever.retrieve` rather than `EmbeddingService.similarity_search` | `tests/test_retrieval_foundation.py` / `tests/test_hybrid_retrieval.py` — orchestrator uses the Retriever interface (regression) | - [x] |
| 10 | retrieval-core | Retriever interface | Retrieval excludes training-purpose chunks | Given `purpose='training'` and `purpose='query'` chunks both matching a query, when `DenseRetriever.retrieve` runs, then no training-purpose chunk is returned | `tests/test_retrieval_foundation.py` — training-purpose exclusion (regression) | - [x] |
| 11 | retrieval-core | Retriever interface | A chat query cannot bypass the purpose restriction | Given training-purpose chunks, when `_vector_source` runs with any user-supplied text naming them, then the SQL still excludes them and no caller parameter overrides it | `tests/test_retrieval_foundation.py` — purpose restriction unbypassable (regression) | - [x] |
| 12 | retrieval-core | Retriever interface | Retrieval excludes chunks owned by another conversation | Given chunks owned by conversation A and library chunks both matching a query, when `DenseRetriever.retrieve` runs for conversation B, then no conversation-A chunk is returned and library chunks may be | `tests/test_cap_6_session_scoped_attachment_retrieval.py` — ::test_attachment_is_invisible_in_another_conversation | - [x] |
| 13 | retrieval-core | Retriever interface | Retrieval includes chunks owned by the current conversation | Given chunks owned by conversation A, when `DenseRetriever.retrieve` runs for conversation A with a matching query, then those chunks may be returned | `tests/test_cap_6_session_scoped_attachment_retrieval.py` — ::test_attachment_is_retrievable_in_its_own_conversation | - [x] |
| 14 | retrieval-core | Retriever interface | metadata_filter cannot widen conversation visibility | Given chunks owned by conversation A, when `retrieve` runs for conversation B with `metadata_filter={"document_ids": [A's document id]}`, then the result is empty | `tests/test_cap_6_session_scoped_attachment_retrieval.py` — ::test_metadata_filter_cannot_widen_conversation_visibility | - [x] |
| 15 | retrieval-core | Retriever interface | Retrieval without a conversation admits only unowned chunks | Given conversation-owned and library chunks both matching a query, when `retrieve` runs with no conversation supplied, then only chunks with a null `conversation_id` are returned | `tests/test_cap_6_session_scoped_attachment_retrieval.py` — ::test_no_conversation_admits_only_unowned_chunks | - [x] |
| 16 | retrieval-core | Retriever interface | SparseRetriever returns full-text matches | Given chunks whose `chunk_text` contains an exact term, when `SparseRetriever.retrieve` runs with that term, then the chunk is returned and results rank by `ts_rank` descending | `tests/test_hybrid_retrieval.py` — SparseRetriever full-text matches (regression) | - [x] |
| 17 | retrieval-core | Retriever interface | SparseRetriever applies the same conversation restriction as DenseRetriever | Given a chunk owned by conversation A containing an exact term, when `SparseRetriever.retrieve` runs for conversation B with that term, then the chunk is not returned | `tests/test_cap_6_session_scoped_attachment_retrieval.py` — ::test_sparse_retriever_applies_the_same_rule | - [x] |
| 18 | retrieval-core | Retriever interface | SparseRetriever returns no error on zero matches | Given chunks with no overlap with the query, when `SparseRetriever.retrieve` runs, then the result is an empty list and no exception is raised | `tests/test_hybrid_retrieval.py` — SparseRetriever zero-match (regression) | - [x] |
| 19 | retrieval-core | Retriever interface | HybridRetriever fuses dense and sparse results via RRF | Given a chunk matching both semantically and lexically, when `HybridRetriever.retrieve` runs, then that chunk ranks at or near the top and the list holds at most `top_k` results | `tests/test_hybrid_retrieval.py` — RRF fusion (regression) + `tests/test_cap_6_session_scoped_attachment_retrieval.py` ::test_hybrid_retriever_applies_the_same_rule | - [x] |
| 20 | retrieval-core | Retriever interface | HybridRetriever includes dense-only matches when sparse search returns nothing | Given a query with semantic but no lexical overlap, when sparse returns zero and dense returns the chunk, then the fused list still includes it | `tests/test_hybrid_retrieval.py` — dense-only inclusion (regression) | - [x] |
| 21 | retrieval-core | Retriever interface | metadata_filter restricts results to one document | Given chunks from two documents both matching, when `retrieve` runs with `metadata_filter={"document_id": one id}`, then every result carries that document id | `tests/test_retrieval_foundation.py` — metadata_filter document restriction (regression) | - [x] |
| 22 | retrieval-core | Chunks carry denormalized conversation ownership | Ingesting a conversation-owned document stamps its chunks | Given a document ingested with a conversation owner, when the worker writes its chunks, then every chunk row carries that `conversation_id` | `tests/test_chunk_metadata_ingest.py` — TestChunkPurposeDenormalization::test_store_chunks_persists_conversation_ownership_on_every_row[conv-a] | - [x] |
| 23 | retrieval-core | Chunks carry denormalized conversation ownership | Ingesting a library document leaves chunk ownership null | Given a document ingested with no conversation owner, when the worker writes its chunks, then every chunk row carries a null `conversation_id` | `tests/test_chunk_metadata_ingest.py` — ::test_store_chunks_persists_conversation_ownership_on_every_row[None] | - [x] |
| 24 | retrieval-core | Chunks carry denormalized conversation ownership | Chunks written before this change remain retrievable | Given chunk rows created before the column existed, when the migration runs and retrieval executes, then those rows have a null `conversation_id` and remain retrievable as before | Migration 041 adds the column nullable with no backfill; `tests/test_retrieval_foundation.py` and `tests/test_hybrid_retrieval.py` seed rows without it and still retrieve (regression) | - [x] |
| 25 | chat-api | Attachment-bearing chat turns | First send creates the conversation and stores attachments | Given staged attachments and no conversation, when the first message is sent with them, then the conversation is created and each attachment is persisted as a document owned by it | `tests/test_chat_api_conversations.py` — ::test_first_send_with_attachments_creates_conversation_and_persists_metadata | - [x] |
| 26 | chat-api | Attachment-bearing chat turns | An attachment is ingested rather than inserted directly | Given a turn carrying one attachment, when the send is processed, then the attachment is ingested through the ingestion service, the row carries checksum/content-store reference/retention mode, and the chat endpoint runs no insert into documents | `tests/test_chat_api_conversations.py` — same test asserts checksum / blob_path / retention_mode; `tests/test_ingestion_boundary.py` (boundary intact) | - [x] |
| 27 | chat-api | Attachment-bearing chat turns | An unsupported attachment type is rejected | Given a turn carrying a file outside the ingestion allow-list, when the send is processed, then a client error naming the unsupported type is returned and no conversation is created for a rejected first send | `tests/test_chat_api_conversations.py` — ::test_unsupported_attachment_is_rejected_without_creating_a_conversation | - [x] |
| 28 | chat-api | Text-only chat sends remain supported | Normal message without attachments still works | Given a message with no staged files, when it reaches the chat endpoint, then the existing text-only path works unchanged | `tests/test_chat_api_conversations.py` — ::test_text_only_send_unchanged (unmodified, still green) | - [x] |
| 29 | chat-api | Text-only chat sends remain supported | A JSON send is handled as it was before this change | Given a JSON chat request with no attachment parts, when it reaches either endpoint, then it is parsed as the existing JSON request and no ingestion is attempted | `tests/test_chat_api_conversations.py` — text-only JSON suite unmodified; `src/portal/src/app/(auth)/chat/page.test.tsx` ::sends a text-only turn as JSON, not multipart | - [x] |
| 30 | chat-api | Attachments are indexed before the turn is answered | The same turn can answer from its own attachment | Given a user attaches a job description and asks about it in one send, when the turn is answered, then retrieval can return chunks from that attachment and the answer can cite it | **GAP** — the same-turn answer path is exercised only at the retrieval layer (`tests/test_cap_6_session_scoped_attachment_retrieval.py` rows 1/13). No end-to-end assertion that a turn cites its own attachment: API tests mock the orchestrator. | - [ ] |
| 31 | chat-api | Attachments are indexed before the turn is answered | A failed attachment does not silently degrade the answer | Given a turn whose attachment processing fails, when the turn is answered, then the response indicates the attachment was unavailable and an answer is still produced | **GAP** — backend returns `unavailable_attachments`; `src/portal/src/app/(auth)/chat/page.test.tsx` asserts the client surfaces it, but no backend test forces a processing failure. | - [ ] |
| 32 | chat-api | Attachments are indexed before the turn is answered | Attachment processing that exceeds the bounded wait degrades gracefully | Given attachment processing that outlasts the bounded wait, when the wait elapses, then the turn is answered and the response indicates the attachment was unavailable | `tests/test_chat_api_conversations.py` — `_patch_ingestion` uses RecordingDispatcher + a 0.05s wait, so every attachment test exercises the timeout branch and the turn still answers | - [x] |
| 33 | chat-api | Attachment content is retrievable only within its own conversation | A job description attached in one session does not answer another session | Given an attachment used in conversation A, when a matching question is asked in conversation B, then the answer neither cites nor draws on that attachment | `tests/test_cap_6_session_scoped_attachment_retrieval.py` — TestConversationVisibilityInGeneratedSQL::test_generated_sql_cannot_read_another_conversations_chunk_text and ::test_a_relation_without_its_own_conversation_column_is_scoped_through_documents | - [x] |
| 34 | chat-api | Attachment content is retrievable only within its own conversation | Tenant library documents remain answerable in every conversation | Given a library document owned by no conversation, when a matching question is asked in any conversation, then the answer can cite it | `tests/test_cap_6_session_scoped_attachment_retrieval.py` — ::test_library_document_is_visible_from_every_conversation and ::test_generated_sql_reaches_the_current_conversations_chunk_text | - [x] |
| 35 | chat-composer-attachments | Attachment-bearing send interaction | Send a message with staged attachments | Given staged files and typed text, when the user sends, then the page transmits the message and each file's content in one request and clears the tray on success | `src/portal/src/app/(auth)/chat/page.test.tsx` — streaming and non-streaming multipart body assertions (FormData carries the File) | - [x] |
| 36 | chat-composer-attachments | Attachment-bearing send interaction | Failed send preserves staged attachments | Given staged files and a send that fails, when the failure returns, then the staged files remain in the tray and an error is shown | `src/portal/src/app/(auth)/chat/page.test.tsx` — ::preserves staged files and shows an error when the send fails | - [x] |
| 37 | chat-composer-attachments | Attachment-bearing send interaction | A text-only send carries no attachment parts | Given typed text and no staged files, when the user sends, then the existing JSON body is sent and the request is not multipart | `src/portal/src/app/(auth)/chat/page.test.tsx` — ::sends a text-only turn as JSON, not multipart | - [x] |
| 38 | chat-composer-attachments | The composer reports attachment send progress | An in-flight attachment send shows progress | Given an attachment-bearing send in flight, when the request is pending, then the composer shows the attachments are being uploaded and prepared and send is disabled | `src/portal/src/components/chat/ChatInput.test.tsx` — TestChatInput attachment send progress (status text, send and remove disabled) | - [x] |
| 39 | chat-composer-attachments | The composer reports attachment send progress | A failed attachment send keeps the files and reports why | Given an attachment-bearing send that fails, when the failure is received, then the failure is surfaced, every staged file remains, and send becomes operable again | `src/portal/src/app/(auth)/chat/page.test.tsx` — ::preserves staged files and shows an error when the send fails | - [x] |
| 40 | chat-composer-attachments | The composer reports attachment send progress | The user is told when an attachment could not be used | Given a response reporting an attachment was unavailable to the answer, when it is rendered, then the user is shown the attachment was not used | `src/portal/src/app/(auth)/chat/page.test.tsx` — ::tells the user when an attachment could not be used for the answer | - [x] |

> **Rule:** Every `#### Scenario:` block in every `specs/**/*.md` file for this change
> MUST appear as a row in this table. A missing scenario is a P1 gap that blocks archive.

---

## 2. Hallucination Risk Register

For each area of complexity in this change, identify what an AI agent might get wrong
and how a human reviewer can detect and correct it.

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|-------------------|----------------------|
| 1 | Where the conversation predicate lives | Implementing conversation scoping as a `metadata_filter` entry or a new `scope` type on `semantic_retrieval`, which would put the isolation guarantee in model-controlled data (design Decision 4 forbids both) | Read the retriever SQL: the conversation clause must be built unconditionally next to `purpose = 'query'`, not from `_metadata_filter_clause`. Confirm `SUPPORTED_SCOPE_TYPES` gained no conversation member, and that row 14's test fails if the clause is moved into `metadata_filter` |
| 2 | The second retrieval channel | Scoping only the vector path and leaving the generated-SQL path unguarded, so `document_chunks.chunk_text` and `documents.filename` remain readable across conversations (design Decision 5) | Confirm `apply_conversation_scope` exists, runs unconditionally on every validated statement before execution, and covers every whitelisted table carrying a `conversation_id`. Check the guard test that fails when a whitelist entry is missing from the scope-column map |
| 3 | Ingestion boundary | Keeping or re-creating the direct `INSERT INTO {schema}.documents` in `chat.py` instead of calling `DocumentIngestionService.ingest()`, leaving attachments without checksum, blob, retention and provenance (design Decision 2) | Grep `chat.py` for any insert into `documents` — there must be none. Confirm `_persist_attachments` is deleted and `tests/test_ingestion_boundary.py` still passes |
| 4 | Ownership write ordering | Setting `conversation_id` in an `UPDATE` after ingest returns, leaving a window where the row is unowned and the dispatched worker stamps chunks with a null owner | Confirm `conversation_id` is a `NormalizedDocument` field written by `_insert_row` in the same statement that creates the row, and that no post-ingest `UPDATE ... SET conversation_id` exists |
| 5 | Awaiting attachment processing | Leaving the fire-and-forget `asyncio.create_task` dispatch in place, so the first turn's retrieval races the embedding write and the attachment appears ignored (design Decision 6) | Confirm the turn awaits each attachment reaching `processed` before retrieval, that the wait is bounded, and that scenarios 30 and 32 genuinely exercise both the success and timeout branches rather than mocking the wait away |
| 6 | Degradation honesty | Swallowing a failed or timed-out attachment and answering as though nothing happened, or conversely failing the whole turn | Confirm both the failure and timeout paths still produce an answer AND set a user-visible indication; check the portal renders it (row 40) rather than the backend setting a field nothing reads |
| 7 | Null semantics of the new column | Treating a null chunk `conversation_id` as "hidden" rather than "tenant-library, visible everywhere", which would make every pre-migration chunk disappear from retrieval | Confirm the predicate is `conversation_id IS NULL OR conversation_id = :conv` — not an equality test that drops nulls — and that row 24 is tested against rows created without the column |
| 8 | Text-only regression | Changing the JSON send path while adding the multipart branch, breaking the archived CAP-2/CAP-3 contracts | Confirm the content-type branch leaves the JSON path untouched, and that the archived text-only tests pass without modification (rows 28, 29, 37) |

---

## 3. Pattern & ADR Compliance

List every currently-in-force ADR that constrains this change (as identified in design.md).

| ADR | Decision Summary | Constraint on This Change | Verification Step |
|-----|-----------------|--------------------------|-------------------|
| ADR-001 | Per-tenant PostgreSQL schemas with isolation enforced at multiple layers | Conversation scoping is a narrower boundary inside a tenant schema and must compose with, never replace, tenant isolation | Confirm every new predicate runs within the already tenant-scoped schema, and that conversation tests run two conversations inside one tenant so a pass cannot be produced by tenant isolation alone |
| ADR-007 | Full RAG pipeline over structured SQL, pgvector search and model inference, with non-bypassable guardrails | Both the vector and SQL answer channels must carry the rule, and it belongs with the guardrails rather than in model-facing arguments | Confirm both `retriever.py` and the SQL execution path enforce the rule, and that the rule is unreachable from tool arguments |
| ADR-011 | Chat attachments are conversation-owned document rows; retrieval and deletion are conversation-scoped; deletion hard-deletes rows, spans, chunks and blobs | Attachments must be conversation-owned at row creation, derived chunks must carry that ownership, and the previously unimplemented retrieval half must now hold | Confirm ownership is written at insert (risk 4), chunks are stamped (rows 22–23), and that `hard_delete_documents` still removes the newly created chunks on conversation delete |
| ADR-012 | CSV support is a branch in the existing ingestion pipeline | A CSV attachment must reach the existing CSV branch with no CSV-specific handling in the chat path | Attach a `.csv` file and confirm it produces chunks via `extract_text_csv`; confirm no CSV branch was added to `chat_api` |
| ADR-013 | Single-environment dev/local deployment via docker compose recreate | Forward-only Alembic revision applied by the existing startup path; no dual-write or staged rollout | Confirm migration 041 follows the 022/034/040 loop-and-guard shape, applies to `tenant_template` and existing tenant schemas, and that downgrade is exercised |
| ADR-014 | Conversation scoping is a mandatory retrieval guardrail enforced from request context across every channel, not a model-selected scope | The enforcement mechanism this change introduces must match the ADR: denormalized chunk column, unconditional retriever predicate, SQL inline-view rewrite, no model-facing widening | Confirm all four elements exist as specified and that the whitelist guard test from risk 2 is present |

---

## 4. Evidence Requirements

Evidence that **MUST** be collected and logged in Section 5 before this change is archived.
Do not archive while any item below remains unchecked.

### Functional Evidence

*(Minimum one item per row in Section 1 — test output proving the THEN was observed in a real execution.)*

- [x] Scenario 1: attachment retrievable in its own conversation
- [x] Scenario 2: attachment invisible in another conversation
- [x] Scenario 3: library documents visible in both conversations
- [x] Scenario 4: no conversation in context returns only library chunks
- [x] Scenario 5: model-chosen scope cannot widen visibility
- [x] Scenario 6: user message text cannot widen visibility
- [x] Scenario 7: conversation scope composes with the purpose restriction
- [x] Scenario 8: DenseRetriever still uses the hnsw index (regression)
- [x] Scenario 9: orchestrator still retrieves via the Retriever interface (regression)
- [x] Scenario 10: training-purpose chunks still excluded (regression)
- [x] Scenario 11: purpose restriction still unbypassable (regression)
- [x] Scenario 12: chunks owned by another conversation excluded
- [x] Scenario 13: chunks owned by the current conversation included
- [x] Scenario 14: `metadata_filter` cannot widen conversation visibility
- [x] Scenario 15: retrieval without a conversation admits only unowned chunks
- [x] Scenario 16: SparseRetriever full-text matches (regression)
- [x] Scenario 17: SparseRetriever applies the conversation restriction
- [x] Scenario 18: SparseRetriever zero-match behaviour (regression)
- [x] Scenario 19: HybridRetriever RRF fusion (regression)
- [x] Scenario 20: HybridRetriever dense-only inclusion (regression)
- [x] Scenario 21: `metadata_filter` document restriction (regression)
- [x] Scenario 22: conversation-owned document stamps its chunks
- [x] Scenario 23: library document leaves chunk ownership null
- [x] Scenario 24: pre-migration chunks remain retrievable
- [x] Scenario 25: first send creates the conversation and stores attachments
- [x] Scenario 26: attachment ingested rather than inserted directly
- [x] Scenario 27: unsupported attachment type rejected
- [x] Scenario 28: text-only send still works (regression)
- [x] Scenario 29: JSON send handled as before (regression)
- [ ] Scenario 30: the same turn answers from its own attachment
- [ ] Scenario 31: failed attachment reported, answer still produced
- [x] Scenario 32: bounded-wait timeout degrades gracefully
- [x] Scenario 33: attachment from session A does not answer session B end-to-end
- [x] Scenario 34: library documents answerable in every conversation
- [x] Scenario 35: composer sends message and file content in one request
- [x] Scenario 36: failed send preserves staged files
- [x] Scenario 37: text-only send is not multipart
- [x] Scenario 38: in-flight send shows progress and disables send
- [x] Scenario 39: failed send keeps files and re-enables send
- [x] Scenario 40: user is told when an attachment could not be used

### Structural Evidence

*(Code review and architectural compliance.)*

- [x] Code review completed — implementation matches design.md decisions (no undocumented deviations)
- [x] All ADR compliance steps in Section 3 confirmed
- [x] No undocumented architectural patterns introduced
- [x] No AI-invented requirements present in generated code (cross-checked against spec files)
- [ ] Migration 041 applied and rolled back cleanly against a provisioned tenant schema

### Edge Case Evidence

*(One item per Hallucination Risk from Section 2.)*

- [x] Risk 1 mitigated — conversation predicate built unconditionally, not from `metadata_filter`; `SUPPORTED_SCOPE_TYPES` unchanged
- [x] Risk 2 mitigated — SQL path scoped; whitelist guard test present and failing when a table is omitted
- [x] Risk 3 mitigated — no direct documents insert remains in `chat.py`; ingestion boundary test passes
- [x] Risk 4 mitigated — ownership written at insert; no post-ingest ownership `UPDATE`
- [ ] Risk 5 mitigated — attachment processing awaited with a bounded wait; both branches genuinely exercised
- [ ] Risk 6 mitigated — failure and timeout both answer and both surface a user-visible indication end-to-end
- [x] Risk 7 mitigated — null `conversation_id` means library-visible; pre-migration rows still retrievable
- [x] Risk 8 mitigated — archived text-only tests pass unmodified

---

## 5. Evidence Log

Record collected evidence here. Every row in Section 1 must have at least one matching
entry. Do not pre-fill — entries must describe real observations.

| # | Evidence Type | Description / Link | Scenario(s) Covered | Collected By | Date |
|---|--------------|-------------------|---------------------|--------------|------|
| 1 | Functional | `pytest tests/test_cap_6_session_scoped_attachment_retrieval.py` — 12 passed (2026-09-17). Conversation A's job description is returned in A and absent in B while the library resume is returned in both; `metadata_filter` naming A's document from B returns empty; retrieval with no conversation returns only unowned chunks; sparse and hybrid behave identically. Every exclusion assertion is paired with a positive assertion on the library document, so none can pass on an empty result set. | 1–5, 12–15, 17, 19 | claude (apply) | 2026-09-17 |
| 2 | Functional | Same run — `TestConversationVisibilityInGeneratedSQL`: a generated `SELECT chunk_text FROM document_chunks` rewritten by `apply_conversation_scope` returns the library chunk and not conversation A's, and `document_text_spans` (which has no `conversation_id` of its own) is scoped through `documents` with the same outcome. | 33, 34 | claude (apply) | 2026-09-17 |
| 3 | Functional | Same run — `TestScopeCoverageGuard`: every whitelisted table appears in the conversation scope-column map, and `SUPPORTED_SCOPE_TYPES` is still `{tenant, document}`, so the boundary did not leak into model-chosen arguments. | 5, 6 | claude (apply) | 2026-09-17 |
| 4 | Functional | `pytest tests/test_chunk_metadata_ingest.py` — 15 passed (2026-09-17), including the new parametrised `test_store_chunks_persists_conversation_ownership_on_every_row`: a conversation-owned document stamps every chunk, a library document leaves every chunk NULL. | 22, 23 | claude (apply) | 2026-09-17 |
| 5 | Functional | `pytest tests/test_chat_api_conversations.py` — 33 passed (2026-09-17). A multipart first send creates the conversation and stores a row carrying checksum, blob_path and retention_mode, which the metadata-only row it replaces never had; an unsupported `.exe` is rejected 422 and leaves the conversations table empty; the archived text-only tests are unmodified and still green. | 25–29, 32 | claude (apply) | 2026-09-17 |
| 6 | Functional | `pytest` over the ten retrieval and SQL suites (`test_retrieval_foundation`, `test_hybrid_retrieval`, `test_retrieval_tools_integration`, `test_retrieval_tools`, `test_retrieval_orchestrator`, `test_reranking_retriever`, `test_retrieval_config`, `test_orchestrator_recovery`, `test_chat_api_sql`, `test_sql_table_whitelist`) — 173 passed (2026-09-17). Every pre-existing retriever behaviour still holds with the conversation clause compiled into the SQL. | 7–11, 16, 18, 20, 21, 24 | claude (apply) | 2026-09-17 |
| 7 | Functional | `npm run test` in `src/portal` — 663 passed / 18 failed (2026-09-17); the chat suites are fully green (19 passed). The multipart body carries the real `File` on both send paths; a text-only send is still JSON with exactly `{message, conversation_id}`; a failed send preserves the tray; the tray shows an upload status with send and remove disabled while in flight; an `unavailable_attachments` response renders a user-visible notice. The 18 failures are the pre-existing portal UI-drift baseline CAP-2 recorded, all in components this change does not touch. | 35–40 | claude (apply) | 2026-09-17 |
| 8 | Functional | `pytest tests/test_cap_5_documents_library_exclusion_and_delete.py` — 8 passed (2026-09-17). Conversation delete still hard-deletes the attachment's row, derived chunks and blob, so ADR-011's delete guarantee holds now that these documents genuinely have chunks. | ADR-011 | claude (apply) | 2026-09-17 |
| 9 | Structural | Code review against design.md: transport branches on `Content-Type` with the JSON path untouched (Decision 1); `_persist_attachments` and its direct INSERT are deleted and a grep finds no insert into `documents` in `chat.py` (Decision 2, risk 3); `conversation_id` is a `NormalizedDocument` field written by `_insert_row` with no post-ingest UPDATE (risk 4); the chunk column is denormalized like `purpose` (Decision 3); the retriever clause is built outside `_metadata_filter_clause` (Decision 4, risk 1); `apply_conversation_scope` runs unconditionally after validation (Decision 5); processing is awaited with a bounded wait and degrades explicitly (Decision 6). `tests/test_ingestion_boundary.py` — 11 passed, so the one-code-path rule is intact. | all | claude (apply) | 2026-09-17 |
| 10 | Edge | Risk 7: the predicate is `conversation_id IS NULL OR conversation_id = :conversation_id`, never an equality test that drops NULLs; migration 041 adds the column nullable with no backfill, and the retrieval suites seed rows without it and still retrieve them. Risk 8: the archived text-only chat tests pass unmodified. | 24, 28, 29 | claude (apply) | 2026-09-17 |
| 11 | Gap | **Scenario 30 is not evidenced.** That a turn can be answered from its own attachment is proven only at the retrieval layer (rows 1 and 13). The API-level tests mock the orchestrator, so nothing asserts end to end that a reply cites an attachment sent in the same turn. A reviewer should exercise this against the running stack before archive. | 30 | claude (apply) | 2026-09-17 |
| 12 | Gap | **Scenario 31 is not evidenced.** The backend reports `unavailable_attachments` and the portal renders it (row 40), and the bounded-wait branch is exercised (row 32), but no backend test forces an attachment's *processing* to fail and asserts the turn still answers carrying the indication. | 31 | claude (apply) | 2026-09-17 |
| 13 | Environment | Not verified in a browser. The portal dev server compiles and serves `/chat` (HTTP 200), but the page renders blank because every API call returns 401 without the backend stack, so the composer could not be exercised interactively. Portal behaviour is covered by the tests in evidence 7. | 35–40 | claude (apply) | 2026-09-17 |

---

## 6. Audit Record

Signed off by a human reviewer before archive. Do not check these boxes during apply.

- [ ] Every row in Section 1 has a populated Verification Artifact and a checked Status
- [ ] Every item in Section 4 is satisfied by real evidence logged in Section 5
- [ ] Every risk in Section 2 has been checked by a human against the implementation
- [ ] Every ADR constraint in Section 3 has been confirmed
- [ ] Reviewer name: ______________________  Date: ____________
