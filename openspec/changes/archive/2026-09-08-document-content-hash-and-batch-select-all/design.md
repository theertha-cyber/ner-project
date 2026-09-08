## Context

`tenant_template.documents.checksum VARCHAR(64)` has existed since migration `002` and is propagated into every tenant schema (`tenant_service.py:59` creates tenant tables with `LIKE tenant_template.<table> INCLUDING ...`, and migration `023` reconciles pre-existing schemas). No code has ever written to it. The upload path (`documents.py:41`) already holds the complete file bytes in memory as `file_data` at line 60 — before the size check, before the MinIO put, before the INSERT — so a hash can be computed with no extra I/O and no streaming rework.

Document semantics that must survive this change: `documents.uploaded_by` scopes list visibility for non-admin roles; `document_text_spans`, `document_chunks`, `extracted_entities`, and `document_entities` all foreign-key to a single `document_id`; delete is a soft delete (`status = 'deleted'`); every table lives inside the per-tenant schema, which is the tenant isolation boundary.

On the portal side, `BatchDocumentSelectModal.tsx` already holds selection as a `Set<string>` and already guards `toggle()` against `already_extracted` documents. Bulk selection is a pure addition to that existing state.

## Goals / Non-Goals

**Goals:**
- One deterministic, stable content hash per uploaded document, computed in exactly one place.
- Identical bytes under different filenames resolve to the same hash and are recognisably linked.
- No change to document ownership, extraction history, annotations, or tenant isolation.
- Bulk selection in the existing modal without redesigning it.

**Non-Goals:**
- Rejecting duplicate uploads.
- Merging or deleting document records.
- Backfilling checksums for historical documents.
- Cross-tenant duplicate detection (would violate the tenant isolation boundary).
- Server-side rejection of already-extracted `documentIds` at `POST /api/v1/extract-batch`.

## Currently-In-Force ADRs

ADR-001 (tenant data isolation) is the only in-force ADR that constrains this change: all checksum lookups MUST stay inside the caller's tenant schema and additionally filter on `tenant_id`. No cross-schema or cross-tenant checksum query is permitted. No ADR revisions needed.

## Decisions

### Decision 1: SHA-256 hex digest over raw uploaded bytes

**Choice:** `hashlib.sha256(data).hexdigest()` over the exact bytes received, in `src/document_service/services/content_hash.py`.

**Rationale:** 64 hex characters fits the existing `VARCHAR(64)` column exactly, which is what `002` sized it for and what `docs/requirements.md` already specifies ("checksum (SHA-256)"). Hashing raw bytes rather than extracted text makes the hash independent of OCR timing and OCR determinism — the hash is available at INSERT time, not minutes later after the OCR task finishes.

**Alternatives considered:**
- Hash the extracted text instead — rejected: text is not available at upload time, OCR output is not guaranteed byte-stable across library versions, and it would make the hash a mutable derived value.
- MD5 — rejected: no shorter than needed, and collision-prone for a value used as an identity signal.
- Perceptual/fuzzy hashing for near-duplicates — rejected as out of scope; the requirement is *identical content*, not similar content.

### Decision 2: Identify and link, never reject or merge

**Choice:** A duplicate upload succeeds normally and returns `duplicate_of: <earliest matching document id>` alongside its own new `id`. Nothing about the existing document is touched.

**Rationale:** The prior document may already carry annotations, an extraction history, and a different `uploaded_by` owner. Rejecting the upload would break the legitimate case of two users independently uploading the same source file under their own ownership; merging would silently reassign or destroy that history. Identification gives the system the signal it needs while leaving the policy decision (what to do about duplicates) to a later, separately-specified change.

**Alternatives considered:**
- Reject with 409 on duplicate — rejected: destroys the independent-ownership case and is not reversible from the client's side.
- Auto-merge into the existing record — rejected outright; explicitly forbidden by the change's constraints and would break ownership, extraction history, and annotation linkage.
- Unique constraint on `(tenant_id, checksum)` — rejected: that is rejection-by-database, same problem, and would fail hard on legacy rows once a backfill runs.

### Decision 3: Duplicate lookup is tenant-schema scoped and excludes soft-deleted rows

**Choice:** `SELECT id FROM {tenant_schema}.documents WHERE tenant_id = :tid AND checksum = :checksum AND status != 'deleted' ORDER BY created_at LIMIT 1`.

