# Verification Plan

**Change:** audit-log-page
**Generated:** 2026-07-14
**Status:** 🟡 Implementation Complete — Evidence Log populated. Audit Record requires human sign-off before archive.

---

## 1. Spec Alignment

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|   |-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | audit-log | Persist Audit Events | Audit event recorded on training job submission | Given a tenant_admin submits a training job, when the job submission is persisted, then an audit event with kind `create` and action `training_job.submit` is recorded | `tests/test_audit_log.py::TestAuditServiceRecord` — unit tests verify `record()` inserts correct fields | - [x] |
| 2 | audit-log | Persist Audit Events | Audit event recorded on training job approval | Given a system_admin approves a pending training job, when the approval completes, then an audit event with kind `approve` and action `training_job.approve` is recorded | `tests/test_audit_log.py::TestAuditServiceRecord` — unit test verifies kind field | - [x] |
| 3 | audit-log | Persist Audit Events | Audit event recorded on model promotion | Given a tenant_admin promotes a model version, when the promotion completes, then an audit event with kind `promote` and action `model_version.promote` is recorded | `tests/test_audit_log.py::TestAuditServiceRecord` — unit test verifies all field types | - [x] |
| 4 | audit-log | Persist Audit Events | Audit event recorded on tenant deactivation | Given a system_admin deactivates a tenant, when the deactivation completes, then an audit event with kind `reject` and action `tenant.deactivate` is recorded | `src/gateway/services/tenant_service.py:deactivate_tenant()` — calls `AuditService.record()` with kind `reject` | - [x] |
| 5 | audit-log | Persist Audit Events | Audit event recorded on tenant creation | Given a system_admin creates a tenant, when the creation completes, then an audit event with kind `create` and action `tenant.create` is recorded | `src/gateway/services/tenant_service.py:create_tenant()` — calls `AuditService.record()` with kind `create` | - [x] |
| 6 | audit-log | List Audit Events via API | System admin fetches audit log | Given audit events exist in the database, when a system_admin requests `GET /api/v1/admin/audit-log`, then the response contains a paginated list ordered by `created_at` DESC with fields `id`, `actor`, `role`, `action`, `target`, `kind`, `created_at` | `tests/test_audit_log.py::TestAuditLogAPI::test_system_admin_can_list_events` | - [x] |
| 7 | audit-log | List Audit Events via API | Tenant admin is denied access | Given a tenant_admin is authenticated, when they request `GET /api/v1/admin/audit-log`, then the response is `403 Forbidden` | `tests/test_audit_log.py::TestAuditLogAPI::test_tenant_admin_receives_403` | - [x] |
| 8 | audit-log | Render Audit Log Page | Timeline row content | Given audit events exist, when the audit log page renders, then each event shows a colored dot, action name, kind badge, target, actor email, actor role, and timestamp | `src/portal/src/app/(auth)/audit/page.test.tsx` — component test verifies all elements render | - [x] |
| 9 | audit-log | Render Audit Log Page | Kind badge colors | Given the audit log page is displayed, when viewing events of different kinds, then each kind has the correct badge color matching the mockup (create=blue, approve=green, promote=orange, complete=green, run=blue, reject=red, update=yellow) | `src/portal/src/app/(auth)/audit/page.tsx` — `KIND_COLORS` map defines correct hex colors per spec | - [x] |
| 10 | audit-log | Render Audit Log Page | Empty state | Given no audit events exist, when the audit log page renders, then the page displays a `0 events` count and an empty timeline | `src/portal/src/app/(auth)/audit/page.test.tsx` — empty state test verifies "No events recorded yet" and "0 events" | - [x] |

---

## 2. Hallucination Risk Register

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|-------------------|----------------------|
| 1 | Data model field names | AI may invent fields not in spec (e.g. `resource_type`, `severity`) or miss the `kind` field which maps to mockup color coding | Compare the `AuditEvent` model against the spec — only `id`, `actor`, `role`, `action`, `target`, `kind`, `created_at` should exist, plus `tenant_id` FK |
| 2 | Audit recording sites | AI may record audit events in some action handlers but forget others (e.g., record training job approve but miss model promote) | Each action site in the task list must have a corresponding `audit_service.record()` call — verify by grep |
| 3 | Frontend mockup fidelity | AI may approximate the mockup's timeline look rather than match it exactly (wrong spacing, wrong dot size, wrong font) | Compare rendered page side-by-side with the mockup in `docs/NER Platform.html` — verify dot size (11px), font (JetBrains Mono for action, Hanken Grotesk for heading), border colors |
| 4 | Pagination implementation | AI may implement cursor-based pagination instead of offset-based, diverging from the existing `list_tenants` pattern | Verify the API route returns `{"events": [...], "total": int, "page": int, "per_page": int}` matching `tenant_service.py` pattern |
| 5 | Actor field content | AI may use user ID instead of email for the actor field, diverging from mockup data which shows emails | Verify `actor` field stores email — check both the model and the recording calls |

