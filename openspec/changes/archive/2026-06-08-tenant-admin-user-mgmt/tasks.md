## 1. Dependencies Layer

- [x] 1.1 Add `require_tenant_admin` to `src/gateway/dependencies.py` — checks `role == "tenant_admin"`, raises 403 otherwise

## 2. New Router Module

- [x] 2.1 Create `src/gateway/api/v1/users.py` with CRUD endpoints at prefix `/api/v1/tenants/{slug}/users`, gated by `Depends(resolve_tenant)` + `Depends(require_tenant_admin)` — mirrors `entity_types.py` structure
- [x] 2.2 Import and wire `users.router` in `src/gateway/main.py`

## 3. Spec & Documentation

- [x] 3.1 Update `openspec/changes/sm-01-identity-tenant-entity-config/specs/user-auth/spec.md` — replace route paths from `/api/v1/admin/tenants/...` to `/api/v1/tenants/...` in "Tenant-Scoped User Management" scenarios

## 4. Tests

- [x] 4.1 Rewrite `test_scenario_10_cross_tenant_blocked` — tenant_admin via `/api/v1/tenants/{slug}/users` cross-tenant → 403 (from `resolve_tenant` tenant mismatch)
- [x] 4.2 Add `test_tenant_admin_creates_user_own_tenant` — tenant_admin via `/api/v1/tenants/{slug}/users` own tenant → 201
- [x] 4.3 Add `test_tenant_admin_lists_users` — tenant_admin GET `/api/v1/tenants/{slug}/users` → 200
- [x] 4.4 Add `test_tenant_admin_gets_user` — tenant_admin GET `/api/v1/tenants/{slug}/users/{id}` → 200
- [x] 4.5 Add `test_tenant_admin_updates_user` — tenant_admin PUT `/api/v1/tenants/{slug}/users/{id}` → 200
- [x] 4.6 Add `test_tenant_admin_deactivates_user` — tenant_admin DELETE `/api/v1/tenants/{slug}/users/{id}` → 200
- [x] 4.7 Add `test_non_admin_role_cannot_create_users` — annotator POST `/api/v1/tenants/{slug}/users` → 403

## 5. Admin Route Cleanup (scope expansion)

- [x] 5.1 Remove 5 user CRUD endpoints from `src/gateway/api/v1/admin.py` — delete handlers, clean up `UserService` and `get_request_tenant_id` imports
- [x] 5.2 Update `tests/test_entity_config.py` fixture — create tenant_admin token directly instead of via admin route
- [x] 5.3 Update `tests/test_tenant_provisioning.py` — quota test uses tenant_admin token + tenant-scoped route
- [x] 5.4 Update `tests/test_user_auth.py` fixture + all test setups — seed users via tenant-scoped routes instead of admin routes
- [x] 5.5 Repurpose `test_scenario_9` — test tenant_admin via tenant-scoped route (was system_admin via admin route)
- [x] 5.6 Update `README.md` — replace Admin - Users section with Users section under tenant-scoped routes
- [x] 5.7 Update proposal, design, spec, verification.md to reflect admin route removal decision

## 6. Verification & Evidence

- [x] 6.1 Run all acceptance-criteria tests (Scenarios 1–9 in verification.md) and confirm all pass — 27/27 pass
- [x] 6.2 Collect functional evidence for each scenario — record one entry per row in verification.md § Evidence Log
- [x] 6.3 Confirm every Hallucination Risk mitigation step in verification.md § Hallucination Risk Register
- [x] 6.4 Confirm all ADR compliance steps in verification.md § Pattern & ADR Compliance
- [ ] 6.5 Complete Audit Record sign-off in verification.md § Audit Record (human reviewer required)
- [x] 6.6 Run `openspec validate tenant-admin-user-mgmt --type change --strict` — clean exit confirmed
