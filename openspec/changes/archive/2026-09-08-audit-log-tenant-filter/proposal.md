## Why

The System Admin Audit Log (`/admin/audit-log` API, `/audit` page) shows every platform event in one chronological list with no way to scope it to a tenant. As tenant count and event volume grow, a System Admin investigating a single tenant has to scan the entire cross-tenant stream. Adding a tenant filter lets admins narrow the view on demand while keeping the current all-tenants view as the default.

## What Changes

- Extend `GET /api/v1/admin/audit-log` with an optional `tenant_id` query parameter. Omitted (or empty), behavior is unchanged — all tenants, current pagination and ordering.
- When `tenant_id` is supplied, `AuditService.list_events` filters both the count and paginated SELECT to that tenant's events only (`WHERE tenant_id = :tenant_id`), preserving `ORDER BY created_at DESC` and offset pagination.
- Add a searchable Tenant filter combobox to the `/audit` page, placed above the event list near the page title/metadata line.
- Default option is "All Tenants"; tenants below it are sourced from the existing `GET /api/v1/admin/tenants` endpoint (requested with a page size large enough to list all tenants, since there is no dedicated "all tenants, no pagination" endpoint today).
- Selecting a tenant re-fetches the audit log scoped to that tenant and resets pagination to page 1; switching back to "All Tenants" restores the full history.
- Selected tenant is held in page-local React state (not persisted across navigation/reload).
- Add an empty-state message for "no audit events for this tenant" distinct from the existing generic empty state.

## Capabilities

### New Capabilities

- `audit-log`: Audit log viewing and filtering — the `/api/v1/admin/audit-log` endpoint and `/audit` page behavior, including the new tenant scoping. (No existing spec currently covers this area; `admin-console` covers tenant management only.)

### Modified Capabilities

- (none — no existing spec requirements change; `admin-console`'s tenant-listing requirement is reused as-is, not modified)

## Impact

- Backend: `src/gateway/api/v1/admin.py` (`list_audit_log` route), `src/gateway/services/audit_service.py` (`list_events` SQL).
- Frontend: `src/portal/src/app/(auth)/audit/page.tsx`, `src/portal/src/hooks/use-audit-log.ts`.
- New frontend component: a searchable combobox (no such component exists in `src/portal/src/components/ui` today — closest precedent is the non-searchable native `FilterSelect` in `src/portal/src/components/ui/filter-select.tsx`, which will inform styling but not be reused directly since it isn't searchable).
- Reuses existing `GET /api/v1/admin/tenants` endpoint and `Tenant` model; no new backend endpoint for tenant listing.
- Tests: `src/portal/src/app/(auth)/audit/page.test.tsx`, `src/portal/src/hooks/use-audit-log.test.tsx`, and backend tests for `AuditService`/`admin.py` audit route (existing test files to be located during implementation).

## Open Questions

- `GET /api/v1/admin/tenants` is paginated (`per_page` max 100). If a deployment ever has more than 100 tenants, a single fetch won't list them all. Given no evidence of tenant counts near that scale, this proposal fetches with `per_page=100` and accepts that ceiling rather than adding a new unpaginated endpoint; revisit if tenant counts approach it.
- Should deactivated/inactive tenants still appear in the filter dropdown (their historical events still exist)? Proposal assumes yes — filter is about audit history, not current tenant status — but flagging for confirmation.
