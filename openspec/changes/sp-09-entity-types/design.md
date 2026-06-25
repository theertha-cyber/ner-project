## Context

The `entity-config` backend spec defines CRUD for tenant-scoped entity types (`/api/v1/tenants/{slug}/entity-types`). The portal's `/entity-types` route renders a `PlaceholderScreen`. Tenant Admins cannot create or manage entity types without direct API calls. The mockup (`docs/NER Platform.html`) shows a full management UI: a 2-column card grid with colored-dot headers, version/required/active badges, base label mapping and examples sections, and a 460 px right-anchored slide-over for create/edit.

The portal already has: `SlideOver` (accessible, Escape/Tab trap, backdrop), TanStack Query, `authFetch`, `useAuth` (exposes `user.tenantSlug`), and toast patterns from training-jobs.

## Goals / Non-Goals

**Goals:**

- Replace the placeholder with a fully interactive entity types management screen matching the mockup
- Implement list, create, edit, and activate/deactivate flows via the existing backend API
- Follow established portal patterns (TanStack Query hooks, `SlideOver`, `authFetch`, toast on mutation)

**Non-Goals:**

- Backend schema changes (no new column for hue/color — computed client-side from index)
- Validation rule or `target_table` fields in the create/edit form (not shown in mockup)
- Pagination (backend returns all active/inactive entity types for a tenant; count is manageable)
- Bulk operations

## Currently-In-Force ADRs

| ADR | Decision Summary | Constraint on This Design |
|-----|-----------------|--------------------------|
| ADR-001: Tenant Data Isolation | All data is isolated per tenant via separate schemas; API endpoints are tenant-scoped | Entity types API calls MUST include `tenantSlug` in the URL path: `/api/v1/tenants/{slug}/entity-types` |
| ADR-002: Single Base Model (partially superseded by ADR-008) | Base model uses CoNLL labels PER/ORG/LOC/MISC | Base model label chips in the form are limited to those four values |

## Decisions

### Decision 1: One spec (`entity-types-screen`) covering page + hooks + components

**Choice:** Deliver the entire entity types UI as a single capability spec rather than splitting hooks into a separate `entity-types-api-client` spec.

**Rationale:** The hooks are simple (list + three mutations); they are only consumed by this one page. Splitting would add overhead with no reuse benefit at this stage.

**Alternatives considered:**
- Separate `entity-types-api-client` spec — ruled out because the hooks have no current cross-screen consumers and a single-spec boundary is easier to verify and implement atomically.

### Decision 2: Hue assigned client-side by index mod 7

**Choice:** Entity type card colors (the colored dot) are derived from `index % 7` mapping to fixed hues `[25, 330, 235, 285, 155, 200, 60]`, matching the mockup's JS logic exactly. Hue is NOT stored server-side.

**Rationale:** Avoids a backend schema migration. The mockup itself uses this index-mod approach. The visual result is stable as long as sort order is deterministic (server returns by `created_at` asc).

**Alternatives considered:**
- Store `hue` column server-side — ruled out as an unnecessary backend change for a pure-visual property.
- Random hue per create call — ruled out because colors would change on page refresh.

### Decision 3: Reuse existing `SlideOver` primitive

**Choice:** `DefineEntityTypeSlideOver` composes the existing `SlideOver` component (width=460).

**Rationale:** `SlideOver` already handles Escape key, focus trap, backdrop click, and accessibility (`role="dialog"`, `aria-modal`). Reusing it keeps the modal behavior consistent with the training-jobs submit modal.

**Alternatives considered:**
- Center modal — ruled out; mockup shows right-anchored panel, and `SlideOver` is already built for this pattern.

### Decision 4: Separate components, not a monolith page file

**Choice:** Break the page into `EntityTypeCard`, `DefineEntityTypeSlideOver`, and a thin `EntityTypesPage` orchestrator. Hooks live in `src/portal/src/hooks/`.

**Rationale:** Mirrors the training-jobs structure (job-card, submit-job-slideover, job-list, page), keeps files testable in isolation, and follows the existing component naming convention.

## Risks / Trade-offs

- [No `target_table` or `validation_rule` in form] → Acceptable for v1; backend accepts null for those fields. Can be added in a follow-up without breaking changes.
- [Color stability depends on server sort order] → Use `created_at asc` ordering; document this assumption in the hook. If order changes, colors shift — acceptable cosmetic risk.
- [Optimistic toggle without rollback UI] → On toggle failure, show error toast and invalidate the query to refetch. No inline rollback needed at this scale.

## Migration Plan

1. Add hooks (`use-entity-types.ts`, `use-create-entity-type.ts`, `use-update-entity-type.ts`, `use-toggle-entity-type.ts`) under `src/portal/src/hooks/`
2. Add components (`EntityTypeCard`, `DefineEntityTypeSlideOver`) under `src/portal/src/components/entity-types/`
3. Replace `PlaceholderScreen` in `src/portal/src/app/(auth)/entity-types/page.tsx` with `EntityTypesPage`
4. No backend changes, no DB migrations, no env var changes — frontend-only deployment

**Rollback:** Revert the page to `PlaceholderScreen`. No data is mutated by frontend code alone.

## Open Questions

- None — all open questions from the proposal are resolved by this design.
