## Why

The Model Registry screen at `/models` is a `PlaceholderScreen`. Tenant Admins and Business Users have no UI to view trained model versions, compare evaluation metrics, or promote/demote models — the backend API (`model-registry`) already exists but is unreachable from the portal.

## What Changes

- Replace `PlaceholderScreen` at `/models` with a full management UI matching the mockup's two-column pattern (list + detail)
- Add `useModelVersions` list hook and `usePromoteModel` / `useDemoteModel` / `useWarmupModel` mutation hooks
- Add `ModelVersionCard` component (list card with version number, status badge, F1 score, date)
- Add `ModelDetailPanel` component (evaluation metrics grid, artifact path, MLflow run link, per-entity metrics section, lineage strip, promote/demote/warmup action buttons gated by role)
- Add `WarmupStatusPanel` component (showing warmup progress state from model-serving)

## Capabilities

### New Capabilities

- `model-registry-screen`: Full model registry page — list, view details, promote, demote, and warmup model versions. Includes all components, hooks, and API wiring needed for the `/models` route.

### Modified Capabilities

- *(none — the backend spec `model-registry` is unchanged)*

## Impact

- **Frontend only**: new React components and TanStack Query hooks under `src/portal/`
- **API calls**: `GET /api/v1/models`, `GET /api/v1/models/active`, `POST /api/v1/models/{id}/promote`, `POST /api/v1/models/{id}/demote`, `POST /api/v1/models/{id}/warmup` — all existing endpoints from `model-registry` spec
- **Auth shell**: `app-shell` nav item for Models already routes to `/models`; placeholder is replaced, nav unchanged

## Open Questions

- Does the warmup endpoint return immediate success/failure or is it an async operation that requires polling? Assume synchronous for v1 (returns 200 on success, 5xx on failure), consistent with the existing model-registry spec wording "proxy SHALL call the model-serving warmup endpoint".
- Per-entity metrics (e.g. `vendor_name_f1`) — does the backend return these in the model version response or only in the training job detail response? Assume they are available in the model version `metrics` object as nested keys.
