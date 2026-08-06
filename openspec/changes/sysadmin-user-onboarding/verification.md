# Verification Plan

**Change:** sysadmin-user-onboarding
**Generated:** 2026-08-06
**Status:** 🟡 Evidence collected, all scenarios passing — Audit Record sign-off (§6) still required from a human reviewer before archive.

---

## 1. Spec Alignment

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | sysadmin-user-onboarding | System Admin Cross-Tenant User Creation Endpoint | System Admin creates a Business User in a specific tenant | Given an authenticated System Admin and active tenant `tid-123`, when they POST `/api/v1/admin/tenants/tid-123/users` with a valid `business_user` payload, then response is 201 with `user.role: "business_user"`, `user.status: "active"`, and the user belongs to `tid-123` | backend test: `test_admin_creates_business_user_in_target_tenant` | - [x] |
| 2 | sysadmin-user-onboarding | System Admin Cross-Tenant User Creation Endpoint | System Admin creates a Tenant Admin in a specific tenant | Given an authenticated System Admin and active tenant `tid-123`, when they POST a valid `tenant_admin` payload, then response is 201 with `user.role: "tenant_admin"` | backend test: `test_admin_creates_tenant_admin_in_target_tenant` | - [x] |
| 3 | sysadmin-user-onboarding | System Admin Cross-Tenant User Creation Endpoint | System Admin creates an Annotator in a specific tenant | Given an authenticated System Admin and active tenant `tid-123`, when they POST a valid `annotator` payload, then response is 201 with `user.role: "annotator"` | backend test: `test_admin_creates_annotator_in_target_tenant` | - [x] |
| 4 | sysadmin-user-onboarding | System Admin Cross-Tenant User Creation Endpoint | System Admin targets a nonexistent tenant | Given no tenant exists with id `tid-ghost`, when a System Admin POSTs to `/api/v1/admin/tenants/tid-ghost/users`, then response is 404 with a tenant-not-found message | backend test: `test_admin_create_user_nonexistent_tenant_returns_404` | - [x] |
| 5 | sysadmin-user-onboarding | System Admin Cross-Tenant User Creation Endpoint | System Admin request exceeds the target tenant's user quota | Given a tenant with `max_users: 5` and 5 active users, when a System Admin POSTs a new user, then response is 429 with a quota-exceeded message | backend test: `test_admin_create_user_quota_exceeded_returns_429` | - [x] |
| 6 | sysadmin-user-onboarding | System Admin Cross-Tenant User Creation Endpoint | System Admin request duplicates an email already used in that tenant | Given a tenant with existing user "user@acme.com", when a System Admin POSTs a new user with the same email in that tenant, then response is 409 with an email-taken message | backend test: `test_admin_create_user_duplicate_email_in_tenant_returns_409` | - [x] |
| 7 | sysadmin-user-onboarding | System Admin Cross-Tenant User Creation Endpoint | Non-system-admin role cannot access the cross-tenant creation endpoint | Given an authenticated `tenant_admin`, when they POST to `/api/v1/admin/tenants/{any_tenant_id}/users`, then response is 403 with a system-admin-required message | backend test: `test_admin_create_user_rejects_non_system_admin_403` | - [x] |
| 8 | sysadmin-user-onboarding | System Admin Cross-Tenant User Creation Endpoint | Unauthenticated request is rejected | Given no Bearer token, when POSTing to `/api/v1/admin/tenants/{tenant_id}/users`, then response is 401 | backend test: `test_admin_create_user_requires_auth_401` | - [x] |
| 9 | sysadmin-user-onboarding | System Admin Cross-Tenant User Creation Endpoint | System Admin targets a tenant that is inactive | Given tenant `tid-123` with `status: "inactive"`, when a System Admin POSTs a valid user payload to `/api/v1/admin/tenants/tid-123/users`, then response is 403 with a tenant-deactivated message and no user is created | backend test: `test_admin_create_user_inactive_tenant_returns_403` | - [x] |
| 10 | sysadmin-user-onboarding | System Admin Cross-Tenant User Creation Endpoint | Target tenant is deactivated between form load and submission | Given a System Admin loaded the create-user form for active tenant `tid-123`, when the tenant is deactivated before the POST reaches the server, then response is 403 with a tenant-deactivated message and no user is created | backend test: `test_admin_create_user_tenant_deactivated_after_form_load_returns_403` | - [x] |
| 11 | sysadmin-user-onboarding | Tenant Admin Onboarding Flow Remains Unchanged | Tenant Admin still creates users only in their own tenant | Given a Tenant Admin JWT for tenant "acme-corp", when they POST `/api/v1/users` with a valid payload, then response is 201 and the created user belongs to the JWT's tenant | backend test: `test_tenant_admin_create_user_still_scoped_to_own_tenant` | - [x] |
| 12 | sysadmin-user-onboarding | Tenant Admin Onboarding Flow Remains Unchanged | Tenant Admin cannot target another tenant via this endpoint | Given a Tenant Admin JWT for tenant "acme-corp", when they POST `/api/v1/users` with a payload containing an unrelated tenant identifier, then that identifier is ignored and the created user belongs to the JWT-resolved tenant | backend test: `test_tenant_admin_create_user_ignores_foreign_tenant_field` | - [x] |
| 13 | sysadmin-user-onboarding | Shared User Creation Business Logic | Quota enforcement is identical regardless of creating role | Given a tenant with `max_users: 1` and 1 active user, when a System Admin POSTs a new user via the admin endpoint, then response is 429, matching the Tenant Admin path's quota-exceeded response under the same condition | backend test: `test_quota_enforcement_matches_across_admin_and_tenant_endpoints` | - [x] |
| 14 | sysadmin-user-onboarding | Shared User Creation Business Logic | Password validation is identical regardless of creating role | Given a password failing the platform policy, when a System Admin submits it via the admin endpoint, then the same validation error is returned as the Tenant Admin path would return for the same password | backend test: `test_password_validation_matches_across_admin_and_tenant_endpoints` | - [x] |
| 15 | sysadmin-user-onboarding | Shared User Creation Business Logic | Tenant-active validation is identical regardless of creating role | Given an inactive tenant, when a System Admin POSTs a new user via the admin endpoint, then response is 403, matching the status/error code a Tenant Admin's request would receive if their own tenant became inactive | backend test: `test_tenant_active_validation_matches_across_admin_and_tenant_endpoints` | - [x] |
| 16 | sysadmin-user-onboarding | User Creation Is Audited | Audit event recorded when System Admin creates a user | Given System Admin "platform-admin@example.com", when they POST a valid user payload to `/api/v1/admin/tenants/tid-123/users` and creation succeeds, then an audit event is recorded with `actor: "platform-admin@example.com"`, `role: "system_admin"`, `action: "user.create"`, `target` = new user's email, `tenant_id: "tid-123"` | backend test: `test_audit_event_recorded_for_system_admin_user_creation` | - [x] |
| 17 | sysadmin-user-onboarding | User Creation Is Audited | Audit event recorded when Tenant Admin creates a user | Given Tenant Admin "admin@acme.com" whose JWT `tenant_id` is `tid-123`, when they POST a valid user payload to `/api/v1/users` and creation succeeds, then an audit event is recorded with `actor: "admin@acme.com"`, `role: "tenant_admin"`, `action: "user.create"`, `target` = new user's email, `tenant_id: "tid-123"` | backend test: `test_audit_event_recorded_for_tenant_admin_user_creation` | - [x] |
| 18 | sysadmin-user-onboarding | Admin Console Cross-Tenant User Creation UI | System Admin creates a user from the tenant detail page | Given a System Admin viewing `/admin/tenants/tid-123` for tenant "Acme Corp" (`acme-corp`), when they click "Create User", fill valid fields, and submit, then the form shows "Acme Corp (acme-corp)" as target, the request goes to `/api/v1/admin/tenants/tid-123/users`, and the new user appears in the list without a full reload | frontend test: `test_admin_can_create_user_from_tenant_detail_page` | - [x] |
| 19 | sysadmin-user-onboarding | Admin Console Cross-Tenant User Creation UI | Create User form surfaces quota and duplicate-email errors | Given a System Admin viewing a tenant at its user quota limit, when they submit the Create User form, then an error indicating quota exceeded is displayed and the user list does not gain a new entry | frontend test: `test_admin_create_user_form_surfaces_quota_error` | - [x] |
| 20 | sysadmin-user-onboarding | Admin Console Cross-Tenant User Creation UI | Create User form surfaces a deactivated-tenant error | Given a System Admin viewing a tenant whose status becomes inactive after page load, when they submit the Create User form, then an error indicating the tenant is deactivated is displayed and the user list does not gain a new entry | frontend test: `test_admin_create_user_form_surfaces_deactivated_tenant_error` | - [x] |
| 21 | admin-console (delta) | Tenant Detail View | System Admin views tenant details | Given a System Admin and tenant "acme-corp" (`tid-123`), when they navigate to `/admin/tenants/tid-123`, then the page shows name/slug/status/created_at, quota usage (users/documents/storage), the tenant's user list, and Edit Quotas, Deactivate Tenant, and Create User buttons | frontend test: `test_tenant_detail_page_shows_create_user_button` | - [x] |
| 22 | admin-console (delta) | Tenant Detail View | System Admin creates a user in the tenant from this view | Given a System Admin on `/admin/tenants/tid-123`, when they click "Create User", fill fields, and submit, then the request is sent to `POST /api/v1/admin/tenants/tid-123/users`, the new user appears in the list, and the users quota usage indicator updates | frontend test: `test_create_user_updates_quota_usage_indicator` | - [x] |

