## 1. Backend: surface tenant_id on training job responses

- [x] 1.1 Add `tenant_id: str` to `TrainingJobResponse` and confirm `TrainingJobListResponse.items` inherits it, in `src/training_service/api/v1/schemas.py`.
- [x] 1.2 Populate `tenant_id` in `_row_to_response()` (`src/training_service/api/v1/training_jobs.py`) from the existing row data (already selected via `SELECT *` in `repository.py`).
- [x] 1.3 Verification: extend `tests/test_training_jobs.py` to cover scenarios 1–5 (existing get-status shapes, now asserting `tenant_id` is present) and scenario 11 (list items include `tenant_id`). Record this file as the Verification Artifact for rows 1–5, 11 in verification.md § Spec Alignment.

## 2. Backend: System Admin cross-tenant detail and list access

- [x] 2.1 In `get_training_job` (`training_jobs.py`), keep the existing 400-when-missing-tenant_id behavior for System Admin; confirm the correct/wrong `tenant_id` paths return 200/404 respectively using the now-present `tenant_id` field.
- [x] 2.2 Rework `list_training_jobs` for the `system_admin` role: when `tenant_id` is provided, keep current single-tenant behavior (via `TrainingJobRepository.list_by_tenant`); when absent, aggregate across all active tenant schemas (reuse the schema-enumeration pattern from `src/gateway/api/v1/dashboard.py::_all_tenant_schemas`, adapted to the training service's DB access) defaulting to `status=pending_approval` when no explicit `status` is given, and honoring an explicit `status` filter across all tenants otherwise. Apply pagination after aggregation.
- [x] 2.3 Ensure each aggregated list item carries its own `tenant_id` (already available per-schema).
- [x] 2.4 Verification: extend `tests/test_training_jobs.py` to cover scenarios 6–8 (System Admin detail: correct/missing/wrong tenant_id) and scenarios 9, 10, 12, 13, 14 (list: status filter, pagination, explicit tenant_id, aggregated default, aggregated with status filter). Record this file as the Verification Artifact for rows 6–10, 12–14.

## 3. Frontend: thread tenant_id through selection, detail, and actions

- [x] 3.1 Add `tenant_id` to the portal's `TrainingJob` type (`src/portal/src/types/training-jobs.ts`).
- [x] 3.2 Update `useTrainingJob` (`src/portal/src/hooks/use-training-job.ts`) to accept the viewer's role/tenant context and append `?tenant_id=` when fetching as `system_admin`, sourcing the value from the selected job row (not `useAuth()`).
- [x] 3.3 Update `src/portal/src/app/(auth)/training-jobs/page.tsx` so the selected job's own `tenant_id` (from `listData`/`selectedJob`) is passed to `useTrainingJob` and to `JobActions`, replacing the current `user?.tenantId ?? ""` value used for `JobActions`.
- [x] 3.4 Confirm `JobList`/row rendering (`src/portal/src/components/training-jobs/job-list.tsx`) passes through `tenant_id` from list items so `handleSelect` has it available.
- [x] 3.5 Verification: add System Admin coverage to `src/portal/src/app/(auth)/training-jobs/page.test.tsx` (currently has none) and update `src/portal/src/hooks/use-training-job.test.tsx`, `src/portal/src/hooks/use-training-jobs.test.tsx`, and `src/portal/src/components/training-jobs/job-actions.test.tsx` to assert `tenant_id` is sent/used correctly, including a fixture where the viewer's own tenant differs from the selected job's tenant (Hallucination Risk 5). Record these files as the Verification Artifact for rows 6–14 (frontend half) as applicable.

## 4. Frontend: clear query cache on logout

- [x] 4.1 In `src/portal/src/lib/auth.tsx`, give `logout()` access to the app's `QueryClient` (e.g. via `useQueryClient()` in the provider, or by having `AuthProvider` accept it) and call `queryClient.clear()` before/after the logout API call resolves.
- [x] 4.2 Verification: extend `src/portal/src/lib/auth.test.tsx` to cover scenario 17 (logout clears cached query data) alongside the existing scenario 16 coverage (`logout calls logout API and clears token and user`, line ~107). Record this file as the Verification Artifact for rows 15–20.

## 5. Gateway: fix dashboard summary transaction cascade

- [x] 5.1 In `_system_admin_data()` (`src/gateway/api/v1/dashboard.py`), add `await db.rollback()` inside each per-schema `except Exception:` block (both the `training_jobs` pending-count loop and the `model_versions` F1 loop, and the `documents` count loop for consistency), so a failure in one schema does not poison the session for subsequent schemas or subsequent metric blocks.
- [x] 5.2 Keep (or add) error logging in each except block so the root cause of a schema failure remains diagnosable, without letting the exception propagate.
- [x] 5.3 Verification: extend `tests/test_dashboard_summary.py` to cover scenario 27 (one tenant schema failure does not blank out other tenants' stats) alongside existing coverage for scenarios 21–26. Record this file as the Verification Artifact for rows 21–27.

## 6. Type-level verification

- [x] 6.1 Verification: confirm `DashboardData` TypeScript type coverage for scenarios 28–29 via existing type-check tooling (`tsc --noEmit` or the portal's existing type test, if any). Record the artifact for rows 28–29 in verification.md.

## 7. Verification & Evidence

- [ ] 7.1 Run all acceptance-criteria tests for every scenario in
         verification.md § Spec Alignment and confirm all pass.
- [x] 7.2 Collect functional evidence (screenshot / test output / log) for each
         scenario — record one entry per row in verification.md § Evidence Log.
- [x] 7.3 Confirm every Hallucination Risk mitigation step in
         verification.md § Hallucination Risk Register.
- [x] 7.4 Confirm all ADR compliance steps in
         verification.md § Pattern & ADR Compliance.
- [ ] 7.5 Complete Audit Record sign-off in verification.md § Audit Record
         (human reviewer required — this task cannot be marked complete by an agent).
- [x] 7.6 Run `openspec validate fix-system-admin-training-queue-bugs --type change --strict` and confirm
         it exits clean before archive.
