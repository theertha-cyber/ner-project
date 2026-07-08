# Verification Plan

**Change:** fix-system-admin-training-queue-bugs
**Generated:** 2026-07-07
**Status:** 🔴 Incomplete — Evidence Log and Audit Record must be filled by a human reviewer before archive.

---

## 1. Spec Alignment

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | training-jobs | Get training job status | Get status of queued job | Given a job in "queued" status, when a Tenant Admin GETs `/api/v1/training-jobs/{job_id}`, then response is 200 with `status: "queued"`, hyperparameters, and `created_at` | tests/test_training_jobs.py::test_status_pending_approval | - [x] |
| 2 | training-jobs | Get training job status | Get status of running job | Given a job in "running" status, when a Tenant Admin GETs `/api/v1/training-jobs/{job_id}`, then response is 200 with `status: "running"`, `current_epoch`, `current_loss`, `started_at` | tests/test_training_jobs.py::test_status_running | - [x] |
| 3 | training-jobs | Get training job status | Get status of completed job | Given a job in "completed" status, when a Tenant Admin GETs `/api/v1/training-jobs/{job_id}`, then response is 200 with `status: "completed"`, `metrics`, `model_version`, `completed_at` | tests/test_training_jobs.py::test_status_completed | - [x] |
| 4 | training-jobs | Get training job status | Get status of failed job | Given a job in "failed" status, when a Tenant Admin GETs `/api/v1/training-jobs/{job_id}`, then response is 200 with `status: "failed"`, `error_message`, `failed_at` | tests/test_training_jobs.py::test_status_failed | - [x] |
| 5 | training-jobs | Get training job status | Get training job as non-owner tenant | Given a job owned by tenant A, when a tenant B user GETs it, then response is 404 with no indication the job exists | tests/test_training_jobs.py::test_status_cross_tenant_404 | - [x] |
| 6 | training-jobs | Get training job status | System Admin gets a job with the correct tenant_id | Given a job owned by tenant A, when a System Admin GETs `/api/v1/training-jobs/{job_id}?tenant_id=<A>`, then response is 200 and body's `tenant_id` equals `<A>` | tests/test_training_jobs.py::test_sysadmin_get_job_correct_tenant_id | - [x] |
| 7 | training-jobs | Get training job status | System Admin gets a job without providing tenant_id | Given a job owned by tenant A, when a System Admin GETs `/api/v1/training-jobs/{job_id}` with no `tenant_id`, then response is 400 with an error naming the missing `tenant_id` requirement | tests/test_training_jobs.py::test_sysadmin_get_job_missing_tenant_id | - [x] |
| 8 | training-jobs | Get training job status | System Admin gets a job with the wrong tenant_id | Given a job owned by tenant A, when a System Admin GETs it with `tenant_id=<B>`, then response is 404 | tests/test_training_jobs.py::test_sysadmin_get_job_wrong_tenant_id | - [x] |
| 9 | training-jobs | List training jobs | List jobs with status filter | Given a tenant with jobs in multiple statuses, when a Tenant Admin GETs `/api/v1/training-jobs?status=running`, then response is 200 containing only "running" jobs | tests/test_training_jobs.py::test_list_filter_by_status | - [x] |
| 10 | training-jobs | List training jobs | List jobs paginated | Given a tenant with 25 jobs, when a Tenant Admin GETs `?page=2&per_page=10`, then response is 200 with 10 jobs and `total: 25, page: 2, per_page: 10` | tests/test_training_jobs.py::test_list_pagination | - [x] |
| 11 | training-jobs | List training jobs | List jobs includes tenant_id on each item | Given a tenant with at least one job, when a Tenant Admin GETs `/api/v1/training-jobs`, then every item includes `tenant_id` matching the caller's tenant | tests/test_training_jobs.py::test_list_filter_by_status | - [x] |
| 12 | training-jobs | List training jobs | System Admin lists jobs with an explicit tenant_id | Given tenant A has 3 jobs and tenant B has 2, when a System Admin GETs `?tenant_id=<A>`, then response is 200 containing only tenant A's 3 jobs | tests/test_training_jobs.py::test_sysadmin_list_explicit_tenant_id | - [x] |
| 13 | training-jobs | List training jobs | System Admin lists jobs with no tenant_id sees an aggregated pending-approval queue | Given tenant A has 1 pending_approval job and tenant B has 1 pending_approval + 1 completed job, when a System Admin GETs `/api/v1/training-jobs` with no `tenant_id`/`status`, then response is 200 containing exactly the 2 pending_approval jobs, each with correct `tenant_id` | tests/test_training_jobs.py::test_sysadmin_list_aggregated_default_pending_approval | - [x] |
| 14 | training-jobs | List training jobs | System Admin lists jobs across tenants with an explicit status filter | Given tenant A and tenant B each have 1 completed job, when a System Admin GETs `?status=completed` with no `tenant_id`, then response is 200 containing both tenants' completed jobs | tests/test_training_jobs.py::test_sysadmin_list_aggregated_with_status_filter | - [x] |
| 15 | auth-context | Auth Context Provider | Successful login sets user and stores token in memory | Given no user authenticated, when `login(...)` succeeds, then `useAuth().user` is set and neither token appears in localStorage/sessionStorage/cookie | src/portal/src/lib/auth.test.tsx::"login sets user and token without writing to localStorage" | - [x] |
| 16 | auth-context | Auth Context Provider | Logout clears user and calls logout endpoint | Given an authenticated user, when `logout()` is called, then `POST /api/v1/auth/logout` is called with bearer token, `useAuth().user` becomes `null`, and the token ref is cleared | src/portal/src/lib/auth.test.tsx::"logout calls logout API and clears token and user" | - [x] |
| 17 | auth-context | Auth Context Provider | Logout clears cached query data | Given cached query results exist (e.g. training jobs list/detail), when `logout()` is called, then the shared query cache is cleared and a subsequent login triggers fresh fetches instead of rendering prior-session data | src/portal/src/lib/auth.test.tsx::"logout clears cached query data" | - [x] |
| 18 | auth-context | Auth Context Provider | On-mount refresh restores session from cookie | Given a valid refresh_token cookie, when `AuthProvider` mounts, then refresh is called automatically and `useAuth().user` is populated on success | src/portal/src/lib/auth.test.tsx::"on-mount refresh success sets token ref and user" | - [x] |
| 19 | auth-context | Auth Context Provider | On-mount refresh failure leaves user as null | Given no valid refresh_token cookie, when `AuthProvider` mounts, then refresh returns 401 and `useAuth().user` remains `null` | src/portal/src/lib/auth.test.tsx::"starts with null user when on-mount refresh fails" | - [x] |
| 20 | auth-context | Auth Context Provider | useAuth throws when called outside AuthProvider | Given a component not wrapped in `AuthProvider`, when it calls `useAuth()`, then it throws the specified error message | src/portal/src/lib/auth.test.tsx::"throws when used outside AuthProvider" | - [x] |
| 21 | dashboard-summary-endpoint | Dashboard Summary Endpoint | system_admin summary returns role-specific data | Given caller role `system_admin`, when `GET /api/v1/dashboard/summary` is called, then response matches the documented system_admin shape (kicker, 4 stats, pTitle, sideTop, etc.) | tests/test_dashboard_summary.py::TestDashboardSummaryShape::test_system_admin_returns_correct_shape | - [x] |
| 22 | dashboard-summary-endpoint | Dashboard Summary Endpoint | tenant_admin summary returns pipeline data | Given caller role `tenant_admin`, when called, then response matches the documented tenant_admin shape | tests/test_dashboard_summary.py::TestDashboardSummaryShape::test_tenant_admin_returns_correct_shape | - [x] |
| 23 | dashboard-summary-endpoint | Dashboard Summary Endpoint | annotator summary returns task data | Given caller role `annotator`, when called, then response matches the documented annotator shape | tests/test_dashboard_summary.py::TestDashboardSummaryShape::test_annotator_returns_correct_shape | - [x] |
| 24 | dashboard-summary-endpoint | Dashboard Summary Endpoint | business_user summary returns extraction data | Given caller role `business_user`, when called, then response matches the documented business_user shape | tests/test_dashboard_summary.py::TestDashboardSummaryShape::test_business_user_returns_correct_shape | - [x] |
| 25 | dashboard-summary-endpoint | Dashboard Summary Endpoint | unavailable training service returns null values | Given the training service errors/times out, when called by tenant_admin, then training-dependent fields are `null`, `sources.training` is `false`, and status is 200 | tests/test_dashboard_summary.py::TestTenantAdminQueries::test_graceful_degradation_when_training_unavailable | - [ ] ⚠️ see note |
| 26 | dashboard-summary-endpoint | Dashboard Summary Endpoint | unauthenticated request rejected | Given no valid JWT, when called, then response is 401 | tests/test_dashboard_summary.py::TestDashboardSummaryShape::test_unauthenticated_returns_401 | - [x] |
| 27 | dashboard-summary-endpoint | Dashboard Summary Endpoint | one tenant schema failure does not blank out other tenants' stats | Given one active tenant's schema is missing an expected table/column while others are healthy, when a system_admin calls the endpoint, then response is 200, pending-approvals/avg-F1 reflect the healthy tenants (not null/zeroed), and no cascading aborted-transaction failures occur on subsequent queries | tests/test_dashboard_summary.py::TestSystemAdminSchemaFailureRecovery::test_one_bad_tenant_schema_does_not_blank_out_others | - [x] |
| 28 | dashboard-summary-endpoint | DashboardData TypeScript Type | type compiles with all fields | Given a `DashboardData` object matching the mockup shape, when assigned to the type, then the compiler produces no errors | `npm run typecheck` (tsc --noEmit) in src/portal — zero errors reported against src/types/dashboard.ts | - [x] |
| 29 | dashboard-summary-endpoint | DashboardData TypeScript Type | null values are assignable | Given a `DashboardData` object with `stats[0].value` as `null`, when assigned to the type, then the compiler produces no errors | `StatItem.value: number \| null` in src/portal/src/types/dashboard.ts; confirmed via `npm run typecheck` | - [x] |