**Rationale:** The schema qualifier is the tenant isolation boundary and the `tenant_id` predicate is defence in depth, matching the pattern every other query in `documents.py` uses. Excluding `status = 'deleted'` means a user who deleted a document and re-uploaded it is not told it is a duplicate of a record they can no longer see. `ORDER BY created_at LIMIT 1` makes the answer deterministic (the original, not an arbitrary later copy) when three or more copies exist.

**Alternatives considered:**
- Return every matching document ID — rejected: the response contract gets unbounded, and no consumer needs more than the original.
- Include soft-deleted rows — rejected: points at a record the API will not serve.

### Decision 4: Index the existing column rather than adding a new one

**Choice:** Migration `034` creates `ix_documents_checksum` on `tenant_template.documents (checksum)` and, in the same `DO $$` loop pattern used by migration `023`, on every already-provisioned `tenant_%` schema.

**Rationale:** The column already exists everywhere; adding a second column named `content_hash` would leave a permanently-NULL column behind and contradict `docs/requirements.md`. New tenants inherit the index automatically because `tenant_service.py` creates tenant tables with `INCLUDING INDEXES`. A plain (non-unique) index is correct here — Decision 2 requires duplicates to be storable.

**Alternatives considered:**
- No index — rejected: the duplicate lookup runs on every upload and would degrade to a sequential scan as a tenant's document count grows.
- Unique index — rejected, see Decision 2.

### Decision 5: "Select all" is derived state, not a third selection mode

**Choice:** The modal keeps its single `Set<string>` of selected IDs. "Select all" is a checkbox whose `checked` value is derived (`selectable.length > 0 && every selectable id is in the set`) and whose handler either adds every selectable ID or removes every selectable ID. Its `disabled` is `selectable.length === 0`.

**Rationale:** Storing a separate `allSelected` boolean would create two sources of truth that drift the moment a user unticks one row. Deriving it means the header checkbox and the row checkboxes cannot disagree. Because the handler only ever iterates `documents.filter(d => !d.already_extracted)`, a disabled document's ID has no code path into the set at all.

**Alternatives considered:**
- A "Select all" button rather than a checkbox — rejected: a button cannot show the current all/none state, and the spec requires the same control to clear the selection.
- Tri-state indeterminate checkbox — considered and kept optional; the acceptance criteria only require checked/unchecked plus a count, and an indeterminate visual is not part of the portal's existing checkbox conventions.

### Decision 6: No server-side change to `POST /api/v1/extract-batch`

**Choice:** Leave `trigger_batch_extraction` untouched.

**Rationale:** `run_batch_extraction` already computes `already = get_already_extracted(...)` and processes only `[d for d in docs if d not in already]` (`worker.py:135-137`), using the exact same shared function the eligible-documents endpoint uses to set the `already_extracted` flag. The invariant "an already-extracted document is never re-extracted" is therefore already enforced at the execution boundary, regardless of what a tampered client submits. This restates Decision 3 of the `batch-extraction-document-selection` change and does not reopen it.

## Risks / Trade-offs

- [Hashing a 50MB upload adds CPU time on the request path] → SHA-256 over 50MB is single-digit milliseconds and the bytes are already fully in memory; no additional read, no streaming change.
- [Documents uploaded before this change have `checksum IS NULL` and will never match a duplicate] → Accepted and documented; the duplicate lookup filters on an exact checksum value so NULL rows simply never match. A backfill is deferred as an open question rather than bolted on here.
- [Two byte-identical files that differ only in filename now report `duplicate_of`, which a caller might misread as "your upload was rejected"] → The response still returns 201 with the new document's own `id` and `status: "pending"`; `duplicate_of` is purely additive metadata.
- [Deriving "Select all" state means a large document list recomputes the predicate on every render] → The list is already unpaginated and rendered in full; an `every()` over the same array is negligible next to rendering it.

## Migration Plan

- Migration `034` is additive (index creation only, `IF NOT EXISTS`), safe to run against live tenant schemas, and requires no downtime or data movement.
- The document-service change is backward compatible: `checksum` and `duplicate_of` are new response fields, and existing clients that ignore unknown fields are unaffected.
- The portal change is contained to one component; no hook, type, or endpoint signature changes.
- Rollback: revert the document-service commit (the index and the already-declared column can remain harmlessly) and revert the portal commit to restore the previous modal.

## Open Questions

- Should a follow-up change backfill `checksum` for pre-existing documents by re-reading their MinIO blobs, and if so, should it run as a one-off script or a migration?
- Should the documents list UI eventually group or badge duplicates now that the signal exists?
