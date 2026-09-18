## 1. Schema — conversation ownership on chunks

- [x] 1.1 Add Alembic revision `041_document_chunks_conversation_id.py` (revises `040`) adding a nullable `conversation_id VARCHAR` to `tenant_template.document_chunks` and to every provisioned `tenant_%` schema, following the loop-and-`to_regclass`-guard shape of migrations 022/034/040. No FK and no backfill (design Migration Plan step 1); implement `downgrade()` symmetrically.
- [x] 1.2 Add the column to the test fixture tenant schema in `tests/conftest.py` so tests exercise the deployed shape.
- [ ] 1.3 Verification: migration applies and downgrades cleanly against a provisioned tenant schema, and pre-existing chunk rows end with a null `conversation_id` (verification rows 24, Structural Evidence "Migration 041"). NOT DONE: `alembic upgrade`/`downgrade` was not run — applying a migration to the shared dev database is the reviewer's call, not something to do unprompted. The column's semantics are covered by tests against the fixture schema; the revision itself is unexercised.

## 2. Ingestion — attachments become real documents

- [x] 2.1 Add `conversation_id: str | None = None` to `NormalizedDocument` (`src/document_service/ingestion/contract.py`) and write it in `DocumentIngestionService._insert_row`'s `INSERT` column list and params (design Decision 2). No post-ingest `UPDATE` may set ownership (risk 4).
- [x] 2.2 Denormalize `conversation_id` onto `document_chunks` in `src/document_service/services/ocr_worker.py`, read from the parent document alongside `purpose` and bound into the existing chunk `INSERT` (design Decision 3).
- [x] 2.3 Verification: `tests/test_chunk_metadata_ingest.py` — ingesting a conversation-owned document stamps every chunk; ingesting a library document leaves every chunk null (verification rows 22, 23).

## 3. Retrieval — the mandatory conversation predicate

- [x] 3.1 Add a `conversation_id: str | None = None` parameter to the `Retriever` protocol and to `DenseRetriever.retrieve`, `SparseRetriever.retrieve`, `HybridRetriever.retrieve` and `RerankingRetriever.retrieve` (`src/shared/retrieval/retriever.py`), threading it through `HybridRetriever`'s two sub-calls and `RerankingRetriever`'s candidate fetch.
- [x] 3.2 Build the predicate unconditionally next to the existing `purpose = 'query'` clause in both the dense and sparse SQL — `AND (conversation_id IS NULL OR conversation_id = :conversation_id)` when a conversation is supplied, `AND conversation_id IS NULL` when it is not. It MUST NOT be reachable from `_metadata_filter_clause` (design Decision 4, risk 1, risk 7).
- [x] 3.3 Carry the current conversation on `ToolContext` (`src/shared/retrieval/tools/base.py`) and pass it from `_retrieve` in `src/shared/retrieval/tools/document_tools.py`. Leave `SUPPORTED_SCOPE_TYPES` and the `scope` argument semantics unchanged — `scope` may only narrow (risk 1).
- [x] 3.4 Thread the conversation from the request into the retrieval context in `src/chat_api/services/rag_orchestrator.py` (`_vector_source`) and `src/chat_api/graph/nodes.py`, taking it from the authenticated request's conversation, never from message text or tool args.
- [x] 3.5 Verification: extend `tests/test_retrieval_foundation.py` and `tests/test_hybrid_retrieval.py` — another conversation's chunks excluded, own conversation's included, `metadata_filter` cannot widen, no-conversation admits only unowned, sparse applies the same rule, and every existing retriever regression still passes (verification rows 8–21).

## 4. SQL path — the second channel

- [x] 4.1 Add `apply_conversation_scope(sql, conversation_id)` beside `apply_document_scope` in `src/chat_api/services/sql_generator.py`, rewriting each conversation-bearing whitelisted table reference into an inline view filtered by `conversation_id IS NULL OR conversation_id = :conv` (design Decision 5).
- [x] 4.2 Define the scope-column map next to `WHITELISTED_TABLES` and run `apply_conversation_scope` unconditionally on every validated statement, after validation and before execution.
- [x] 4.3 Verification: extend `tests/test_sql_table_whitelist.py` with a guard test that fails when a whitelisted table carrying `conversation_id` is absent from the scope-column map, plus a test that a generated statement selecting `chunk_text` returns no other conversation's rows (verification row 33, risk 2).

## 5. Chat API — multipart turns, ingestion, and the bounded wait

