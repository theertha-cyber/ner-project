# Verification Plan

**Change:** tenant-admin-user-mgmt
**Generated:** 2026-06-08
**Status:** 🟡 Functional evidence collected; awaiting human Audit Record sign-off before archive.

---

## 1. Spec Alignment

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | tenant-user-mgmt | Tenant-Admin User CRUD Endpoints | Tenant Admin creates a user in their own tenant | Given an authenticated Tenant Admin for "acme-corp", when they POST to `/api/v1/tenants/acme-corp/users` with valid payload, then response is 201 with user object containing email, role, status | `test_tenant_admin_creates_user_own_tenant` (Task 4.2) | ✅ |
| 2 | tenant-user-mgmt | Tenant-Admin User CRUD Endpoints | Tenant Admin lists users in their own tenant | Given an authenticated Tenant Admin with existing users, when they GET `/api/v1/tenants/acme-corp/users`, then response is 200 with paginated user list | `test_tenant_admin_lists_users` (Task 4.3) | ✅ |
| 3 | tenant-user-mgmt | Tenant-Admin User CRUD Endpoints | Tenant Admin gets a specific user in their tenant | Given an authenticated Tenant Admin and existing user "user-123", when they GET `/api/v1/tenants/acme-corp/users/user-123`, then response is 200 with user details | `test_tenant_admin_gets_user` (Task 4.4) | ✅ |
| 4 | tenant-user-mgmt | Tenant-Admin User CRUD Endpoints | Tenant Admin updates a user in their tenant | Given an authenticated Tenant Admin and existing user "user-123", when they PUT `/api/v1/tenants/acme-corp/users/user-123` with `{"role": "business_user"}`, then response is 200 with updated role | `test_tenant_admin_updates_user` (Task 4.5) | ✅ |
| 5 | tenant-user-mgmt | Tenant-Admin User CRUD Endpoints | Tenant Admin deactivates a user in their tenant | Given an authenticated Tenant Admin and active user "user-123", when they DELETE `/api/v1/tenants/acme-corp/users/user-123`, then response is 200 and user status is "inactive" | `test_tenant_admin_deactivates_user` (Task 4.6) | ✅ |
| 6 | tenant-user-mgmt | Tenant-Admin User CRUD Endpoints | Tenant Admin cannot create users in another tenant (cross-tenant blocked) | Given an authenticated Tenant Admin for "acme-corp", when they POST to `/api/v1/tenants/other-corp/users` with valid payload, then response is 403 with tenant scope error | `test_scenario_10_cross_tenant_blocked` (Task 4.1) | ✅ |
| 7 | tenant-user-mgmt | Tenant-Admin User CRUD Endpoints | Non-tenant-admin role cannot create users (role enforcement) | Given an authenticated `annotator` user for "acme-corp", when they POST to `/api/v1/tenants/acme-corp/users` with valid payload, then response is 403 with admin-required error | `test_non_admin_role_cannot_create_users` (Task 4.7) | ✅ |
| 8 | user-auth (modified) | Tenant-Scoped User Management | Tenant Admin creates a user in their own tenant | Same as #1 — route path corrected from `/api/v1/admin/...` to `/api/v1/tenants/...` | Same as #1 | ✅ |
| 9 | user-auth (modified) | Tenant-Scoped User Management | Tenant Admin attempts cross-tenant user creation | Same as #6 — route path corrected from `/api/v1/admin/...` to `/api/v1/tenants/...` | Same as #6 | ✅ |

> **Rule:** Every `#### Scenario:` block in every `specs/**/*.md` file for this change
> MUST appear as a row in this table. A missing scenario is a P1 gap that blocks archive.

---

