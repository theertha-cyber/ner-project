## Why

The Entity Types screen at `/entity-types` is a `PlaceholderScreen`. Tenant Admins have no UI to define or manage the entity types that drive annotation pre-labeling and extraction targeting — the backend API (`entity-config`) already exists but is unreachable from the portal.

## What Changes

- Replace `PlaceholderScreen` at `/entity-types` with a full management UI matching the mockup
- Add `useEntityTypes` list hook and `useCreateEntityType` / `useUpdateEntityType` / `useToggleEntityType` mutation hooks
- Add `EntityTypeCard` component (2-column card grid with colored dot, version badge, required/active pills, base label mapping, examples)
- Add `DefineEntityTypeSlideOver` (460 px right-anchored slide-over with NAME, DESCRIPTION, EXAMPLES, BASE MODEL LABEL chips, Required toggle)
- Expose active/inactive toggle per card (soft-delete via `is_active: false`)

## Capabilities

### New Capabilities

- `entity-types-screen`: Full entity types management page — list, create, edit, and activate/deactivate entity types. Includes all components, hooks, and API wiring needed for the `/entity-types` route.

### Modified Capabilities

*(none — the backend spec `entity-config` is unchanged)*

## Impact

- **Frontend only**: new React components and TanStack Query hooks under `src/portal/`
- **API calls**: `GET /api/v1/tenants/{slug}/entity-types`, `POST`, `PUT /{name}`, `PATCH /{name}` (toggle active) — all existing endpoints from `entity-config` spec
- **Auth shell**: `app-shell` nav item for Entity Types already routes to `/entity-types`; placeholder is replaced, nav unchanged

## Open Questions

- The mockup assigns a `hue` value (0–360) per entity type for the colored dot — should this be server-side (stored column) or client-side (derived from entity type index)? Assume client-side for now to avoid a backend schema change.
- Does the slide-over need validation error display (inline field errors from 422 responses), or is a toast sufficient? Assume toast for v1, consistent with training-jobs pattern.