- [x] 5.1 Branch both `POST /api/v1/chat` and `POST /api/v1/chat/stream` on `Content-Type`: parse the existing `ChatRequest` for JSON, and message/conversation fields plus file parts for `multipart/form-data`. The JSON path must stay byte-for-byte unchanged (design Decision 1, risk 8).
- [x] 5.2 Delete `_persist_attachments` and its direct `INSERT INTO {schema}.documents`; build a `NormalizedDocument` per uploaded file (platform-upload source, `SINGLE_USE`, `purpose='query'`, authenticated human actor, resolved `conversation_id`) and call `DocumentIngestionService.ingest()` (design Decision 2, risk 3).
- [x] 5.3 Retire `AttachmentInput` from the send contract in `src/chat_api/api/v1/schemas.py`.
- [x] 5.4 Await each ingested attachment reaching `processed` before retrieval runs, bounded by a timeout; on failure or timeout proceed with the turn and set a user-visible indication that the attachment was unavailable (design Decision 6, risks 5 and 6).
- [x] 5.5 Map `UnsupportedFileType` to a client error naming the type and `IncompatibleRetention` to a clear client error naming the retention conflict, rather than a 500 (design Risks).
- [x] 5.6 Verification (landed in `tests/test_chat_api_conversations.py` and `tests/test_cap_6_session_scoped_attachment_retrieval.py` rather than a new file, next to the attachment tests they replace; scenarios 30 and 31 remain unevidenced, see verification.md Evidence Log rows 11-12): add `tests/test_chat_api_attachment_ingestion.py` — first send creates the conversation and ingests, no direct documents insert remains, unsupported type rejected without creating a conversation, the same turn answers from its own attachment, failure and timeout both answer with the indication, and session A's attachment does not answer session B (verification rows 25–27, 30–34).
- [x] 5.7 Verification: confirm `tests/test_ingestion_boundary.py` still passes and archived text-only chat tests pass unmodified (verification rows 28, 29; risks 3 and 8).

## 6. Portal — send file content and report progress

- [x] 6.1 Change the chat page send path (`src/portal/src/app/(auth)/chat/page.tsx`) to build a `FormData` body carrying the message, conversation id and each staged `File` when attachments are staged; keep the existing JSON body verbatim when none are (design Decision 1).
- [x] 6.2 Keep the staged queue holding real `File` objects rather than metadata-only entries, and retire `toChatAttachment`.
- [x] 6.3 Show an in-flight "uploading and preparing" state on the tray while an attachment-bearing send is pending, keep send disabled for its duration, clear on success and preserve the tray with a surfaced error on failure.
- [x] 6.4 Render the backend's "attachment was not available to this answer" indication in the thread.
- [x] 6.5 Verification: extend `src/portal/src/components/chat/ChatInput.test.tsx` and `src/portal/src/app/(auth)/chat/page.test.tsx` — multipart body carries file content, text-only send stays JSON, in-flight progress shown and send disabled, failed send preserves files and re-enables send, unavailable-attachment notice rendered (verification rows 35–40).
- [x] 6.6 Run `npm run typecheck --workspace=src/portal` and the portal test suite; fix any failure this change introduces.

## 7. End-to-end — the HR scenario

- [x] 7.1 Add an end-to-end test covering the driving use case: attach a job description in a new session, ask a question answered from it, then open a second session and ask a question matching the same content and assert the answer neither cites nor draws on it (verification rows 1–4, 33).
- [x] 7.2 Verify conversation delete still removes the newly created chunks and blobs for an ingested attachment (ADR-011 compliance).
- [ ] 7.3 Run the backend suite (`poetry run python -m pytest`) and record any pre-existing failures as a baseline distinct from regressions introduced here.

## 8. Verification & Evidence

- [ ] 8.1 Run all acceptance-criteria tests for every scenario in verification.md § Spec Alignment and confirm all pass.
- [ ] 8.2 Collect functional evidence (screenshot / test output / log) for each scenario — one entry per row in verification.md § Evidence Log.
- [ ] 8.3 Confirm every Hallucination Risk mitigation step in verification.md § Hallucination Risk Register.
- [ ] 8.4 Confirm all ADR compliance steps in verification.md § Pattern & ADR Compliance.
- [ ] 8.5 Complete Audit Record sign-off in verification.md § Audit Record (human reviewer required).
- [ ] 8.6 Run `openspec validate cap-6-session-scoped-attachment-retrieval --type change --strict` before archive.