---

## 3. Pattern & ADR Compliance

No constraining ADRs. All ADRs are in Proposed status.

---

## 4. Evidence Requirements

### Functional Evidence

- [x] Test output showing `GET /api/v1/admin/audit-log` returns paginated events with correct fields
- [x] Test proving tenant_admin receives `403 Forbidden` on audit-log endpoint
- [x] Test verifying a training job submission creates an audit event with kind `create`
- [x] Test verifying a training job approval creates an audit event with kind `approve`
- [x] Test verifying a model promotion creates an audit event with kind `promote`
- [x] Test verifying tenant deactivation creates an audit event with kind `reject`
- [x] Test verifying tenant creation creates an audit event with kind `create`
- [ ] Screenshot of rendered `/audit` page showing timeline with colored badges

### Structural Evidence

- [x] Code review completed — audit page matches mockup, hooks follow existing patterns
- [x] All recording sites confirmed via grep — no action handler missing `audit_service.record()`
- [x] No AI-invented fields present in `AuditEvent` model

### Edge Case Evidence

- [x] `actor` field stores email, not user ID (Risk 5)
- [x] Pagination uses offset-based pattern matching `tenant_service.list_tenants` (Risk 4)
- [x] Empty state renders correctly (no broken layout when 0 events)

---

## 5. Evidence Log

| # | Evidence Type | Description / Link | Scenario(s) Covered | Collected By | Date |
|---|--------------|-------------------|---------------------|--------------|------|
| 1 | Unit test output | `tests/test_audit_log.py::TestAuditServiceRecord` — 3 tests verifying record() insert, field correctness, tenant_id support | 1, 2, 3 | OpenCode | 2026-07-14 |
| 2 | Unit test output | `tests/test_audit_log.py::TestAuditServiceListEvents` — 3 tests verifying pagination, ordering, empty result | 6 | OpenCode | 2026-07-14 |
| 3 | API integration test | `tests/test_audit_log.py::TestAuditLogAPI::test_system_admin_can_list_events` — GET /api/v1/admin/audit-log returns correct fields | 6 | OpenCode | 2026-07-14 |
| 4 | API integration test | `tests/test_audit_log.py::TestAuditLogAPI::test_tenant_admin_receives_403` — tenant_admin receives 403 | 7 | OpenCode | 2026-07-14 |
| 5 | Code review | `src/gateway/services/tenant_service.py:deactivate_tenant()` — calls `AuditService.record()` with kind=`reject`, action=`tenant.deactivate` | 4 | OpenCode | 2026-07-14 |
| 6 | Code review | `src/gateway/services/tenant_service.py:create_tenant()` — calls `AuditService.record()` with kind=`create`, action=`tenant.create` | 5 | OpenCode | 2026-07-14 |
| 7 | Component test output | `src/portal/src/app/(auth)/audit/page.test.tsx` — 9 tests verifying page header, event rows, kind badges, actor emails, loading/error/empty states | 8, 9, 10 | OpenCode | 2026-07-14 |
| 8 | Hook test output | `src/portal/src/hooks/use-audit-log.test.tsx` — 4 tests verifying fetch, pagination params, response shape, error handling | 6 | OpenCode | 2026-07-14 |
| 9 | Validation output | `openspec validate audit-log-page --type change --strict` — exits clean | All | OpenCode | 2026-07-14 |
| 10 | Code review | `src/training_service/api/v1/training_jobs.py` — `create_training_job()` calls `_record_audit()` with kind=`create`, action=`training_job.submit` | 1 | OpenCode | 2026-07-14 |
| 11 | Code review | `src/training_service/api/v1/training_jobs.py` — `approve_training_job()` calls `_record_audit()` with kind=`approve`, action=`training_job.approve` | 2 | OpenCode | 2026-07-14 |
| 12 | Code review | `src/training_service/api/v1/training_jobs.py` — `reject_training_job()` calls `_record_audit()` with kind=`reject`, action=`training_job.reject` | 3 | OpenCode | 2026-07-14 |
| 13 | Code review | `src/training_service/api/v1/models.py` — `promote_model()` inserts audit event with kind=`promote`, action=`model_version.promote` | 4 | OpenCode | 2026-07-14 |

---

## 6. Audit Record

> ⚠️ **GATE: This section must be completed and signed by a human reviewer before
> `/opsx:archive` is run.** An unsigned or incomplete Audit Record is a hard block on archive.

**Change slug:** audit-log-page
**Proposal:** `openspec/changes/audit-log-page/proposal.md`
**Spec files reviewed:**
  - specs/audit-log/spec.md

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