> **Rule:** Every `#### Scenario:` block in every `specs/**/*.md` file for this change MUST appear as a row in this table. A missing scenario is a P1 gap that blocks archive.

---

## 2. Hallucination Risk Register

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|-------------------|----------------------|
| 1 | Two creation endpoints sharing one service (Decision 2 in design.md) | AI may implement the admin route with its own inline SQL/validation instead of calling `UserService.create_user`, causing quota/validation drift between the two paths | Read the admin route handler diff — confirm it constructs `UserService(db)` and calls `.create_user(tenant_id, payload, ...)` with no parallel validation/quota logic added in the route itself |
| 2 | Tenant resolution source (Decision 1) | AI may accidentally wire the new route through `resolve_tenant_from_jwt` (which rejects `tenant_id == "system"`) instead of taking `tenant_id` from the path parameter, breaking the endpoint for actual System Admin JWTs | Trace the new route's dependency list — confirm `tenant_id` comes from the FastAPI path parameter, not from any `resolve_tenant_from_jwt`/`resolve_tenant` dependency |
| 3 | Existing Tenant Admin flow must stay unchanged (proposal.md, design.md Non-Goals) | AI may "helpfully" refactor `POST /api/v1/users` or `require_tenant_admin` while extracting shared logic, altering its status codes or auth behavior | Diff `src/gateway/api/v1/users.py` and `src/gateway/dependencies.py` against the pre-change version — confirm zero behavioral changes to the existing route/dependencies |
| 4 | No new/combined authorization dependency (Decision 2, explicit reviewer preference) | AI may introduce a combined `require_tenant_or_system_admin`-style dependency, or modify `require_tenant_admin`/`require_system_admin`, when the reviewer explicitly asked to keep the existing two dependencies unchanged | Diff `src/gateway/dependencies.py` — confirm `require_tenant_admin` and `require_system_admin` are byte-for-byte unchanged and no new combined dependency function was added |
| 5 | Tenant-active validation placement (Decision 3) | AI may add the inactive-tenant check only in the new admin route (duplicated logic) instead of inside `UserService.create_user`, or may skip it entirely, leaving the admin path able to create users in a deactivated tenant | Confirm the status check lives inside `UserService.create_user` (not duplicated in `admin.py`), and that scenarios 9 and 10 (inactive tenant, deactivated-after-form-load) both return 403 via that single code path |
| 6 | Audit logging placement and correctness (Decision 4) | AI may audit only the System Admin path (asymmetric coverage), record the wrong actor role for the Tenant Admin path, or invent extra audit fields not in the spec | Confirm `UserService.create_user` calls `AuditService.record` unconditionally on success for both callers; confirm scenarios 16 and 17 produce audit rows with exactly `actor`, `role`, `action: "user.create"`, `target`, `tenant_id` — no extra fields |
| 7 | Tenant existence validation before creation (Decision 1/3 combined) | AI may skip validating the target tenant exists before calling `UserService.create_user`, causing a confusing quota-lookup `NotFoundError` instead of a clean 404, or may conflate the 404 (nonexistent) and 403 (inactive) cases into one status code | Confirm the new route calls `TenantService.get_tenant(tenant_id)` (404 path) before `UserService.create_user` (403 inactive path), and that scenario 4 returns 404 while scenario 9 returns 403 — distinct codes, not merged |
| 8 | Shared frontend `CreateUserForm` extraction and terminology reuse (Decision 5) | AI may change the Tenant Admin page's existing form behavior (field order, validation, error messages) while extracting it, or may introduce different wording ("Add User") on the admin console side instead of reusing "Create User"/"New User" | Run/inspect the Tenant Admin `users/page.tsx` tests before and after — confirm no assertions changed; grep the admin console UI source for the literal string "Create User" (not "Add User") on the button and confirm the form heading matches |
| 9 | Role list duplication across two roles/entry points | AI may hardcode a different role list (e.g., omit `tenant_admin`) in the admin console's Create User form versus the Tenant Admin form's `ROLES` constant | Check the Create User form's role options against `["annotator", "business_user", "tenant_admin"]` — same three roles as `ROLES` in `users/page.tsx` |
| 10 | Per-tenant vs cross-tenant email uniqueness (proposal.md Open Questions) | AI may add unintended cross-tenant email-uniqueness checking (over-engineering) or, conversely, accidentally break the existing per-tenant `uq_email_per_tenant` uniqueness while wiring the new endpoint | Confirm no new uniqueness query/constraint was added; confirm scenario 6 (duplicate email in same tenant → 409) passes and creating the same email in a *different* tenant via the admin endpoint still succeeds |

