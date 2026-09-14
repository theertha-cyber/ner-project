## Context

Chat attachments are persisted as conversation-owned document rows (CAP-3, ADR-011): `_persist_attachments` inserts metadata-only rows into the tenant `documents` relation with a `conversation_id` linking each row to exactly one conversation. Migration `040` added `conversation_id` with `ON DELETE CASCADE` from `documents` to `conversations`.

Two gaps remain, both in scope for CAP-5:

1. **Library isolation is incomplete.** `list_documents` already appends `conversation_id IS NULL` to its predicates when the column exists, but `get_document` (fetch-by-id), `get_document_text`, and `delete_document` (library soft-delete) do not. A conversation attachment is therefore reachable by an honest guess of its id, its derived text can be fetched, and it can be soft-deleted out from under its owning conversation — contradicting ADR-011's model that a conversation-owned row is reachable only through that conversation.

2. **Conversation deletion does not clean up attachments.** `delete_conversation` deletes `chat_messages` and the `conversations` row only. The `ON DELETE CASCADE` backstop removes the attachment document rows as a side effect, but nothing removes their blobs (when present) or their derived spans, chunks, entities and relational-projection rows. FR-007 requires those to be unrecoverable through the product.

The constraint that shapes the solution is the decomposition's: reuse the existing delete-propagation pattern (`build_relational_delete_statements`, the same pure builder the extraction worker and the library soft-delete use) rather than inventing a second cleanup path. The propagating delete path in the library already removes chunks, spans, entities and relational rows per document; the hard-delete needed here differs by also removing the stored blob and deleting the document row outright instead of marking it `deleted`.

## Goals / Non-Goals

**Goals:**

- Every tenant-wide Documents library surface (list, fetch-by-id, text retrieval, library delete) excludes conversation-linked rows.
- Conversation deletion hard-deletes the conversation's attachment document rows, their blobs, and every derived artefact row, before the conversation row is removed.
- The cleanup reuses the existing propagation pattern — one way to delete a document's derived state.
- The delete path is idempotent and safe to retry (NFR from the decomposition).
- Non-chat document behavior is unchanged (FR-004).

**Non-Goals:**

- CSV parser behavior, composer staging UI, and new conversation send contract details (decomposition "Out of scope").
- Changing the library's soft-delete semantics for non-chat documents — the library still marks rows `deleted`; only conversation-owned rows are refused there.
- Backfilling cleanup for attachments of conversations deleted before this change.
- New schema migration — `040` already provides the column and the cascade backstop.

## Currently-In-Force ADRs

| ADR | Decision Summary | Constraint on This Design |
|-----|-----------------|--------------------------|
| ADR-011 | Conversation-scoped chat attachments in the existing document model | Conversation deletion must hard-delete the linked document rows, derived spans/chunks and blob objects; library queries must exclude conversation-linked documents. |

## Decisions

### Decision 1: Exclude conversation-linked rows on every library surface, not only the list

**Choice:** Apply the same `conversation_id IS NULL` predicate already used by `list_documents` to `get_document`, `get_document_text`, and `delete_document`. For the text-retrieval route this means resolving the owning document row first (it currently queries spans directly and would happily return text for a conversation-owned id); for fetch-by-id and library delete it means adding the predicate to the lookup and returning not-found when no qualifying row exists.

**Rationale:** ADR-011 scopes a conversation-owned attachment to its conversation. An id-guessable fetch, a span-text leak, or a library soft-delete of the attachment would each break that scoping from a different angle; leaving any of them means the exclusion is cosmetic. The same predicate form keeps the library behavior uniform and the non-chat path untouched.

**Alternatives considered:**
- Rely on the existing list predicate and UI hiding — ruled out because the decomposition explicitly requires the exclusion "in the query predicate rather than relying on naming or UI hiding", and fetch/text/delete routes remain open.
- A dedicated `excludeConversationOwned` flag on each route — ruled out because it would be a second way to express the same rule and could drift.

### Decision 2: A single shared cleanup helper for a document's hard delete

