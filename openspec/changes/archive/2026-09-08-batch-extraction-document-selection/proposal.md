## Why

"New batch run" in the portal (`BatchRunsTab.tsx`) triggers `POST /api/v1/extract-batch` with no `documentIds`, so the backend silently picks every `processed`/`purpose='query'` document, including ones already extracted with the active model. The worker skips already-extracted documents at execution time (`_get_already_extracted` in `worker.py`), but the user has no visibility or control over which documents a run will touch, and cannot target a specific subset. Users need to pick documents up front, and should not be able to pick ones already processed.

## What Changes

- Add `GET /api/v1/extract-batch/eligible-documents` on the extraction service: returns tenant documents in `processed` status with an `already_extracted` flag (true when `extracted_entities` has rows for that `document_id` + the active model version).
- Add a document-selection modal in the portal, opened from "New batch run" in `BatchRunsTab.tsx`, listing eligible documents with checkboxes.
- Documents already extracted with the active model version SHALL render disabled/unselectable in the modal, with a label indicating they were already processed.
- Confirming the modal calls `POST /api/v1/extract-batch?documentIds=<selected>` with only the checked, not-yet-extracted document IDs (never triggers the "process all eligible" default path from this UI).
- Modal SHALL block confirmation when zero documents are selected.
- `useBatchRuns().triggerBatch` SHALL accept an explicit `documentIds: string[]` argument instead of always calling the no-arg endpoint.

## Capabilities

### New Capabilities

(none — this extends existing capabilities)

### Modified Capabilities

- `extraction-service`: add the eligible-documents listing endpoint (new requirement); existing batch-extraction requirement is unchanged.
- `portal-extraction-page`: "New batch run" SHALL open a document-selection modal instead of triggering immediately; modal behavior (listing, disabling already-extracted docs, confirm/cancel) becomes a new requirement under this capability.

## Impact

- `src/extraction_service/api/v1/extraction.py`: new `GET` route.
- `src/extraction_service/api/v1/schemas.py`: new response schema for eligible documents.
- `src/extraction_service/services/entity_store.py` or `worker.py`: reuse/expose the already-extracted lookup for a set of documents (currently private to `worker.py`).
- `src/portal/src/components/extractions/BatchRunsTab.tsx`: wire modal open/close instead of direct trigger.
- New portal component: document-selection modal (e.g. `BatchDocumentSelectModal.tsx`).
- `src/portal/src/hooks/use-batch-runs.ts`: `triggerBatch` signature change to accept `documentIds`.
- `src/portal/src/types/extraction.ts` / `documents.ts`: add `already_extracted` field to eligible-document type.
- `src/gateway/api/v1/extraction_proxy.py`: new proxy route for `GET /extract-batch/eligible-documents` (required — the portal's `authFetch` would otherwise route a `/api/v1/documents/*`-prefixed path to the document-service directly, bypassing the gateway/extraction-service entirely; this is why the endpoint lives under `/extract-batch/*` rather than `/documents/*`).
- `docker-compose.yml`: `extraction_service` service needed `NER_DATABASE_URL_SYNC` added (only `celery_worker_extraction` had it) since the new endpoint reuses the worker's sync-engine lookup functions.

## Open Questions

- Should the eligible-documents endpoint paginate, or return the full list (tenant document volumes are assumed small enough for a modal checklist — confirm no pagination needed)?
- Confirmed: "already processed" is defined per the existing idempotency rule — extracted with the **current active model version** — not merely `status='processed'`. A document extracted only under a since-superseded model version SHALL be selectable again.
