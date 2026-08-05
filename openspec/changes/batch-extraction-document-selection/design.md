## Context

Today `BatchRunsTab.tsx` "New batch run" button calls `POST /api/v1/extract-batch` with no `documentIds`. `trigger_batch_extraction` (extraction.py:94) then selects every document with `status='processed' AND purpose='query'` — it has no idea which documents were already extracted. The actual "already extracted" check (`_get_already_extracted`, worker.py:87) lives inside the Celery worker and only runs after the batch is queued, producing a `skipped_count` the user sees after the fact. There is no document-level picker anywhere in the portal.

Idempotency is keyed on `extracted_entities` rows matching `document_id` + active `model_version` (per the existing extraction-service spec, not `extraction_runs.document_id` which is NULL for batch rows). Any new "already extracted" check must reuse this same definition, or the picker will disagree with what the worker actually skips.

## Goals / Non-Goals

**Goals:**
- Surface eligible documents to the user before a batch run starts.
- Prevent selecting documents already extracted under the tenant's current active model version.
- Keep the "already extracted" definition identical to the worker's existing skip logic (no second source of truth).

**Non-Goals:**
- Changing how the worker itself skips documents (already correct, unchanged).
- Pagination/search UX polish for very large document sets (flagged as an open question, not solved here).
- Changing the no-`documentIds` "process all eligible" backend behavior — it stays available for non-UI callers (e.g. scripts), the portal simply stops using it.

## Currently-In-Force ADRs

None of the existing ADRs (001–008, covering tenant data isolation, base-model strategy, model-serving topology, OpenSpec governance, agent boundaries, training infra, chatbot architecture, base-model-as-default) constrain a portal picker UI or a read-only document-listing endpoint. No ADR revisions needed.

## Decisions

### Decision 1: New read-only endpoint vs. reusing `/api/v1/documents`

**Choice:** Add `GET /api/v1/extract-batch/eligible-documents` on the extraction service, returning `processed` documents with an `already_extracted` boolean per document.

**Rationale:** `/api/v1/documents` is owned by the document-ingestion side and has no notion of extraction/model-version state. The extraction service already owns `extracted_entities` and the active-model lookup (`_get_active_model_version`, worker.py:105), so it's the natural owner of "is this document already extracted."

**Alternatives considered:**
- Extend `/api/v1/documents` with an `already_extracted` field — rejected, would require the document service to query extraction-service tables/cross-service join.
- Compute eligibility client-side by cross-referencing `/api/v1/documents` and `/api/v1/entities` — rejected, forces the frontend to reimplement the active-model-version + idempotency logic that already exists server-side.

### Decision 2: Extract shared "already extracted" lookup out of `worker.py`

**Choice:** Move `_get_already_extracted(tenant_id, doc_ids, model_version)` from `worker.py` into `entity_store.py` as a reusable function; both the worker and the new endpoint call it.

**Rationale:** Avoids duplicating the idempotency query (currently only defined once, privately, in the Celery worker module). Keeps the picker and the actual skip behavior guaranteed to agree.

**Alternatives considered:**
- Duplicate the query in the new endpoint — rejected, two copies of the same SQL will drift.

### Decision 3: Enforcement is server-side, not just modal-disabled checkboxes

**Choice:** `trigger_batch_extraction` continues to accept explicit `documentIds`; the endpoint doesn't need new server-side rejection of already-extracted IDs in the request, because the worker already skips them (existing behavior, unchanged). The modal disabling is a UX guardrail, not the enforcement boundary.

**Rationale:** The idempotency skip is already authoritative and tested (see extraction-service spec's "Batch extraction skips already-extracted documents" scenario). Duplicating that enforcement in the trigger endpoint would be redundant; the modal only needs to stop users from *intending* to re-run something pointless.

**Alternatives considered:**
- Reject already-extracted `documentIds` at `POST /extract-batch` with a 422 — rejected as unnecessary; would double the idempotency logic and complicate the "explicit documentIds bypasses purpose filtering" contract that already exists for other callers.

## Risks / Trade-offs

- [New endpoint and worker function can drift if someone edits one without the other] → Consolidating into one shared `entity_store.py` function (Decision 2) removes the duplication that would otherwise cause drift.
- [Eligible-documents list has no pagination; a tenant with thousands of processed documents gets a huge payload] → Acceptable for now given current tenant document volumes; flagged as an open question below.
- [Active model version can change between fetching the eligible list and confirming the modal, making the disabled/enabled state stale] → Low risk given how infrequently model promotion happens relative to modal usage; worker-side skip still protects correctness even if the modal's flag is stale.

## Migration Plan

- No schema/data migration required — reuses existing `extracted_entities`, `extraction_runs`, and model-version lookups.
- Backend: add the new endpoint and shared lookup function; ship independently of the frontend (additive, no breaking change to `POST /api/v1/extract-batch`).
- Frontend: swap `BatchRunsTab.tsx`'s direct trigger for the modal flow; `useBatchRuns().triggerBatch` signature change is contained to this component tree.
- Rollback: revert the frontend commit to restore the old one-click trigger; backend endpoint can stay (unused) without harm.

## Open Questions

- Should `/api/v1/extract-batch/eligible-documents` paginate once tenant document counts grow large enough that the modal list becomes unwieldy?
