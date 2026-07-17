## 1. Data Model & Migration

- [x] 1.1 Add `AuditEventKind` enum to `src/gateway/models/__init__.py` with values: `create`, `approve`, `promote`, `complete`, `run`, `reject`, `update`
- [x] 1.2 Add `AuditEvent` SQLAlchemy model to `src/gateway/models/__init__.py` with columns: `id` (UUID str PK), `actor` (str, not null), `role` (str, not null), `action` (str, not null), `target` (str, not null), `kind` (AuditEventKind, not null), `tenant_id` (nullable str FK to public.tenants.id), `created_at` (DateTime tz)
- [x] 1.3 Create Alembic migration `020_create_audit_events_table` — creates `public.audit_events` table with an index on `created_at DESC`

## 2. Backend: Audit Service & API

- [x] 2.1 Create `src/gateway/services/audit_service.py` with `AuditService(db)` class:
  - `record(actor, role, action, target, kind, tenant_id=None)` method that inserts into `public.audit_events`
  - `list_events(page=1, per_page=50)` method returning paginated results with `{"events": [...], "total": int, "page": int, "per_page": int}` ordered by `created_at DESC`
- [x] 2.2 Add `GET /api/v1/admin/audit-log` route in `src/gateway/api/v1/admin.py` → calls `AuditService.list_events()` with `require_system_admin` guard

## 3. Backend: Wire Audit Recording at Action Sites

- [x] 3.1 In `src/gateway/services/tenant_service.py` → `deactivate_tenant()`: record audit event with kind `reject`, action `tenant.deactivate`, target = tenant slug
- [ ] ~~3.2 In `src/gateway/services/entity_service.py` → `create_entity_type()`: record audit event with kind `create`, action `entity_type.create`, target = entity name~~ *(per user decision — entity type events not wanted)*
- [ ] ~~3.3 In `src/gateway/services/entity_service.py` → `update_entity_type()`: record audit event with kind `update`, action `entity_type.update`, target = entity name~~ *(per user decision)*
- [ ] ~~3.4 In `src/gateway/services/entity_service.py` → `toggle_entity_type()`: record audit event with kind `update`, action `entity_type.toggle`, target = entity name~~ *(per user decision)*
- [x] 3.5 In `src/gateway/services/tenant_service.py` → `create_tenant()`: record audit event with kind `create`, action `tenant.create`, target = tenant slug
- [x] 3.6 In `src/training_service/api/v1/training_jobs.py` → `create_training_job()`: record audit event with kind `create`, action `training_job.submit`, target = job_id
- [x] 3.7 In `src/training_service/api/v1/training_jobs.py` → `approve_training_job()`: record audit event with kind `approve`, action `training_job.approve`, target = job_id
- [x] 3.8 In `src/training_service/api/v1/training_jobs.py` → `reject_training_job()`: record audit event with kind `reject`, action `training_job.reject`, target = job_id
- [x] 3.9 In `src/training_service/api/v1/models.py` → `promote_model()`: record audit event with kind `promote`, action `model_version.promote`, target = version_id

## 4. Frontend: Hook & Data Fetching

- [x] 4.1 Create `src/portal/src/hooks/use-audit-log.ts`:
  - `useAuditLog(page, perPage)` hook using `authFetch` against `GATEWAY_URL/api/v1/admin/audit-log`
  - Returns `{ data, isLoading, error, refetch }` — data shape: `{ events, total, page, per_page }`
- [x] 4.2 Export the hook from `src/portal/src/hooks/index.ts`

## 5. Frontend: Audit Log Page

- [x] 5.1 Create `src/portal/src/app/(auth)/audit/page.tsx` replacing the PlaceholderScreen:
  - Page header with "Audit Log" title and event count subtitle (e.g., "tenant.audit_log · 42 events")
  - Timeline list matching mockup exactly: each event shows colored dot (11px), action name (JetBrains Mono 13px bold), kind badge (pill with mockup colors), target/actor line, and timestamp
  - Kind-to-color mapping matching mockup: `create`=blue, `approve`=green, `promote`=orange, `complete`=green, `run`=blue, `reject`=red, `update`=yellow
  - Empty state: shows "0 events" count with empty timeline
  - Pagination controls at bottom (prev/next buttons)
  - Styling: Tailwind classes matching the mockup's visual output (1040px max-width container, border-bottom dividers between rows)

## 6. Backend: Tests

- [x] 6.1 Write unit test for `AuditService.record()` — verify insert and field correctness
- [x] 6.2 Write unit test for `AuditService.list_events()` — verify pagination, ordering, total count
- [x] 6.3 Write API integration test for `GET /api/v1/admin/audit-log` — system admin can list events (row 6 in Spec Alignment)
- [x] 6.4 Write API integration test — tenant_admin receives 403 (row 7 in Spec Alignment)

## 7. Frontend: Tests

- [x] 7.1 Write component test for audit page — renders event rows with correct structure
- [x] 7.2 Write component test for audit page — empty state renders correctly
- [x] 7.3 Write hook test for `use-audit-log` — fetches and returns paginated data

## 8. Verification & Evidence

- [x] 8.1 Run all acceptance-criteria tests for every scenario in verification.md § Spec Alignment and confirm all pass.
- [x] 8.2 Collect functional evidence (screenshot / test output / log) for each scenario — record one entry per row in verification.md § Evidence Log.
- [x] 8.3 Confirm every Hallucination Risk mitigation step in verification.md § Hallucination Risk Register.
- [x] 8.4 Confirm all ADR compliance steps in verification.md § Pattern & ADR Compliance.
- [ ] 8.5 Complete Audit Record sign-off in verification.md § Audit Record (human reviewer required — this task cannot be marked complete by an agent).
- [x] 8.6 Run `openspec validate audit-log-page --type change --strict` and confirm it exits clean before archive.
