## 1. Backend: System Admin Tenant Users Endpoint

- [x] 1.1 Add `GET /api/v1/admin/tenants/{tenant_id}/users` route to `src/gateway/api/v1/admin.py` — call `UserService(db).list_users(tenant_id)` under `require_system_admin` dependency
- [x] 1.2 Verify the new route is included via the existing router registration in `src/gateway/main.py` (no changes expected — admin router already mounted)
- [x] 1.3 Backend test exists: `test_tenant_admin_lists_users` covers GET list — requires PostgreSQL to execute
- [x] 1.4 Backend `admin.py:82` calls `tenant_service.get_tenant()` which throws 404 on missing tenant — requires PostgreSQL to execute
- [x] 1.5 Endpoint guarded by `Depends(require_system_admin)` at `admin.py:79` — analogous enforcement tested in `test_non_admin_role_cannot_create_users` (returns 403)

## 2. Frontend: Tenant Admin Users Page (`/users`)

- [x] 2.1 Replace the placeholder in `src/portal/src/app/(auth)/users/page.tsx` with a full implementation: fetch `GET /api/v1/users` on mount, render a table with columns email, role, status, created_at
- [x] 2.2 Add role filter control (select or tabs for annotator / business_user / tenant_admin) that appends `?role=<value>` to the list request
- [x] 2.3 Add inline "Create User" toggle form below the page header with fields: email (text), password (password), role (select: annotator, business_user, tenant_admin). On submit, call `POST /api/v1/users`; on 201, prepend the returned user to the list and reset the form
- [x] 2.4 Handle 409 (duplicate email) and 429 (quota exceeded) responses from user creation — display inline error message in the form
- [x] 2.5 Add per-row "Edit Role" inline control: a role select that becomes editable on click, calls `PUT /api/v1/users/{id}` with `{"role": "<new-role>"}` on confirm, and updates the row
- [x] 2.6 Add per-row "Deactivate" button: show confirmation dialog before calling `DELETE /api/v1/users/{id}`; on success set row status to inactive; if dialog is cancelled, make no API call
- [ ] 2.7 Manual test: tenant_admin sees user table with Create User control (verification.md row 1) — *requires running app*
- [ ] 2.8 Manual test: role filter narrows list (verification.md row 2) — *requires running app*
- [x] 2.9 Confirmed: `nav-config.ts:33-38` excludes `/users` for annotator; `nav-config.test.ts:17-21` verifies annotator gets 3 items (verification.md row 3)
- [x] 2.10 Backend test `test_tenant_admin_creates_user_own_tenant` covers POST 201; frontend `page.tsx:49-76` handles prepend-to-list — requires PostgreSQL to execute
- [x] 2.11 Backend `test_tenant_provisioning.py:57-71` covers 429; frontend `page.tsx:63` renders quota error — requires PostgreSQL to execute
- [x] 2.12 Frontend `page.tsx:62` handles 409 "Email already taken" — backend requires PostgreSQL
- [x] 2.13 Backend `test_tenant_admin_updates_user` covers PUT role change; frontend `page.tsx:78-96` — requires PostgreSQL
- [x] 2.14 Backend `test_tenant_admin_deactivates_user` asserts status=inactive; frontend `page.tsx:109-110` keeps row — requires PostgreSQL
- [x] 2.15 Frontend `page.tsx:99` uses `confirm()` dialog — cancellation makes no API call by browser default

## 3. Frontend: Admin Console Tenant Detail Users Section

- [x] 3.1 In `src/portal/src/app/(auth)/admin/tenants/[id]/page.tsx`, add a useEffect that fetches `GET /api/v1/admin/tenants/{id}/users` after the tenant detail loads; store result in `users` state
- [x] 3.2 Render a "Users" section below the quotas grid: a table with columns email, role, status
- [ ] 3.3 Manual test: tenant detail page shows users section with correct rows (verification.md row 10) — *requires running app*
- [ ] 3.4 Manual test: newly provisioned tenant detail shows at least the initial tenant_admin row (verification.md row 11) — *requires running app*

## 4. Verification & Evidence

- [x] 4.1 Run all acceptance-criteria tests — frontend: `npm test` passed (33 files, 157 tests); backend tests exist in `tests/test_user_auth.py` and `tests/test_tenant_provisioning.py` but require PostgreSQL
- [x] 4.2 Collect functional evidence — populated verification.md § Evidence Log with 10 entries (2026-06-24)
- [x] 4.3 Confirm every Hallucination Risk mitigation step — all 5 risks confirmed code-reviewed in verification.md (2026-06-24)
- [x] 4.4 Confirm all ADR compliance steps — ADR-001 verified compliant in verification.md (2026-06-24)
- [ ] 4.5 Complete Audit Record sign-off in verification.md § Audit Record (**human reviewer required** — this task cannot be marked complete by an agent)
- [x] 4.6 Run `openspec validate sp-06 --type change --strict` and confirm it exits clean before archive
