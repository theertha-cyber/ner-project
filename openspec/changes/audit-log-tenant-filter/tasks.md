## 1. Backend: Tenant Filter on Audit Log Endpoint

- [x] 1.1 Add optional `tenant_id: str | None = Query(None)` parameter to `list_audit_log` in `src/gateway/api/v1/admin.py:121-129` and pass it through to `AuditService.list_events`.
- [x] 1.2 Update `AuditService.list_events` in `src/gateway/services/audit_service.py:50-83` to accept `tenant_id: str | None = None` and conditionally append `WHERE tenant_id = :tenant_id` (bound parameter, not string interpolation) to both the `COUNT(*)` query and the paginated `SELECT` query.
- [x] 1.3 Add/extend backend tests covering: no `tenant_id` (unchanged behavior), `tenant_id` with matching events, `tenant_id` with zero matching events — locate or create the test file for `AuditService`/`admin.py` audit route.

## 2. Frontend: Searchable Tenant Combobox Component

- [x] 2.1 Create `src/portal/src/components/ui/searchable-combobox.tsx`: a text-input-driven combobox that filters a client-supplied option list, styled with the same CSS variables as `src/portal/src/components/ui/filter-select.tsx` (`--surface-3`, `--ink`, `--ink-3`, `--line`).
- [x] 2.2 Add a component test file (e.g. `searchable-combobox.test.tsx`) covering: typing filters options, selecting an option calls `onChange` and closes the dropdown, clicking outside closes it.

## 3. Frontend: Wire Tenant Filter into Audit Page

- [x] 3.1 Update `src/portal/src/hooks/use-audit-log.ts`: add optional `tenantId` param to `useAuditLog`, include it in the `queryKey`, and append `tenant_id` to the query string only when set.
- [x] 3.2 Add a `useTenants` (or reuse/add) hook that fetches `GET /api/v1/admin/tenants?per_page=100` (no `status` filter) for the combobox options, cached under its own query key.
- [x] 3.3 Update `src/portal/src/app/(auth)/audit/page.tsx`: add `selectedTenantId` state (default `null`/all), render the `SearchableCombobox` above the event list near the title/metadata block with "All Tenants" as the first option followed by tenants from 3.2.
- [x] 3.4 On tenant selection change, update `selectedTenantId` and reset `page` to `1`; pass `selectedTenantId` into `useAuditLog`.
- [x] 3.5 Add a tenant-specific empty-state message (e.g. "No audit events for this tenant") distinct from the existing generic empty state, shown when `selectedTenantId` is set and `data.events.length === 0`; ensure pagination controls are hidden in this case (already covered by existing `totalPages > 1` guard, but verify with a tenant that has zero events).

## 4. Verification & Evidence

- [x] 4.1 Run all acceptance-criteria tests for every scenario in verification.md § Spec Alignment and confirm all pass.
- [x] 4.2 Collect functional evidence (screenshot / test output / log) for each scenario — record one entry per row in verification.md § Evidence Log.
- [x] 4.3 Confirm every Hallucination Risk mitigation step in verification.md § Hallucination Risk Register.
- [x] 4.4 Confirm all ADR compliance steps in verification.md § Pattern & ADR Compliance.
- [ ] 4.5 Complete Audit Record sign-off in verification.md § Audit Record (human reviewer required — this task cannot be marked complete by an agent).
- [x] 4.6 Run `openspec validate audit-log-tenant-filter --type change --strict` and confirm it exits clean before archive.
