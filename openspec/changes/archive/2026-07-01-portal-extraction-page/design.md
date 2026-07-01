## Context

The `/extractions` page currently renders a `<PlaceholderScreen>` for the `business_user` role. All backend extraction APIs are implemented and stable: real-time inference (`POST /api/v1/extract`), batch extraction (`POST /api/v1/extract-batch`, `GET /api/v1/extract-batch/{run_id}`), entity listing and filtering (`GET /api/v1/entities`), and entity review (`PATCH /api/v1/entities/{id}`). This design covers the frontend only — no backend changes are required.

The portal uses Next.js App Router, Tailwind CSS, and the `authFetch` wrapper for authenticated API calls. Feature components live under `src/portal/src/components/<feature>/`. Pages are thin shells that compose feature components. The training-jobs page (split panel: list left, detail right) and the annotation workspace (multi-pane with tab-like switching) are the closest structural precedents.

## Goals / Non-Goals

**Goals:**
- Replace the placeholder with a working three-tab workspace: Playground, Batch Runs, Entity Review
- Match the mockup layout and visual style exactly
- Use existing portal patterns: `authFetch`, Tailwind token classes, `SegmentControl` UI primitive, `Badge` component, spinner pattern

**Non-Goals:**
- Backend changes or new API endpoints
- Role access control changes (the nav already exposes Extractions to `business_user` only)
- Pagination on the entity list (first iteration fetches all, adding pagination is a follow-up)
- Websocket / SSE real-time polling for batch progress (use interval polling with `setInterval`)

## Currently-In-Force ADRs

| ADR | Decision Summary | Constraint on This Design |
|-----|-----------------|--------------------------|
| ADR-001: Tenant Data Isolation | All data is tenant-scoped; never mix tenant data | All API calls are JWT-authenticated; `authFetch` attaches the bearer token automatically — no explicit tenant ID is needed in URLs (`/api/v1/extract` not `/api/v1/tenants/{tid}/extract`) |
| ADR-003: Per-Tenant Model Serving | Each tenant's extraction routes to their promoted model via the serving pool | Frontend is unaware of serving topology; it calls `/api/v1/extract` and receives `model_version` in the response — display it as "model v{N} · serving" |
| ADR-008: Base Model as Default | If no fine-tuned model is promoted, extraction uses base model (v0, CoNLL labels) | Frontend must not assume a promoted model exists; when `model_version === "0"` the entity types will be CoNLL standard (PER, ORG, LOC, MISC), not custom types — this is valid and expected |

## Decisions

### Decision 1: Tab state in component state, not URL

**Choice:** `useState<'playground' | 'batch' | 'entities'>('playground')` — no URL query param for the active tab.

**Rationale:** The three tabs are content modes within the same page, not navigable destinations. Unlike the training-jobs page where `?selected=` is used to make a specific job deep-linkable, the extraction tabs have no shareable state worth encoding in the URL. Keeping it in component state is simpler and consistent with how the mockup models it.

**Alternatives considered:**
- `?tab=playground` in URL — adds unnecessary URL complexity for state that doesn't need to be bookmarkable or shareable

### Decision 2: One page component, sub-components per tab

**Choice:** A single `ExtractionPage` component (`src/portal/src/components/extractions/ExtractionPage.tsx`) owns the tab state and renders one of three tab sub-components: `PlaygroundTab`, `BatchRunsTab`, `EntityReviewTab`. The page shell at `src/portal/src/app/(auth)/extractions/page.tsx` simply renders `<ExtractionPage />`.

**Rationale:** Mirrors the annotation workspace pattern (`AnnotationPage.tsx` is the main component, page.tsx is the shell). Each tab is complex enough to warrant its own file but they share tab state managed by the parent.

**Alternatives considered:**
- Three separate routes under `/extractions/playground`, `/extractions/batch`, `/extractions/entities` — over-engineered for this scope; tabs are not separate pages

### Decision 3: Custom hooks for each data concern

**Choice:** Three hooks following the existing `use-*` naming pattern:
- `useExtract()` — manages playground text state, running state, and calls `POST /api/v1/extract`
- `useBatchRuns()` — fetches batch run list, handles "New batch run" trigger, polls in-progress runs every 3s
- `useEntities(filter)` — fetches entity list with review-status filter, handles confirm/reject mutations

**Rationale:** Decouples data from presentation, consistent with `useTrainingJobs` / `useTrainingJob` pattern. Polling is handled inside `useBatchRuns` with `useEffect` + `setInterval`, cleared when no runs are in-flight.

**Alternatives considered:**
- Inline fetch logic in components — harder to test and violates the existing hook pattern
- SWR/React Query for polling — not used elsewhere in the codebase; `authFetch` + `useState` is the established pattern

### Decision 4: Batch Runs layout mirrors training-jobs split panel

**Choice:** `BatchRunsTab` uses a 340px-wide left list of run cards + a right detail panel, matching the mockup and the training-jobs structural precedent.

**Rationale:** The mockup shows this exact layout: `grid-template-columns: 340px 1fr`. The training-jobs page already implements a similar pattern, so the same structural approach (left list, right detail) is well understood by the codebase.

**Alternatives considered:**
- Accordion rows — mockup shows a master-detail split, not an accordion

### Decision 5: Entity review uses filter pills, not tabs

**Choice:** `EntityReviewTab` renders a row of filter pills (`all` / `unreviewed` / `confirmed` / `corrected` / `rejected`) controlling a `filter` state string. On filter change, re-fetch `GET /api/v1/entities?reviewStatus=<filter>` (omit param for `all`). Confirm/Reject buttons call `PATCH /api/v1/entities/{id}` and optimistically update the row.

**Rationale:** Matches the mockup exactly. Optimistic updates keep the UI snappy without a loading state per row.

**Alternatives considered:**
- Client-side filter over a full entity list fetch — wastes memory for large datasets; server-side filter is the correct approach

## Risks / Trade-offs

- [`POST /api/v1/extract` may be gated to `tenant_admin` only] → If the gateway returns 403 for `business_user`, the Playground tab will show an error state. The open question in the proposal covers this; if confirmed, a single-line gateway permission change resolves it without touching frontend code.
- [Polling interval for batch runs may cause excessive requests] → 3-second interval is only active when at least one run is `running` or `queued`; the interval is cleared immediately when all runs are terminal states.
- [Entity list without pagination may be slow for large tenants] → Acceptable for v1; the spec explicitly defers pagination. The `GET /api/v1/entities` endpoint is already paginated server-side; adding a "Load more" button is a straightforward follow-up.

## Migration Plan

1. Replace the `PlaceholderScreen` import in `extractions/page.tsx` with `ExtractionPage`
2. Add `src/portal/src/components/extractions/` directory with all new component and hook files
3. No database migrations, no backend deploys, no environment variable changes required
4. Rollback: revert the one-line change in `page.tsx` — the placeholder is still importable

## Open Questions

- **Gateway permissions for `business_user` on `POST /api/v1/extract`**: The extraction-service spec says annotators get 403, but `business_user` is not mentioned. Needs confirmation before the Playground tab can be marked fully verified.
Answer: Extraction service and page should be available for business users and tenant admins. 