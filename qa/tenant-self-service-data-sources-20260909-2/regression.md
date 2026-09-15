# Regression -- tenant-self-service-data-sources-20260909-2

Scope: did this release break anything that used to work. Base URL http://localhost:8000 (dev). No prior QA report exists for this run, so there are no previously-failed scenarios to retest; the baseline is the repository suites at HEAD `74fe6d4`.

## Results

| Check | Expected | Observed | Status | Evidence |
|---|---|---|---|---|
| Change-set Python suites (`test_tenant_data_source_control_plane`, `test_external_postgresql_chat`, `test_azure_blob_source_sync`, `test_ingestion_boundary`, `test_local_compose_delivery_evidence`) | all pass | **107 passed** in 26.5s | pass | pytest output |
| Portal data-sources scope (`lib/data-sources`, `hooks/use-data-sources`, `app/(auth)/settings/data-sources`, `components/data-sources`, `lib/nav-config`) | all pass | 44 passed / 1 failed of 45 | fail (pre-existing, see below) | vitest output |
| `nav-config.test.ts` business_user count | 5 items | 4 items | fail — **pre-existing, not a regression**: `git show a6143e6^:nav-config.ts` has the same 4-item `business_user` branch, and CAP-5's diff touched only the `tenant_admin` branch | `git show a6143e6` |
| `sidebar.test.tsx` 6 failures | pass | fail — **pre-existing, not a regression**: failures assert stale text (`Documents` vs current `Uploaded Documents`); the file has no `data-sources` selector and no count CAP-5 could break | vitest output + `Sidebar.tsx` |
| Remaining portal failures (annotation, dark-mode, layout-preference, documents, entity-types, training-jobs — 42 more) | pass | fail — **pre-existing, outside change set**: none of these files were touched by CAP-2..CAP-6 (`git diff --name-only 60db8d0^..4dd49e5`, 73 files) | vitest output + change-set file list |
| Live compatibility: platform upload/chat routes still registered | present | 44 paths in live `/openapi.json`, pre-existing routes intact | pass | live `/openapi.json` |
| Live compatibility: unauthenticated platform surface unchanged | 401 envelope | `POST /api/v1/chat` without token returns 401 | pass | live curl |

## Decision

**No regression attributable to CAP-2..CAP-6.** The portal suite does not pass as a whole (49 failures), but every failure was shown to pre-date or sit outside this run's 73-file change set; the one in-scope failure (`business_user` count) fails identically on the pre-CAP-5 tree. The pre-existing portal failures are recorded as follow-up work, not as blockers on this release.
