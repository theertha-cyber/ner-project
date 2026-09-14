## 1. Library exclusion

- [x] 1.1 Update `src/document_service/api/v1/documents.py` so `get_document` (fetch-by-id) resolves rows with an explicit `conversation_id IS NULL` predicate and returns not-found for conversation-linked rows.
- [x] 1.2 Update `src/document_service/api/v1/documents.py` so `get_document_text` resolves the owning document row with the exclusion predicate before returning spans, returning not-found (and no span text) for conversation-linked rows.
- [x] 1.3 Update `src/document_service/api/v1/documents.py` so `delete_document` (library soft-delete) refuses conversation-linked rows with not-found and leaves the row unchanged.
- [x] 1.4 Confirm `list_documents` keeps its existing `conversation_id IS NULL` predicate and that listing, counts, and the empty state behave unchanged for non-chat uploads.

## 2. Hard-delete cleanup helper

- [x] 2.1 Add `hard_delete_documents(session, schema, tenant_id, document_ids)` to `src/document_service/services/hard_delete.py`: for each id, delete the stored blob via the content store (guarding on a present reference), delete derived rows (`document_chunks`, `document_text_spans`, `extracted_entities`, `document_entities`), run `build_relational_delete_statements` with `list_existing_generated_tables` narrowing, then `DELETE` the document row — all as no-ops on already-absent rows.
- [x] 2.2 Make the helper tolerate metadata-only attachment rows (no persisted blob reference) and missing relational tables, so a retry or an attachment-less conversation leaves no residue and raises nothing.

## 3. Conversation delete path

- [x] 3.1 Update `delete_conversation` in `src/chat_api/api/v1/chat.py`, after the existing ownership check, to select the conversation's attachment document ids with blob references and call `hard_delete_documents` before deleting `chat_messages` and the conversation row, committing once.

## 4. Regression coverage

- [x] 4.1 Add a test that the library listing omits a conversation-linked row from results and total while returning the non-chat upload (verification.md row 1).
- [x] 4.2 Add a test that fetch-by-id of a conversation-linked row returns not-found (verification.md row 2).
- [x] 4.3 Add a test that library text retrieval of a conversation-linked row returns not-found with no span text (verification.md row 3).
- [x] 4.4 Add a test that library delete of a conversation-linked row returns not-found and leaves the row unchanged (verification.md row 4).
- [x] 4.5 Add a test that non-chat list/fetch/text/soft-delete behavior is unchanged (verification.md row 5).
- [x] 4.6 Add a test that conversation deletion removes attachment document rows, blobs, and every derived artefact row, and the conversation is no longer retrievable (verification.md row 6).
- [x] 4.7 Add a test that retrying a conversation delete returns not-found with no partial state (verification.md row 7).
- [x] 4.8 Add a test that deleting a conversation without attachments is unchanged (verification.md row 8).

## 5. Verification & Evidence

- [x] 5.1 Run all acceptance-criteria tests for every scenario in verification.md § Spec Alignment and confirm all pass.
- [x] 5.2 Collect functional evidence (test output / log) for each scenario — record one entry per row in verification.md § Evidence Log.
- [x] 5.3 Confirm every Hallucination Risk mitigation step in verification.md § Hallucination Risk Register.
- [x] 5.4 Confirm all ADR compliance steps in verification.md § Pattern & ADR Compliance.
- [x] 5.5 Complete Audit Record sign-off in verification.md § Audit Record (automated sign-off — human sign-off waived by run policy).
- [x] 5.6 Run `openspec validate cap-5-documents-library-exclusion-and-hard-delete-cleanup --type change --strict` and confirm it exits clean before archive.