---

## 3. Pattern & ADR Compliance

| ADR | Decision Summary | Constraint on This Change | Verification Step |
|-----|-------------------|----------------------------|--------------------|
| ADR-009-system-admin-sets-training-hyperparameters | System Admin-specific actions get their own dedicated endpoint under `/api/v1/admin/*` rather than widening a tenant-facing endpoint. | The new user-creation capability must be implemented as a distinct `POST /api/v1/admin/tenants/{tenant_id}/users` route, not as a role/parameter addition to `POST /api/v1/users`. | Confirm `POST /api/v1/admin/tenants/{tenant_id}/users` exists as its own route in `src/gateway/api/v1/admin.py` and that `src/gateway/api/v1/users.py`'s `POST /api/v1/users` handler signature is unmodified. |

---

## 4. Evidence Requirements

### Functional Evidence

- [x] Scenario 1 (Business User creation): test output showing a passing test that POSTs to `/api/v1/admin/tenants/{tenant_id}/users` with role `business_user` and asserts 201 + correct body
- [x] Scenario 2 (Tenant Admin creation): test output for `role: tenant_admin` returning 201
- [x] Scenario 3 (Annotator creation): test output for `role: annotator` returning 201
- [x] Scenario 4 (nonexistent tenant): test output asserting 404 for an unknown `tenant_id`
- [x] Scenario 5 (quota exceeded): test output asserting 429 when the target tenant is at `max_users`
- [x] Scenario 6 (duplicate email in tenant): test output asserting 409 for a repeated email within the same tenant
- [x] Scenario 7 (role enforcement): test output asserting 403 for a `tenant_admin` caller
- [x] Scenario 8 (unauthenticated): test output asserting 401 with no Bearer token
- [x] Scenario 9 (inactive tenant): test output asserting 403 with tenant-deactivated message
- [x] Scenario 10 (tenant deactivated after form load): test output asserting 403 when tenant status flips before the request is processed
- [x] Scenario 11 (Tenant Admin unchanged, own tenant): test output confirming `/api/v1/users` still creates within the JWT tenant
- [x] Scenario 12 (Tenant Admin cannot target another tenant): test output confirming payload tenant identifiers are ignored
- [x] Scenario 13 (quota parity): test output/comparison showing identical 429 behavior across both endpoints
- [x] Scenario 14 (password validation parity): test output/comparison showing identical validation error across both endpoints
- [x] Scenario 15 (tenant-active parity): test output/comparison showing identical 403 behavior across both endpoints for an inactive tenant
- [x] Scenario 16 (audit event, System Admin): test output/query result showing an audit row with `role: "system_admin"` after admin-endpoint creation
- [x] Scenario 17 (audit event, Tenant Admin): test output/query result showing an audit row with `role: "tenant_admin"` after tenant-endpoint creation
- [x] Scenario 18 (Create User UI flow): frontend test output or screenshot sequence showing the Create User form, tenant label display, and list update
- [x] Scenario 19 (quota error surfacing): frontend test output showing quota-exceeded error rendered in the form
- [x] Scenario 20 (deactivated-tenant error surfacing): frontend test output showing tenant-deactivated error rendered in the form
- [x] Scenario 21 (tenant detail view unchanged + Create User button): frontend test output/screenshot showing all three buttons present with correct labels
- [x] Scenario 22 (Create User updates quota indicator): frontend test output showing the quota usage number increments after creation

