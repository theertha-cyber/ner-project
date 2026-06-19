# Verification Plan

**Change:** fix-users-tenant-resolution
**Generated:** 2026-06-18
**Status:** 🔴 Incomplete — Evidence Log and Audit Record must be filled by a human reviewer before archive.

---

## 1. Spec Alignment

Map every requirement and every scenario in this change to a testable acceptance criterion.
Each row drives one evidence entry in Section 5.

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | tenant-user-mgmt | Tenant-Admin User CRUD Endpoints | Tenant Admin creates a user in their own tenant | Given a tenant admin JWT (no URL slug), when POST /api/v1/users with valid email/password/role, then response is 201 with a `user` object containing email, role "annotator", status "active" | | - [ ] |
| 2 | tenant-user-mgmt | Tenant-Admin User CRUD Endpoints | Tenant Admin lists users in their own tenant | Given a tenant admin JWT, when GET /api/v1/users, then response is 200 with a list of users scoped to the token's tenant | | - [ ] |
| 3 | tenant-user-mgmt | Tenant-Admin User CRUD Endpoints | Tenant Admin gets a specific user in their tenant | Given a tenant admin JWT and an existing user-123 in that tenant, when GET /api/v1/users/user-123, then response is 200 with email, role, and status fields | | - [ ] |
| 4 | tenant-user-mgmt | Tenant-Admin User CRUD Endpoints | Tenant Admin updates a user in their tenant | Given a tenant admin JWT and user-123, when PUT /api/v1/users/user-123 with {"role": "business_user"}, then response is 200 with the updated role reflected | | - [ ] |
| 5 | tenant-user-mgmt | Tenant-Admin User CRUD Endpoints | Tenant Admin deactivates a user in their tenant | Given a tenant admin JWT and an active user-123, when DELETE /api/v1/users/user-123, then response is 200 and user status is "inactive" | | - [ ] |
| 6 | tenant-user-mgmt | Tenant-Admin User CRUD Endpoints | Non-tenant-admin role cannot access user endpoints | Given an annotator JWT, when POST /api/v1/users with a valid payload, then response is 403 with a message indicating tenant admin access is required | | - [ ] |
| 7 | tenant-user-mgmt | Tenant-Admin User CRUD Endpoints | Unauthenticated request is rejected | Given no Bearer token, when POST /api/v1/users, then response is 401 | | - [ ] |

> **Rule:** Every `#### Scenario:` block in every `specs/**/*.md` file for this change
> MUST appear as a row in this table. A missing scenario is a P1 gap that blocks archive.

---

## 2. Hallucination Risk Register

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|-------------------|----------------------|
| 1 | Partial dependency swap | AI may update some endpoints but not all five, leaving a mix of `resolve_tenant` and `resolve_tenant_from_jwt` in the same router | Grep `users.py` for `resolve_tenant` — only `resolve_tenant_from_jwt` should appear; no occurrences of `resolve_tenant,` (the non-JWT variant) |
| 2 | Router prefix change | AI may update the prefix string but leave a stale `{tenant_id}` path parameter in individual route decorators or function signatures | Inspect all `@router.` decorators in `users.py` — none should reference `{tenant_id}`; function signatures should not accept a `tenant_id` path param |
| 3 | Response shape drift | AI may accidentally alter response field names or status codes while refactoring the file | Compare the five endpoint responses against the old implementation — `user`, `users` keys and all status codes (201, 200) must be unchanged |
| 4 | Import not updated | AI may add `resolve_tenant_from_jwt` to the function call but forget to add it to the import line, causing a runtime `NameError` | Check the import line in `users.py` — `resolve_tenant_from_jwt` must be imported from `src.gateway.dependencies`; `resolve_tenant` import may be removed |
| 5 | Old URL still registered | AI may update `users.py` but leave a stale route registration in `main.py` that still maps the old prefix | Check `src/gateway/main.py` — the users router should be included once with no explicit `prefix` override that re-adds `{tenant_id}` |

---

## 3. Pattern & ADR Compliance

| ADR | Decision Summary | Constraint on This Change | Verification Step |
|-----|-----------------|--------------------------|-------------------|
| ADR-001: Tenant Data Isolation | JWT `tenant_id` is the authoritative tenant identity at the API gateway; all tenant-scoped operations must validate it | `resolve_tenant_from_jwt` must validate the JWT `tenant_id` claim against the database (tenant exists + active) before allowing access — bypassing this check is non-compliant | Trace the `resolve_tenant_from_jwt` code path in `src/gateway/dependencies.py` — confirm it queries `public.tenants WHERE id = :id` and raises on missing/inactive tenant |

---

## 4. Evidence Requirements

Evidence that **MUST** be collected and logged in Section 5 before this change is archived.
Do not archive while any item below remains unchecked.

### Functional Evidence

- [ ] Scenario 1 (create): Swagger UI or curl — POST /api/v1/users with Bearer token only returns 201 with user object
- [ ] Scenario 2 (list): GET /api/v1/users with Bearer token returns 200 with users array
- [ ] Scenario 3 (get): GET /api/v1/users/{user_id} returns 200 with correct user fields
- [ ] Scenario 4 (update): PUT /api/v1/users/{user_id} with role change returns 200 with updated role
- [ ] Scenario 5 (deactivate): DELETE /api/v1/users/{user_id} returns 200 and user status is "inactive"
- [ ] Scenario 6 (role enforcement): Request with annotator token returns 403
- [ ] Scenario 7 (unauthenticated): Request with no Bearer token returns 401

### Structural Evidence

- [ ] Code review completed — implementation matches design.md decisions (no undocumented deviations)
- [ ] All ADR compliance steps in Section 3 confirmed ✓
- [ ] No undocumented architectural patterns introduced
- [ ] No AI-invented requirements present in generated code (cross-checked against spec files)

### Edge Case Evidence

- [ ] Risk 1 confirmed: grep `users.py` for `resolve_tenant` shows only `resolve_tenant_from_jwt`, no bare `resolve_tenant`
- [ ] Risk 2 confirmed: no `{tenant_id}` path parameter present in any `@router.` decorator or function signature in `users.py`
- [ ] Risk 3 confirmed: response field names and status codes match original implementation
- [ ] Risk 4 confirmed: import line includes `resolve_tenant_from_jwt` and gateway starts without `NameError`
- [ ] Risk 5 confirmed: `main.py` includes users router without a stale prefix override

---

## 5. Evidence Log

| # | Evidence Type | Description / Link | Scenario(s) Covered | Collected By | Date |
|---|--------------|-------------------|---------------------|--------------|------|
| 1 | | | | | |
| 2 | | | | | |
| 3 | | | | | |

---

## 6. Audit Record

> ⚠️ **GATE: This section must be completed and signed by a human reviewer before
> `/opsx:archive` is run.** An unsigned or incomplete Audit Record is a hard block on archive.

**Change slug:** fix-users-tenant-resolution
**Proposal:** `openspec/changes/fix-users-tenant-resolution/proposal.md`
**Spec files reviewed:**
- specs/tenant-user-mgmt/spec.md

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
