## Why

The `/extractions` route in the portal exists for the `business_user` role but renders only a placeholder screen. Business users have no way to interact with the extraction pipeline — they cannot test the model against text, monitor batch extraction runs, or review and correct extracted entities. The backend extraction service is fully implemented; the only missing piece is the frontend.

## What Changes

- Replace `PlaceholderScreen` at `/extractions` with a full three-tab workspace
- **Playground tab**: real-time text extraction via `POST /api/v1/extract` — paste text, see entities returned with type, value, and confidence, sorted by confidence descending
- **Batch Runs tab**: trigger new batch extraction runs via `POST /api/v1/extract-batch`, list existing runs with progress bars and status pills, click a run to see its detail panel (total / processed / skipped / failed stats + large progress percentage)
- **Entity Review tab**: browse all extracted entities from `GET /api/v1/entities` with filter pills by review status (all / unreviewed / confirmed / corrected / rejected), confirm or reject each entity row in-line

## Capabilities

### New Capabilities

- `portal-extraction-page`: Three-tab extraction workspace at `/extractions` for the `business_user` role — Playground (real-time inference), Batch Runs (async batch job management), and Entity Review (entity listing, filtering, confirm/reject actions)

### Modified Capabilities

<!-- none — no existing spec-level requirements are changing -->

## Impact

- `src/portal/src/app/(auth)/extractions/page.tsx` — replaces placeholder
- New component files under `src/portal/src/components/extractions/`
- Calls existing gateway endpoints: `POST /api/v1/extract`, `POST /api/v1/extract-batch`, `GET /api/v1/extract-batch/{run_id}`, `GET /api/v1/entities`, `PATCH /api/v1/entities/{id}`
- No backend changes required
- No nav changes required — `business_user` nav already includes the Extractions link

## Open Questions


- Should business users be able to trigger new batch runs, or only view them? The mockup shows a "New batch run" button 
Answer- yes.