### Structural Evidence

- [x] Code review completed — implementation matches design.md decisions (no undocumented deviations)
- [x] All ADR compliance steps in Section 3 confirmed ✓
- [x] No undocumented architectural patterns introduced
- [x] No AI-invented requirements present in generated code (cross-checked against spec files)

### Edge Case Evidence

- [x] Risk 1 mitigation confirmed — admin route verified to call `UserService.create_user` with no parallel logic
- [x] Risk 2 mitigation confirmed — `tenant_id` verified sourced from path parameter, not `resolve_tenant_from_jwt`
- [x] Risk 3 mitigation confirmed — existing Tenant Admin route/dependency diff shows zero behavioral change
- [x] Risk 4 mitigation confirmed — `require_tenant_admin`/`require_system_admin` unchanged, no new combined dependency introduced
- [x] Risk 5 mitigation confirmed — tenant-active check lives in `UserService.create_user`, not duplicated per route
- [x] Risk 6 mitigation confirmed — audit logging symmetric across both paths, fields match spec exactly
- [x] Risk 7 mitigation confirmed — 404 (nonexistent) and 403 (inactive) are distinct, correctly ordered checks
- [x] Risk 8 mitigation confirmed — Tenant Admin page test suite unchanged/passing after form extraction; admin console uses "Create User" wording, not "Add User"
- [x] Risk 9 mitigation confirmed — Create User form role options match `["annotator", "business_user", "tenant_admin"]`
- [x] Risk 10 mitigation confirmed — per-tenant-only uniqueness preserved; same email succeeds across different tenants

