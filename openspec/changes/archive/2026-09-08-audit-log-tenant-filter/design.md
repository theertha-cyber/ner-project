## Context

`GET /api/v1/admin/audit-log` (`src/gateway/api/v1/admin.py:121-129`) is served by `AuditService.list_events` (`src/gateway/services/audit_service.py:50-83`), which runs two raw `text()` SQL statements against `public.audit_events` — a `COUNT(*)` and a `SELECT ... ORDER BY created_at DESC LIMIT :limit OFFSET :offset` — with no `WHERE` clause today. `audit_events.tenant_id` already exists (nullable, since some actions are system-level with no tenant). The frontend `/audit` page (`src/portal/src/app/(auth)/audit/page.tsx`) fetches via `useAuditLog(page, perPage)` (`src/portal/src/hooks/use-audit-log.ts`), using classic Prev/Next pagination against `{events, total, page, per_page}`.

Tenant options for the filter come from the existing `GET /api/v1/admin/tenants` endpoint (`TenantService.list_tenants`), which is itself paginated (`per_page` max 100, default 20).

No searchable combobox component exists anywhere in `src/portal/src`; the closest precedent is `FilterSelect` (`src/portal/src/components/ui/filter-select.tsx`), a styled native `<select>` — not searchable, and not usable directly since it doesn't support type-to-filter.

## Goals / Non-Goals

**Goals:**
- Add optional server-side tenant filtering to the existing audit-log endpoint without duplicating it.
- Add a searchable tenant combobox to the `/audit` page, defaulting to "All Tenants".
- Preserve existing chronological ordering and Prev/Next pagination semantics exactly when no filter is applied.

**Non-Goals:**
- No date-range, actor, kind, or other new filter dimensions — tenant only.
- No change to the pagination *mechanism* (still offset-based Prev/Next) — a switch to cursor/infinite-scroll pagination is out of scope.
- No new "list all tenants unpaginated" endpoint — the filter reuses `GET /api/v1/admin/tenants` as-is.
- No persistence of the selected tenant across page reloads/navigation (in-memory state only, per requirements).

## Currently-In-Force ADRs

| ADR | Decision Summary | Constraint on This Design |
|-----|-------------------|--------------------------|
| ADR-001 (tenant-data-isolation) | Per-tenant PostgreSQL schemas; `public` schema reserved for migration tracking, except System Admin cross-tenant reporting uses a controlled cross-schema/reporting path. | `audit_events` and `tenants` already live in `public` schema as pre-existing System Admin reporting data (not changed by this proposal). Filtering by `tenant_id` column is additive SQL on an existing table/column — no new cross-schema access pattern is introduced. |
| ADR-004 (openspec-governance) | Changes to this repo follow the OpenSpec spec-driven workflow. | This change is proposed via that workflow (this document). |

Other ADRs (002, 003, 005, 006, 007, 008, 009) concern model strategy, serving topology, agent boundaries, training infra, chat/RAG, and training hyperparameters — none constrain audit log filtering.

## Decisions

### Decision 1: Filter via a single optional query parameter, applied in both SQL statements

**Choice:** Add `tenant_id: str | None = Query(None)` to the `GET /api/v1/admin/audit-log` route and pass it through to `AuditService.list_events(page, per_page, tenant_id=None)`. Inside the service, build the `WHERE tenant_id = :tenant_id` clause conditionally and apply it to *both* the `COUNT(*)` query and the paginated `SELECT`, so `total`/`totalPages` stay correct for the filtered set.

