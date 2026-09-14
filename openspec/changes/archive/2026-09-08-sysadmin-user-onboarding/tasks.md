## 1. Backend: Shared Service Extensions

- [x] 1.1 Extend `UserService.create_user` in `src/gateway/services/user_service.py` to select `status` alongside `max_users` in its existing tenant/quota lookup, and raise `TenantInactiveError` (already defined in `src/shared/exceptions.py`, 403) if the tenant is not `active`, before the quota/uniqueness checks.
- [x] 1.2 Extend `UserService.create_user` to accept `actor_email: str = ""` and `actor_role: str = ""` and, on successful creation, call `AuditService(self.db).record(actor=actor_email, role=actor_role, action="user.create", target=email, kind=AuditEventKind.create, tenant_id=tenant_id)` — mirroring the pattern in `TenantService.create_tenant` ([tenant_service.py:84-91](src/gateway/services/tenant_service.py:84)).
- [x] 1.3 Confirm no new or combined authorization dependency is added to `src/gateway/dependencies.py` — `require_tenant_admin` and `require_system_admin` stay exactly as they are.

## 2. Backend: Admin User Creation Endpoint

- [x] 2.1 Add `POST /api/v1/admin/tenants/{tenant_id}/users` to `src/gateway/api/v1/admin.py`, gated by `Depends(require_system_admin)`, taking `tenant_id` from the path, validating the tenant exists via `TenantService.get_tenant(tenant_id)` (404 if missing), then calling `UserService(db).create_user(tenant_id, payload.model_dump(), actor_email=request.state.user_email, actor_role=request.state.role)`. Reuse the `CreateUserRequest` schema shape from `users.py` (import it or define an identical one) so the request body matches `POST /api/v1/users` exactly.
- [x] 2.2 Update `src/gateway/api/v1/users.py`'s `create_user` handler to pass `actor_email`/`actor_role` from `request.state` into `UserService.create_user`, so the existing Tenant Admin path also gets audit logging (no change to its route signature, status codes, or auth dependency).
- [x] 2.3 Confirm existing exception handlers map `TenantInactiveError` → 403, `NotFoundError` → 404, `QuotaExceededError` → 429, `ConflictError` → 409, `ValidationError` → 400/422 consistently for both routes.

## 3. Backend Tests

- [x] 3.1 Add test `test_admin_creates_business_user_in_target_tenant` (verification.md row 1).
- [x] 3.2 Add test `test_admin_creates_tenant_admin_in_target_tenant` (row 2).
- [x] 3.3 Add test `test_admin_creates_annotator_in_target_tenant` (row 3).
- [x] 3.4 Add test `test_admin_create_user_nonexistent_tenant_returns_404` (row 4).
- [x] 3.5 Add test `test_admin_create_user_quota_exceeded_returns_429` (row 5).
- [x] 3.6 Add test `test_admin_create_user_duplicate_email_in_tenant_returns_409` (row 6).
- [x] 3.7 Add test `test_admin_create_user_rejects_non_system_admin_403` (row 7).
- [x] 3.8 Add test `test_admin_create_user_requires_auth_401` (row 8).
- [x] 3.9 Add test `test_admin_create_user_inactive_tenant_returns_403` (row 9) asserting `UserService.create_user` rejects a target tenant with `status: "inactive"`.
- [x] 3.10 Add test `test_admin_create_user_tenant_deactivated_after_form_load_returns_403` (row 10) — deactivate the tenant between the initial `get_tenant` existence check setup and the `create_user` call, assert 403.
- [x] 3.11 Add regression test `test_tenant_admin_create_user_still_scoped_to_own_tenant` (row 11).
- [x] 3.12 Add regression test `test_tenant_admin_create_user_ignores_foreign_tenant_field` (row 12).
- [x] 3.13 Add test `test_quota_enforcement_matches_across_admin_and_tenant_endpoints` (row 13).
- [x] 3.14 Add test `test_password_validation_matches_across_admin_and_tenant_endpoints` (row 14).
- [x] 3.15 Add test `test_tenant_active_validation_matches_across_admin_and_tenant_endpoints` (row 15) comparing 403 behavior for an inactive tenant across both endpoints.
- [x] 3.16 Add test `test_audit_event_recorded_for_system_admin_user_creation` (row 16), querying `public.audit_events` after a successful admin-endpoint creation and asserting `actor`, `role: "system_admin"`, `action: "user.create"`, `target`, `tenant_id`.
- [x] 3.17 Add test `test_audit_event_recorded_for_tenant_admin_user_creation` (row 17), same assertions with `role: "tenant_admin"` after a `/api/v1/users` creation.
- [x] 3.18 Add test confirming the same email succeeds when created in two different tenants via the admin endpoint (supports Hallucination Risk 10).

