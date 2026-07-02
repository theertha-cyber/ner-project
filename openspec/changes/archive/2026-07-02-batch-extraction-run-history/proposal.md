## Why

The extraction service exposes `POST /api/v1/extract-batch` (trigger a run) and `GET /api/v1/extract-batch/{run_id}` (single-run status), but no endpoint to list a tenant's past runs. The portal's Batch Runs tab calls `GET /api/v1/extract-batch` on mount to populate run history, which doesn't exist as a route — it returns `405 Method Not Allowed`. As a result, every page reload shows "No batch runs yet" even when completed, queued, or failed runs exist in the tenant's `extraction_runs` table. This was caught during manual UI testing of batch extraction.

## What Changes

- Add `GET /api/v1/extract-batch` to the extraction service: lists the tenant's extraction runs ordered by `started_at` descending, returned as `{ "runs": [...] }` shaped to match the existing `BatchRunStatus` fields plus `run_id`.
- Add a corresponding gateway proxy route so the list request reaches the extraction service without a `{tid}` in the URL, consistent with the other extraction proxy routes.
- Update `use-batch-runs.ts` expectations are already correct (frontend code needs no change) — this change only closes the backend gap it depends on.
- Tighten the `portal-extraction-page` spec's "Batch Runs tab lists existing runs" scenario to require the real `GET /api/v1/extract-batch` call (removing the existing hedge that allowed the list to be "derived from available run data").

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `extraction-service`: Add a "List extraction runs" requirement (new `GET /api/v1/extract-batch` endpoint) and extend the "Gateway Extraction Proxy" requirement's path table with this new route.
- `portal-extraction-page`: Tighten the Batch Runs tab requirement so run history is always sourced from `GET /api/v1/extract-batch` on mount, not just "derived from available run data".

## Impact

- **Code**: `src/extraction_service/api/v1/extraction.py` (new route handler), `src/extraction_service/api/v1/schemas.py` (new response schema), `src/extraction_service/services/entity_store.py` (new query helper), `src/gateway/api/v1/*` (new proxy route, wherever the existing `extract-batch` proxy routes live).
- **Data**: Read-only query against the existing `extraction_runs` table — no schema migration needed.
- **Frontend**: No code change expected; `src/portal/src/hooks/use-batch-runs.ts` already calls the endpoint this change adds.
- **Downstream**: None — this is additive and read-only.

## Open Questions

- Should the list endpoint be paginated/limited (e.g., last 50 runs), or return all runs unbounded? Given typical run volume per tenant is expected to stay small, a simple `LIMIT` (e.g., 50) with no cursor is likely sufficient for now.
- Should the response include per-run `document_id` even though it's always NULL for batch runs (per the existing idempotency design), or omit it from the list shape entirely? Leaning toward omitting it since it carries no information for batch runs.