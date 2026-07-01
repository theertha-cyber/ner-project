## Context

The `model-registry` backend spec defines CRUD and lifecycle management for tenant model versions: `GET /api/v1/models`, `GET /api/v1/models/active`, `POST /api/v1/models/{id}/promote`, `POST /api/v1/models/{id}/demote`, `POST /api/v1/models/{id}/warmup`. The portal's `/models` route renders a `PlaceholderScreen`. Tenant Admins cannot view version history, compare metrics, or promote/demote models without direct API calls.

The portal already has: TanStack Query, `authFetch`, `useAuth` (exposes `user.tenantSlug`), toast patterns, skeleton loading, and two-column list+detail patterns from the training-jobs screen.

## Goals / Non-Goals

**Goals:**

- Replace the placeholder with a fully interactive model registry page matching the mockup's two-column layout
- Implement list, detail view, promote, demote, and warmup flows via the existing backend API
- Follow established portal patterns (TanStack Query hooks, `authFetch`, toast on mutation, role-gated actions)
- Distinguish promoted models visually with a primary-colored "Promoted" badge

**Non-Goals:**

- Backend schema changes (no new fields, no new endpoints)
- Training job submission or hyperparameter configuration (handled by SP-07)
- Batch operations (multi-promote, multi-demote)
- Model version deletion or soft-delete (not in backend spec)
- Real-time polling of training status from within model registry (training jobs screen handles this)

## Currently-In-Force ADRs

| ADR | Decision Summary | Constraint on This Design |
|-----|-----------------|--------------------------|
| ADR-001: Tenant Data Isolation | All data is isolated per tenant via separate schemas; API endpoints are tenant-scoped | Model registry API calls MUST include `tenantSlug` in the URL prefix via the gateway routing |
| ADR-003: Model Serving Topology | Per-tenant model serving with version pinning, on-demand loading | Promote triggers warmup via the backend; frontend only calls POST, does not poll warmup status |
| ADR-002: Single Base Model (partially superseded by ADR-008) | Base model uses CoNLL labels PER/ORG/LOC/MISC | N/A — model registry is agnostic to base model choice |

## Decisions

### Decision 1: One spec (`model-registry-screen`) covering page + hooks + components

**Choice:** Deliver the entire model registry UI as a single capability spec rather than splitting hooks into a separate `model-registry-api-client` spec.

**Rationale:** The hooks are only consumed by this one page. Splitting would add overhead with no reuse benefit.

**Alternatives considered:**
- Separate `model-registry-api-client` spec — ruled out because the hooks have no current cross-screen consumers.

### Decision 2: Two-column list+detail layout matching training-jobs pattern

**Choice:** Use the same left-column card list + right-column detail panel layout as SP-07 (Training Jobs). Cards are left-aligned with primary info (version, status, F1, date). Detail panel appears on card click.

**Rationale:** Consistent UX pattern. Users familiar with training jobs will immediately understand model registry navigation.

**Alternatives considered:**
- Single-column list with expandable rows — ruled out because the mockup shows a detail panel for rich metrics, lineage, and actions.
- Table layout — ruled out because the card format better accommodates status badges, metrics summary, and visual prominence for the promoted version.

### Decision 3: Active model fetched as separate query

**Choice:** `useModelVersions()` returns the list from `GET /api/v1/models` and separately fetches `GET /api/v1/models/active` to identify which model is currently promoted.

**Rationale:** The list endpoint does not necessarily indicate which model is promoted (the promoted version is distinguished by its `status` field). A dedicated active query ensures the UI can highlight the promoted model and the dashboard secondary panel can consume the same query.

**Alternatives considered:**
- Derive promoted model from the list by filtering `status === "promoted"` — ruled out because the dashboard component and other screens may need the active model independently without refetching the full list.

### Decision 4: Promote/demote/warmup buttons gated by role client-side

**Choice:** `tenant_admin` sees all action buttons; `business_user` sees a read-only detail panel. Role check via `useAuth().user.role`.

**Rationale:** The backend enforces authorization (returns 403 for unauthorized roles), but hiding the buttons prevents confusing API errors and matches the mockup behavior.

**Alternatives considered:**
- Always show buttons and let backend reject — ruled out as poor UX.

### Decision 5: Per-entity metrics in collapsible section

**Choice:** Per-entity F1/precision/recall scores (if present in the model version `metrics` object) render in a collapsible accordion below the main metrics grid, collapsed by default.

**Rationale:** Most users care about overall F1. Per-entity detail is valuable for power users but would overwhelm the main metrics grid. The mockup shows this pattern for training jobs metrics.

### Decision 6: Always show base model (version 0) as a permanent list entry

**Choice:** Synthesize a version 0 entry client-side and always append it at the bottom of the model registry list. If `GET /api/v1/models/active` returns `version_number: 0`, use that data directly; otherwise construct a synthetic entry with `status: "archived"`.

**Rationale:** ADR-008 requires version 0 (`dslim/bert-base-NER`) to always be available as the tenant's fallback inference model. It is never returned by `GET /api/v1/models` (no database row) but is always returned by `GET /api/v1/models/active` when no fine-tuned model is promoted. Showing it in the list makes the registry accurate and prevents users from thinking the system has no active model.

**Alternatives considered:**
- Only show version 0 when it is the active model — ruled out because it disappears once a fine-tuned model is promoted, giving the false impression it no longer exists.
- Backend returns version 0 in the list endpoint — ruled out as it requires a backend change and ADR-008 explicitly calls version 0 "synthetic with no database row."

**Version 0 UI rules:**
- Card label: "Base Model" (not "v0")
- Status badge: "promoted" when `activeModel.version_number === 0`, "archived" otherwise
- Detail panel: shows model name `dslim/bert-base-NER` and CoNLL labels; no Promote / Demote / Warmup buttons

## Risks / Trade-offs

- [Per-entity metrics field name convention unknown] → Assume pattern `{entity_type_name}_f1`, `{entity_type_name}_precision`, `{entity_type_name}_recall`. If the backend uses a different structure (e.g. nested object), the component will need adjustment. Document the expected shape in the types file.
- [Warmup endpoint may be async] → Assume synchronous (200 on success, 5xx on failure) per the model-registry spec. If async, the warmup button could show "Triggered" state instead of "Success".
- [Promote replaces active model optimistically] → On promote success, immediately invalidate both the list and active model queries to reflect the change. No optimistic update within the mutation handler — let the refetch show the new state.

## Migration Plan

1. Add hooks (`use-model-versions.ts`, `use-promote-model.ts`, `use-demote-model.ts`, `use-warmup-model.ts`) under `src/portal/src/hooks/`
2. Add components (`ModelVersionCard`, `ModelDetailPanel`, `WarmupStatusPanel`) under `src/portal/src/components/model-registry/`
3. Add types (`src/portal/src/types/model-registry.ts`) for `ModelVersion` and related interfaces
4. Replace `PlaceholderScreen` in `src/portal/src/app/(auth)/models/page.tsx` with `ModelRegistryPage`
5. No backend changes, no DB migrations, no env var changes — frontend-only deployment

**Rollback:** Revert the page to `PlaceholderScreen`. No data is mutated by frontend code alone.

## Open Questions

- None — all open questions from the proposal are resolved by this design. The warmup endpoint is assumed synchronous per the existing model-registry spec. Per-entity metrics structure will be documented in types and adjusted on first real API integration.