## 4. Frontend: Shared Create User Form

- [x] 4.1 Extract the create-user form (fields, state, submit handler shape, and existing "Create User" button / "New User" heading wording) from `src/portal/src/app/(auth)/users/page.tsx` into `src/portal/src/components/users/CreateUserForm.tsx`, accepting props `{ roles: string[], onSubmit: (payload) => Promise<...>, tenantLabel?: string }`. Do not introduce new wording ("Add User") anywhere in the extracted component.
- [x] 4.2 Update `src/portal/src/app/(auth)/users/page.tsx` to use `CreateUserForm` with `roles={ROLES}` and no `tenantLabel`, preserving all existing behavior and wording (email/password/role fields, 409/429/403 error handling, list update on success).
- [x] 4.3 Update/port existing Tenant Admin `users` page tests to confirm no behavioral or wording regression after extraction.

## 5. Frontend: Admin Console Create User UI

- [x] 5.1 Add a "Create User" button and toggled `CreateUserForm` (with `tenantLabel={`${tenant.name} (${tenant.slug})`}`) to `src/portal/src/app/(auth)/admin/tenants/[id]/page.tsx`, submitting to `POST /api/v1/admin/tenants/{id}/users`. Use "Create User" as the button label, matching the Tenant Admin page — not "Add User".
- [x] 5.2 On successful creation, prepend the new user to the page's `users` state (no full reload) and update the displayed `user_count`/quota indicator.
- [x] 5.3 Surface 429 (quota), 409 (duplicate email), and 403 (deactivated tenant) errors inline in the form, matching the existing Tenant Admin page's error-handling pattern.

## 6. Frontend Tests

- [x] 6.1 Add test `test_admin_can_create_user_from_tenant_detail_page` (row 18) confirming the tenant label is shown, the request targets `/api/v1/admin/tenants/{id}/users`, and the new user appears in the list without a reload.
- [x] 6.2 Add test `test_admin_create_user_form_surfaces_quota_error` (row 19) confirming a quota-exceeded response renders an inline error and does not add a row.
- [x] 6.3 Add test `test_admin_create_user_form_surfaces_deactivated_tenant_error` (row 20) confirming a 403 tenant-deactivated response renders an inline error and does not add a row.
- [x] 6.4 Add/update test `test_tenant_detail_page_shows_create_user_button` (row 21) confirming Edit Quotas, Deactivate Tenant, and Create User buttons are all present with correct labels.
- [x] 6.5 Add test `test_create_user_updates_quota_usage_indicator` (row 22) confirming the users quota count increments after a successful creation.

## 7. Verification & Evidence

- [x] 7.1 Run all acceptance-criteria tests for every scenario in verification.md § Spec Alignment and confirm all pass.
- [x] 7.2 Collect functional evidence (screenshot / test output / log) for each scenario — record one entry per row in verification.md § Evidence Log.
- [x] 7.3 Confirm every Hallucination Risk mitigation step in verification.md § Hallucination Risk Register.
- [x] 7.4 Confirm all ADR compliance steps in verification.md § Pattern & ADR Compliance.
- [ ] 7.5 Complete Audit Record sign-off in verification.md § Audit Record (human reviewer required).
- [x] 7.6 Run `openspec validate sysadmin-user-onboarding --type change --strict` and confirm it exits clean before archive.