**Choice:** Add one async helper in `document_service` — `hard_delete_documents(session, schema, tenant_id, document_ids)` (proposed home: `src/document_service/services/hard_delete.py`) — that removes, per document id: the stored blob via the content store (guarding on a present reference), the derived rows (`document_chunks`, `document_text_spans`, `extracted_entities`, `document_entities`), the generated relational rows via `build_relational_delete_statements` with the same `existing_tables` narrowing the library delete already uses, and finally the document row itself (`DELETE`, not `UPDATE ... SET status='deleted'`). The conversation delete route calls it for the conversation's attachment ids before removing the conversation.

**Rationale:** The decomposition's constraint is to reuse the existing propagation pattern and allow the conversation delete route to invoke shared helpers. Both the library soft-delete and this hard-delete then derive from the same pure builder, so the sync and async callers cannot diverge into a half-deleted document. A module under `document_service` keeps the helper near the tables and store it touches, and gives `chat_api` a one-way dependency edge that stays acyclic (chat_api → document_service.services, never the reverse).

**Alternatives considered:**
- Replicating the delete statements inline in `chat.py` — ruled out because it duplicates the propagation logic and violates the decomposition constraint.
- Making the library soft-delete do a hard delete for conversation-owned rows — ruled out because the library must not manage conversation-owned rows at all; the conversation lifecycle owns them (Decision 1).

### Decision 3: Cleanup order and the cascade as backstop only

**Choice:** In `delete_conversation`, after the existing ownership check: select the conversation's attachment document ids (with blob references), call `hard_delete_documents` for them, then delete `chat_messages` and the `conversations` row, committing once at the end. The `ON DELETE CASCADE` on `documents.conversation_id` is treated as a backstop, never as the mechanism: explicit cleanup runs first, so blobs and derived rows are gone even though the row itself would have cascaded anyway.

**Rationale:** ADR-011 names the order — document rows, derived spans/chunks and blob objects before the conversation row is removed. The relational tables declare no foreign key to `documents`, so only explicit propagation removes their rows; the cascade covers just the document rows and would leave blobs and relational rows behind if it were relied on. Running the cleanup inside the same transaction as the conversation deletion keeps "delete" atomic: a failure rolls back and a retry is safe.

**Alternatives considered:**
- Rely on the cascade and only clean derived rows — ruled out because blobs must also go, and naming the cascade as the deletion mechanism makes the API's contract depend on a schema side effect.
- Deleting the conversation first and letting the cascade fire, then cleaning residue — ruled out because the residue (blobs, relational rows) is exactly what FR-007 says must not survive, and the attachment rows would already be gone by the time cleanup tried to read their blob references.

## Risks / Trade-offs

- [A chat attachment whose metadata row has `conversation_id` but no persisted blob (`blob_path` NULL — the CAP-3 metadata-only shape)] → The helper guards content-store deletion on the presence of a reference and skips cleanly; tests cover the NULL-reference case.
- [Deleting the conversation row fires the cascade even if explicit cleanup is skipped or fails] → Cleanup runs before the conversation delete inside the same transaction, so a rollback restores the attachment rows; the cascade never runs alone.
- [Library exclusion could regress the non-chat listing, fetch, text or soft-delete path] → The predicate is additive (row must also satisfy `conversation_id IS NULL`); the existing visibility and relational-delete tests keep running, and new scenarios assert non-chat behavior is unchanged.
- [Idempotency: a retried delete must not error on already-absent rows] → The helper's deletes are no-ops on missing rows, the re-delete of a missing conversation returns not-found through the existing ownership check, and nothing commits partial state.

## Migration Plan

1. Add `hard_delete_documents` to `document_service` reusing `build_relational_delete_statements`.
2. Extend the library exclusion predicate in `documents.py` to fetch-by-id, text retrieval and library delete.
3. Wire `delete_conversation` in `chat.py` to the helper before deleting messages and the conversation.
4. Add tests: exclusion per library surface, non-chat unchanged, hard-delete removes rows/blobs/derived state, retry is safe, attachment-less conversation delete unchanged.
5. Roll back by reverting the code change; no data migration is involved — `040` already applied, and rows deleted by this change were conversation-owned by contract.

## Open Questions

- None. ADR-011 and the decomposition resolve the exclusion and hard-delete semantics this change needs; no in-force ADR is being revisited.