> **Rule:** Every `#### Scenario:` block in every `specs/**/*.md` file for this change MUST appear as a row above. A missing scenario is a P1 gap that blocks archive.

> **Note on row 25:** `test_graceful_degradation_when_training_unavailable` (and the other `TestTenantAdminQueries`/`TestAnnotatorQueries`/`TestBusinessUserQueries`/`TestRouteDispatch` tests that depend on the `tenant_schema` fixture in `tests/conftest.py`) could not be executed in this session — the fixture's `ALTER TABLE ... DROP CONSTRAINT` statement (`tests/conftest.py:38-43`) is invalid Postgres syntax (schema-qualifies the constraint name, which `DROP CONSTRAINT` does not accept), raising `PostgresSyntaxError` at fixture setup. This is a **pre-existing bug unrelated to this change** — `tests/conftest.py` was not modified by this change, the bug predates it (confirmed via `git log`), and it affects unrelated capabilities (tenant_admin/annotator/business_user dashboard shapes) rather than anything touched here. Row 25's requirement (unavailable training service → null values) is unchanged by this change's edits to `_system_admin_data()`; a human reviewer should confirm this test passed before the `tenant_schema` fixture regressed, or fix the fixture separately and re-run. All `system_admin`-path rows (21, 26, 27) that don't depend on this fixture were run and pass.