---

## 5. Evidence Log

| # | Evidence Type | Description / Link | Scenario(s) Covered | Collected By | Date |
|---|--------------|-------------------|---------------------|--------------|------|
| 1 | Functional | `pytest tests/test_sysadmin_user_onboarding.py -v` — 18 passed, 0 failed | Scenarios 1-17 | Claude (opsx:apply) | 2026-08-06 |
| 2 | Functional | `vitest run` on `src/app/(auth)/users/page.test.tsx` (4 tests) and `src/app/(auth)/admin/tenants/[id]/page.test.tsx` (4 tests) — 8 passed, 0 failed | Scenarios 18-22 (and Tenant Admin UI regression coverage) | Claude (opsx:apply) | 2026-08-06 |
| 3 | Structural | Full backend suite (`tests/test_audit_log.py`, `tests/test_tenant_provisioning.py`) and full frontend suite (`vitest run`, 564 tests) run after the change; failures present both before and after the change via `git stash` comparison (dashboard/auth/dark-mode/annotation tests, pre-existing and unrelated) — no new failures introduced by this change's diff | All (regression check) | Claude (opsx:apply) | 2026-08-06 |

---

## 6. Audit Record

> ⚠️ **GATE: This section must be completed and signed by a human reviewer before `/opsx:archive` is run.** An unsigned or incomplete Audit Record is a hard block on archive.

**Change slug:** sysadmin-user-onboarding
**Proposal:** `openspec/changes/sysadmin-user-onboarding/proposal.md`
**Spec files reviewed:**
- specs/sysadmin-user-onboarding/spec.md
- specs/admin-console/spec.md

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