**Rationale:** Matches the existing pattern for optional filters elsewhere in this file (`list_tenants`'s `status_filter`). Keeps one endpoint, one code path; omitted param is a strict no-op (same SQL text executes as today when `tenant_id` is `None`).

**Alternatives considered:**
- New endpoint `GET /api/v1/admin/audit-log/by-tenant/{tenant_id}` — rejected: proposal explicitly says do not duplicate endpoints, and it fragments pagination logic across two code paths.
- Move from raw `text()` SQL to SQLAlchemy Core/ORM query building — rejected as out of scope; the existing file's pattern is deliberate (see sibling `record()` method), and a broader ORM migration is a separate concern from this feature.

### Decision 2: Tenant options fetched via existing `/admin/tenants?per_page=100`

**Choice:** The frontend combobox loads tenant options with a single `useQuery` call to `GET /api/v1/admin/tenants?per_page=100` (no `status` filter, so both active and deactivated tenants appear — their historical audit events still exist and should remain filterable). Cached under its own query key so it does not refetch on every page/tenant filter change.

**Rationale:** Reuses an existing, already-authorized endpoint; avoids building and maintaining a second tenant-listing code path for one dropdown.

**Alternatives considered:**
- New unpaginated `GET /api/v1/admin/tenants/all` endpoint — rejected: adds backend surface for a problem (>100 tenants) that isn't confirmed to exist yet; flagged as an open question instead.
- Fetch tenants lazily as the admin types in the combobox (server-side search) — rejected: `list_tenants` has no name-search param today, and client-side filtering of ≤100 tenants is simpler and fast enough.

### Decision 3: New lightweight `SearchableCombobox` UI component, styled to match `FilterSelect`

**Choice:** Build a small new component (e.g. `src/portal/src/components/ui/searchable-combobox.tsx`) — a text input that filters a client-side option list and opens a dropdown listbox on focus — using the same CSS custom properties (`--surface-3`, `--ink`, `--ink-3`, `--line`) and general visual language as `FilterSelect`. No new dependency.

**Rationale:** No combobox exists in the project (confirmed: no cmdk/downshift/Radix in `package.json`, no matches for Combobox/Autocomplete in `src/portal/src`). Requirements call for reusing existing patterns; matching `FilterSelect`'s styling tokens keeps it visually native without pulling in a new UI library for one control.

**Alternatives considered:**
- Add a combobox library (Radix UI, `cmdk`, `downshift`) — rejected: introduces a new dependency and design pattern for a single use site; requirements prefer reuse over new patterns.
- Reuse `FilterSelect` as-is (native `<select>`) — rejected: native `<select>` has no type-to-filter/search behavior, which the requirements explicitly ask for ("searchable dropdown").

### Decision 4: Selecting a tenant resets pagination to page 1

**Choice:** In `AuditPage`, changing the selected tenant sets `page` back to `1` alongside updating the tenant filter state, and `useAuditLog` includes `tenantId` in its `queryKey` and query string.

**Rationale:** A filtered result set has a different `total`/`totalPages`; keeping a stale `page` value could request an out-of-range offset (empty page) after narrowing to a smaller tenant.

**Alternatives considered:**
- Leave `page` untouched — rejected: would frequently land on an empty page after filtering.

## Risks / Trade-offs

- [Adding a `WHERE` clause built from an f-string-adjacent conditional could reintroduce SQL injection if not parameterized] → Use SQLAlchemy `text()` bound parameters (`:tenant_id`) exactly as the existing `record()` method does; never interpolate the tenant id directly into the SQL string.
- [`GET /api/v1/admin/tenants?per_page=100` silently truncates if tenant count exceeds 100] → Documented as an open question in the proposal; acceptable for current scale, revisit with a dedicated endpoint if tenant count approaches the limit.
- [New `SearchableCombobox` is a bespoke component with its own keyboard/focus/accessibility behavior to get right (arrow keys, Escape, click-outside)] → Keep the first version minimal (text filter + click/select), covered by component tests; expand interaction coverage if reused elsewhere later.
- [Filtering by `tenant_id = NULL` for system-level events is not directly reachable via this UI] → Out of scope per proposal (only real tenants are listed); "All Tenants" already surfaces these events in the unfiltered view.

## Migration Plan

- Backend and frontend changes ship together in one PR; no data migration needed (`tenant_id` column already exists on `audit_events`).
- No feature flag — additive query parameter defaults to today's behavior when omitted, so existing callers (including the current frontend before it's updated) are unaffected during rollout.
- Rollback: revert the PR; no schema or data changes to unwind.

## Open Questions

- Confirmed via proposal: deactivated tenants remain selectable in the filter (their audit history persists). No ADR conflict.
- If tenant counts approach the `per_page=100` ceiling on `/admin/tenants`, a dedicated unpaginated or search-based tenant-listing endpoint should be considered — not needed now.