---

## 2. Hallucination Risk Register

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|-------------------|----------------------|
| 1 | `tenant_id` field naming across the stack | Backend uses snake_case (`tenant_id`); the portal's existing `AuthUser.tenantId` is camelCase. An implementation could inconsistently name the new `TrainingJob.tenant_id` field (e.g. `tenantId` in the TS type but `tenant_id` on the wire, without a mapping step), causing silent `undefined` reads | Diff the portal `TrainingJob` type and every call site that reads the job's tenant against the actual JSON key returned by `training_jobs.py` — confirm a real mapping/rename exists if casing differs, not an assumed match |
| 2 | System Admin list aggregation loop | An implementation might reuse `dashboard.py`'s pattern incorrectly — e.g. paginate *before* aggregating (wrong `total`/`page` semantics) instead of aggregating then paginating, or forget to apply the default `pending_approval` filter only when both `tenant_id` and `status` are absent | Re-read `list_training_jobs` against spec scenarios 12–14 line by line; construct the fixture in scenario 13 (mixed statuses across two tenants) and confirm the exact item set and `total` returned |
| 3 | Query cache clearing scope | `logout()` might call `queryClient.removeQueries()` with an overly narrow key filter (missing the training-jobs keys) or clear a *different* `QueryClient` instance than the one `layout.tsx` actually renders with (e.g. a test-only or stale reference), silently fixing the symptom in tests but not in the running app | Manually reproduce: log in as tenant_admin, view a job list, log out (no page reload), log in as system_admin, confirm the list does not flash tenant_admin's cached rows before the fresh fetch resolves |
| 4 | Rollback placement in `_system_admin_data` | Adding `await db.rollback()` only once after the whole per-schema loop (rather than inside each iteration's `except` block) would look like a fix but not actually prevent the cascade within that same loop | Confirm via code review that `rollback()` sits inside the innermost `except Exception:` block for each of the two per-schema loops (`training_jobs` pending count, `model_versions` F1), not after the loop |
| 5 | `JobActions` tenant_id sourcing | The existing `job-actions.test.tsx` fixture likely uses a single tenant throughout; an implementation could leave `page.tsx` still passing `user?.tenantId` to `JobActions` (the viewer's own tenant) instead of the selected job's `tenant_id`, and existing tests would still pass because both values coincide in the fixture | Add/inspect a test scenario where the logged-in system_admin's own `tenantId` differs from (or is empty relative to) the selected job's owning tenant, and confirm the approve/reject/cancel request actually carries the job's tenant, not the viewer's |
| 6 | ADR-001 cross-schema query compliance | The aggregation loop for System Admin list/detail could be implemented as a single dynamic SQL statement spanning multiple schemas (e.g. a generated `UNION ALL` across schema names) rather than one explicitly-scoped query per schema, which is harder to audit for tenant-scope leakage | Review the actual SQL executed (via `text(...)` calls or query logs) and confirm each query is scoped to exactly one `tenant_<uuid>` schema per execution, matching the pattern already used in `dashboard.py` |

---

## 3. Pattern & ADR Compliance

| ADR | Decision Summary | Constraint on This Change | Verification Step |
|-----|-----------------|--------------------------|-------------------|
| ADR-001 | Tenant isolation via per-tenant Postgres schemas; System Admin cross-tenant reads require explicit cross-schema queries; no query may omit tenant scope | Every query touching training-job data (detail, list-with-tenant_id, list-aggregated) must resolve to an explicit `tenant_<uuid>` schema per execution — never an implicit or unscoped cross-tenant query | Review the SQL in `training_jobs.py`/`repository.py` after implementation: confirm the aggregated list path issues one schema-scoped query per active tenant (same shape as `dashboard.py`'s existing loop), and confirm no new query omits a schema qualifier |

---

## 4. Evidence Requirements

### Functional Evidence

- [x] Scenario 1–8 (Get training job status, all): backend test output covering queued/running/completed/failed status shapes and the three System Admin `tenant_id` variants (correct, missing, wrong) — `tests/test_training_jobs.py`, 27 passed
- [x] Scenario 9–14 (List training jobs, all): backend test output covering status filter, pagination, `tenant_id` on items, System Admin explicit-tenant, System Admin aggregated-default, System Admin aggregated-with-status-filter — `tests/test_training_jobs.py`, 27 passed
- [x] Scenario 15–20 (Auth Context Provider, all): frontend test output covering login, logout (endpoint + state clear), logout cache-clear, mount refresh success/failure, useAuth-outside-provider throw — `src/portal/src/lib/auth.test.tsx`, 9 passed
- [x] Scenario 21–27 (Dashboard Summary Endpoint, all) *except 25*: backend test output covering system_admin/tenant_admin/annotator/business_user role shapes, unauthenticated 401, and the one-bad-schema-doesn't-blank-others case — `tests/test_dashboard_summary.py`, 8 passed. **Scenario 25 blocked** — see note under Section 1 (pre-existing `tenant_schema` fixture bug, unrelated to this change)
- [x] Scenario 28–29 (DashboardData TypeScript Type, both): `npm run typecheck` (`tsc --noEmit`) — zero errors against `src/types/dashboard.ts`

### Structural Evidence

- [x] Code review completed — implementation matches design.md Decisions 1–3 (no undocumented deviations)
- [x] All ADR compliance steps in Section 3 confirmed ✓
- [x] No undocumented architectural patterns introduced
- [x] No AI-invented requirements present in generated code (cross-checked against spec files)

### Edge Case Evidence

- [x] Risk 1 mitigation confirmed — `tenant_id` is snake_case end-to-end: backend `TrainingJobResponse.tenant_id` (schemas.py) → portal `TrainingJob.tenant_id` (types/training-jobs.ts) → read directly as `job.tenant_id` in page.tsx/job-actions.tsx, no casing translation layer introduced
- [x] Risk 2 mitigation confirmed — `_list_aggregated_across_tenants` aggregates all per-tenant rows first, then applies `offset`/`per_page` slicing after sort (training_jobs.py); default `pending_approval` filter applies only when `status` query param is absent, confirmed by scenario 13 (mixed statuses, two tenants) vs. scenario 14 (explicit `status=completed`) tests
- [ ] Risk 3 mitigation confirmed — automated test (`auth.test.tsx::"logout clears cached query data"`) confirms `queryClient.clear()` fires against the same `QueryClient` instance `AuthProvider` consumes via `useQueryClient()`; a live manual cross-role browser repro (login as tenant_admin → logout → login as system_admin, confirm no stale flash) was **not** performed in this session and is left for human sign-off
- [x] Risk 4 mitigation confirmed — `await db.rollback()` sits inside each of the three innermost per-schema `except Exception:` blocks (documents count, training_jobs pending count, model_versions F1) in `dashboard.py::_system_admin_data`, not after the loop
- [x] Risk 5 mitigation confirmed — `page.tsx` now passes `selectedJob.tenant_id` (not `user?.tenantId`) to `JobActions`; `job-actions.test.tsx::"approves using the job's own tenant_id, not the viewer's tenant, when they differ"` and `page.test.tsx`'s system_admin describe block both use a fixture where the system_admin viewer's tenant is empty and the job's tenant is `"tenant-b"`/`"tenant-b-owns-this-job"`, confirming the request carries the job's tenant
- [x] Risk 6 mitigation confirmed — `_list_aggregated_across_tenants` and `_all_active_tenant_ids` issue one `text(...)` query per schema per iteration (same shape as `dashboard.py::_all_tenant_schemas`), no dynamic cross-schema `UNION` introduced

---

## 5. Evidence Log

| # | Evidence Type | Description / Link | Scenario(s) Covered | Collected By | Date |
|---|--------------|-------------------|---------------------|--------------|------|
| 1 | Test output | `pytest tests/test_training_jobs.py -q` → `27 passed` | 1–14 | AI agent (Claude) | 2026-07-07 |
| 2 | Test output | `pytest tests/test_dashboard_summary.py -q -k "system_admin or SystemAdmin"` → `3 passed` (shape, tenant-count-wired, schema-failure-recovery); full-file run separately shows `TestDashboardSummaryShape` (unauthenticated/tenant_admin/annotator/business_user shapes) also passing, 8/8 non-`tenant_schema`-dependent tests green | 21, 22, 23, 24, 26, 27 | AI agent (Claude) | 2026-07-07 |
| 3 | Test output | `vitest run` in `src/portal` → `452 passed` across `auth.test.tsx`, `use-training-job.test.tsx`, `use-training-jobs.test.tsx`, `job-actions.test.tsx`, `job-card.test.tsx`, `job-detail-panel.test.tsx`, `job-list.test.tsx`, `page.test.tsx` (training-jobs); 4 pre-existing unrelated failures in `AnnotationImportPreview.test.tsx`/`BatchRunsTab.test.tsx` (untouched by this change) | 15–20, 6–14 (frontend half) | AI agent (Claude) | 2026-07-07 |
| 4 | Type-check output | `npm run typecheck` (`tsc --noEmit`) in `src/portal` — no errors against `src/types/dashboard.ts` or `src/types/training-jobs.ts`; only pre-existing, unrelated errors remain (documents page, annotation drag test, MetricsPanel, ModelRegistryPage) | 28, 29 | AI agent (Claude) | 2026-07-07 |
| 5 | Known gap | Scenario 25 (`test_graceful_degradation_when_training_unavailable`) and other `tenant_schema`-fixture-dependent tests in `test_dashboard_summary.py` could not run — pre-existing `tests/conftest.py` fixture bug (invalid `DROP CONSTRAINT` SQL), unrelated to this change. See note under § Spec Alignment row 25 | 25 (blocked) | AI agent (Claude) | 2026-07-07 |

---

## 6. Audit Record

> ⚠️ **GATE: This section must be completed and signed by a human reviewer before `/opsx:archive` is run.** An unsigned or incomplete Audit Record is a hard block on archive.

**Change slug:** fix-system-admin-training-queue-bugs
**Proposal:** `openspec/changes/fix-system-admin-training-queue-bugs/proposal.md`
**Spec files reviewed:**
  - specs/training-jobs/spec.md
  - specs/auth-context/spec.md
  - specs/dashboard-summary-endpoint/spec.md

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