## 2. Hallucination Risk Register

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|-------------------|----------------------|
| 1 | New dependency `require_tenant_admin` | AI may create an overly permissive dependency (admitting any role instead of only `tenant_admin`) or copy `require_tenant_role` verbatim | Verify `require_tenant_admin` checks `role == "tenant_admin"` exactly — no fallthrough to other roles |
| 2 | Route prefix alignment | AI may use `{tenant_id}` path param (matching admin routes) instead of `{slug}` (matching tenant-scoped pattern) | Verify `users.py` uses `prefix="/api/v1/tenants/{slug}/users"` — same pattern as `entity_types.py` |
| 3 | Cross-tenant enforcement | AI may rely only on `require_tenant_admin` and omit `resolve_tenant`, allowing a tenant_admin from tenant A to manage tenant B's users | Verify every route in `users.py` has both `Depends(resolve_tenant)` and `Depends(require_tenant_admin)` |
| 4 | Admin user routes removed | AI may leave dead imports (UserService, get_request_tenant_id) in `admin.py` or forget to remove all 5 user endpoints | Verify `admin.py` has no `UserService` import and no `/users` endpoint routes |
| 5 | Admin routes weakened | AI may accidentally change `require_system_admin` to `require_tenant_admin` on the remaining admin routes (tenant CRUD) | Verify `admin.py` tenant routes still use `require_system_admin`, only user routes were removed |

---

## 3. Pattern & ADR Compliance

| ADR | Decision Summary | Constraint on This Change | Verification Step |
|-----|-----------------|--------------------------|-------------------|
| ADR-001 | Tenant Data Isolation via separate schemas; API Gateway validates JWT `tenant_id` against URL | New tenant-scoped user routes must use `resolve_tenant` to enforce tenant match (same pattern as `entity_types.py`) | Verify every route in `users.py` includes `Depends(resolve_tenant)` |

---

## 4. Evidence Requirements

### Functional Evidence

- [x] #1: Test output showing tenant_admin creates user in own tenant via `/api/v1/tenants/{slug}/users` → 201
- [x] #2: Test output showing tenant_admin lists users in own tenant → 200 with paginated list
- [x] #3: Test output showing tenant_admin gets specific user → 200 with user details
- [x] #4: Test output showing tenant_admin updates user role → 200 with updated role
- [x] #5: Test output showing tenant_admin deactivates user → 200 with status "inactive"
- [x] #6: Test output showing tenant_admin cross-tenant creation → 403 with tenant scope error
- [x] #7: Test output showing non-admin role creation attempt → 403 with admin-required error
- [x] #8-9: Covered by same test outputs as #1 and #6 above (corrected route paths verified)

### Structural Evidence

- [x] Code review completed — `users.py` follows `entity_types.py` pattern with `resolve_tenant` + `require_tenant_admin`
- [x] ADR-001 compliance confirmed — all tenant-scoped routes in `users.py` use `Depends(resolve_tenant)`
- [x] No undocumented architectural patterns introduced
- [x] No AI-invented requirements present in generated code (cross-checked against spec files)
- [x] `admin.py` user CRUD endpoints fully removed — no `UserService` import, no `/users` route definitions

### Edge Case Evidence

- [x] Risk 1 mitigation confirmed — `require_tenant_admin` checks `role == "tenant_admin"` exactly (source: `dependencies.py:31-35`)
- [x] Risk 2 mitigation confirmed — route prefix uses `{slug}` via `resolve_tenant` middleware, not `{tenant_id}` in URL param
- [x] Risk 3 mitigation confirmed — every route in `users.py` has both `Depends(resolve_tenant)` and `Depends(require_tenant_admin)`
- [x] Risk 4 mitigation confirmed — `admin.py` has no imports of `UserService` or `get_request_tenant_id`, no user route handlers
- [x] Risk 5 mitigation confirmed — `admin.py` tenant CRUD routes (create, list, get, update, deactivate) all still use `require_system_admin`

---

## 5. Evidence Log

| # | Evidence Type | Description / Link | Scenario(s) Covered | Collected By | Date |
|---|--------------|-------------------|---------------------|--------------|------|
| 1 | Functional | `test_tenant_admin_creates_user_own_tenant` — PASSED (201 with user object) | #1, #8 | agent | 2026-06-08 |
| 2 | Functional | `test_tenant_admin_lists_users` — PASSED (200 with user list) | #2 | agent | 2026-06-08 |
| 3 | Functional | `test_tenant_admin_gets_user` — PASSED (200 with user email) | #3 | agent | 2026-06-08 |
| 4 | Functional | `test_tenant_admin_updates_user` — PASSED (200 with role `business_user`) | #4 | agent | 2026-06-08 |
| 5 | Functional | `test_tenant_admin_deactivates_user` — PASSED (200 with status `inactive`) | #5 | agent | 2026-06-08 |
| 6 | Functional | `test_scenario_10_cross_tenant_blocked` — PASSED (403 cross-tenant) | #6, #9 | agent | 2026-06-08 |
| 7 | Functional | `test_non_admin_role_cannot_create_users` — PASSED (403 non-admin) | #7 | agent | 2026-06-08 |
| 8 | Structural | `dependencies.py` — `require_tenant_admin` checks `role == "tenant_admin"` exactly | All | agent | 2026-06-08 |
| 9 | Structural | `users.py` — every route has `Depends(resolve_tenant)` + `Depends(require_tenant_admin)` | All | agent | 2026-06-08 |
| 10 | Structural | `admin.py` — 5 user CRUD endpoints removed, remaining 5 tenant routes still use `require_system_admin` | N/A | agent | 2026-06-08 |
| 11 | Structural | `admin.py` — no `UserService` import, no `/users` routes, `get_request_tenant_id` removed | N/A | agent | 2026-06-08 |
| 12 | Structural | All test fixtures updated — `seeded_tenant_and_user`, `tenant_with_token`, quota tests use tenant_admin tokens directly, no admin route dependency | All | agent | 2026-06-08 |
| 13 | Functional | Full test suite — 27/27 tests pass (`test_user_auth.py:14`, `test_entity_config.py:6`, `test_tenant_provisioning.py:5`, `test_env_config.py:2`) | All | agent | 2026-06-08 |
| 14 | Edge Case | `openspec validate tenant-admin-user-mgmt --type change --strict` — clean exit | All | agent | 2026-06-08 |

---

## 6. Audit Record

> ⚠️ **GATE: This section must be completed and signed by a human reviewer before
> `/opsx:archive` is run.** An unsigned or incomplete Audit Record is a hard block on archive.

**Change slug:** tenant-admin-user-mgmt
**Proposal:** `openspec/changes/tenant-admin-user-mgmt/proposal.md`
**Spec files reviewed:**
- specs/tenant-user-mgmt/spec.md
- specs/user-auth/spec.md

### Reviewer Sign-Off

| Check | Status |
|-------|--------|
| Design reviewed against proposal | - [ ] |
| All ADRs in Section 3 verified compliant | - [ ] |
| Spec Alignment table complete (no missing scenarios) | - [ ] |
| Evidence Log populated with real evidence | - [ ] |
| All functional evidence items in Section 4 checked | - [ ] |
| All structural evidence items in Section 4 checked | - [ ] |
| All edge case evidence items in Section 4 checked | - [ ] |

### AI Output Review

| Check | Status |
|-------|--------|
| All generated artifacts reviewed for spec alignment | - [ ] |
| No hallucinated requirements introduced | - [ ] |
| No undocumented patterns used | - [ ] |
| No AI-invented fields, endpoints, or behaviours present | - [ ] |
| Every THEN clause in specs has a corresponding evidence entry | - [ ] |
| Hallucination risk register reviewed and all mitigations confirmed | - [ ] |

**Archive approved by:** ___________________________

**Date:** ___________

**Notes:**
<!-- Any observations, caveats, or follow-up items for future changes. -->
