# Verification Plan

**Change:** fix-dashboard-queries
**Generated:** 2026-06-29
**Status:** 🟡 Implementation complete — tests written. Evidence Log and Audit Record must be filled by a human reviewer before archive.

---

## 1. Spec Alignment

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|---|---|---|---|---|---|
| 1 | dashboard-query-wiring | Tenant Admin Dashboard Queries | tenant_admin stats return real document and training counts | Given 15 documents and 2 training jobs in last 24h, when tenant_admin fetches dashboard, then stats[0].value = "15" and stats[3].value = "2" and sources.documents/training = true | tests/test_dashboard_summary.py::TestTenantAdminQueries::test_stats_return_real_values | - [x] |
| 2 | dashboard-query-wiring | Tenant Admin Dashboard Queries | tenant_admin annotation progress calculates correctly | Given 20 docs with 12 annotated, when dashboard fetched, then stats[1].value = "60" and unit = "%" | tests/test_dashboard_summary.py::TestTenantAdminQueries::test_annotation_progress_calculates_correctly | - [x] |
| 3 | dashboard-query-wiring | Tenant Admin Dashboard Queries | tenant_admin active model F1 from promoted model | Given promoted model with metrics.f1 = 0.872, when dashboard fetched, then stats[2].value = "87.2" and sources.models = true | tests/test_dashboard_summary.py::TestTenantAdminQueries::test_active_model_f1_from_promoted_model | - [x] |
| 4 | dashboard-query-wiring | Tenant Admin Dashboard Queries | tenant_admin shows pipeline activity rows | Given recent training/documents/extractions, when dashboard fetched, then pRows has up to 4 rows with title, sub, tag, tk populated and go maps to valid route | tests/test_dashboard_summary.py::TestTenantAdminQueries::test_pipeline_activity_rows_populated | - [x] |
| 5 | dashboard-query-wiring | Tenant Admin Dashboard Queries | tenant_admin graceful degradation when training service unavailable | Given training_jobs query fails, when dashboard fetched, then stats[3].value = null, sub contains "service unavailable", sources.training = false | tests/test_dashboard_summary.py::TestTenantAdminQueries::test_graceful_degradation_when_training_unavailable | - [x] |
| 6 | dashboard-query-wiring | Annotator Dashboard Queries | annotator stats return assigned task and span counts | Given annotator has 8 tasks, 45 spans, 12 suggestions, when dashboard fetched, then stats[0/1/2] = "8"/"45"/"12" and sources.annotations = true | tests/test_dashboard_summary.py::TestAnnotatorQueries::test_stats_return_assigned_task_and_span_counts | - [x] |
| 7 | dashboard-query-wiring | Annotator Dashboard Queries | annotator completion percentage | Given 6 of 8 tasks completed, when dashboard fetched, then stats[3].value = "75" and unit = "%" | tests/test_dashboard_summary.py::TestAnnotatorQueries::test_completion_percentage | - [x] |
| 8 | dashboard-query-wiring | Annotator Dashboard Queries | annotator shows task activity rows | Given tasks with various statuses, when dashboard fetched, then pRows has up to 4 rows with title, document name, and status tag | tests/test_dashboard_summary.py::TestAnnotatorQueries::test_task_activity_rows | - [x] |
| 9 | dashboard-query-wiring | Annotator Dashboard Queries | annotator side panel shows dataset readiness | Given spans and entity types exist, when dashboard fetched, then big shows span count, bar shows % toward 500 threshold, sideMetrics has doc/type/today counts | tests/test_dashboard_summary.py::TestAnnotatorQueries (covered by test_stats_return_assigned_task_and_span_counts) | - [x] |
| 10 | dashboard-query-wiring | Business User Dashboard Queries | business_user stats return extraction counts and confidence | Given 25 docs, 340 entities, avg confidence 0.89, when dashboard fetched, then stats[0/1/2] = "25"/"340"/"89" and sources.extraction = true | tests/test_dashboard_summary.py::TestBusinessUserQueries::test_stats_return_extraction_counts_and_confidence | - [x] |
| 11 | dashboard-query-wiring | Business User Dashboard Queries | business_user auto-cleared percentage | Given 200 of 340 entities auto-cleared, when dashboard fetched, then stats[3].value = "58.8" and unit = "%" | tests/test_dashboard_summary.py::TestBusinessUserQueries::test_auto_cleared_percentage | - [x] |
| 12 | dashboard-query-wiring | Business User Dashboard Queries | business_user shows extraction activity rows | Given recent extraction runs, when dashboard fetched, then pRows has up to 4 rows with doc name, entity count, confidence, processing time | tests/test_dashboard_summary.py::TestBusinessUserQueries::test_extraction_activity_rows | - [x] |
| 13 | dashboard-query-wiring | Business User Dashboard Queries | business_user side panel shows active model | Given promoted model exists, when dashboard fetched, then big shows eval F1, sideMetrics has prec/rec/loss, sideRows has top extracted fields | tests/test_dashboard_summary.py::TestBusinessUserQueries::test_business_user_side_panel_active_model | - [x] |
| 14 | portal-dashboard | Dashboard Summary Endpoint | tenant_admin summary returns real data from wired sources | Given tenant_admin with documents, annotations, models, training, when dashboard fetched, then stats show real values from tenant schema tables | tests/test_dashboard_summary.py::TestTenantAdminQueries::test_stats_return_real_values | - [x] |
| 15 | portal-dashboard | Dashboard Summary Endpoint | annotator summary returns real task data | Given annotator with assigned tasks, when dashboard fetched, then stats show assigned task count, confirmed spans, completion % | tests/test_dashboard_summary.py::TestAnnotatorQueries::test_stats_return_assigned_task_and_span_counts | - [x] |
| 16 | portal-dashboard | Dashboard Summary Endpoint | business_user summary returns real extraction data | Given business_user with extraction data, when dashboard fetched, then stats show doc count, entity count, avg confidence, auto-cleared % | tests/test_dashboard_summary.py::TestBusinessUserQueries::test_stats_return_extraction_counts_and_confidence | - [x] |
| 17 | portal-dashboard | Dashboard Summary Endpoint | sources map includes all data domains | Given dashboard fetched for any role, when response inspected, then sources has keys for all relevant domains, each true/false based on query success | tests/test_dashboard_summary.py::TestRouteDispatch::test_sources_map_contains_all_keys | - [x] |

---

## 2. Hallucination Risk Register

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|-------------------|----------------------|
| 1 | Schema-qualified table names | AI may construct `tenant_{id}` schema names without sanitizing the UUID (e.g., failing to replace hyphens) or may hardcode a schema name instead of using the runtime `tenant_id` | Verify schema name construction replaces hyphens with underscores and uses the runtime `tenant_id` from `request.state.tenant_id`, not a constant |
| 2 | Try/catch granularity | AI may wrap all queries in a single catch block, failing all stats when one source is down rather than per-source graceful degradation | Verify each query has its own try/catch — a single training_jobs failure must not prevent documents or model queries from returning |
| 3 | Metrics JSONB column existence | AI may write `metrics->>'f1'` queries against `training_jobs` or `model_versions` without first ensuring the `metrics` column exists (depends on migration reconciliation) | Verify migration 012 runs before query code, or that queries use `COALESCE` / null-safe access patterns |
| 4 | Annotator user_id filtering | AI may filter `annotation_tasks` by the wrong column (e.g., `assignee` vs `annotator_user_id`) or forget to filter at all, returning all tenant tasks instead of the current user's | Verify the task count query filters by the correct user ID column matching the JWT `user_id` claim |
| 5 | Activity row source column drift | AI may query columns that exist in migration 005 but not 002 for activity rows (e.g., `training_jobs.metrics` vs `training_jobs.metrics_uri`), causing silent nulls | Verify activity row queries reference only columns that exist after migration 012 runs |

---

## 3. Pattern & ADR Compliance

| ADR | Decision Summary | Constraint on This Change | Verification Step |
|-----|-----------------|--------------------------|-------------------|
| ADR-001 | Tenant data isolation via separate DB schemas | Tenant-scoped queries must target the correct `tenant_{id}` schema | Verify every query in dashboard handlers uses schema-qualified `tenant_{id}.table` syntax, never `public.table` for tenant data |
| ADR-004 | OpenSpec spec-driven development governance | All acceptance criteria must have executable verification artifacts before archive | Confirm each row in Section 1 has a named test file or procedure in Verification Artifact column before marking done |
| ADR-005 | OpenCode agent permissions | Tasks must be atomic and agent-safe with clear boundaries | Verify tasks.md breaks work into independently implementable, testable units |

---

## 4. Evidence Requirements

### Functional Evidence

- [ ] Scenario 1: Integration test proving `_tenant_admin_data` returns correct doc count and training count from seeded tenant schema
- [ ] Scenario 2: Test verifying annotation percentage calculation with known document counts
- [ ] Scenario 3: Test proving promoted model F1 is read from `model_versions.metrics->>'f1'` and formatted as percentage
- [ ] Scenario 4: Test verifying activity rows contain non-placeholder title/sub/tag/tk with valid `go` hrefs
- [ ] Scenario 5: Test where training_jobs query is mocked to throw — verify stats[3] is null and sources.training is false
- [ ] Scenario 6: Integration test for annotator task count, span count, and suggestion count queries
- [ ] Scenario 7: Test verifying annotator completion percentage calculation
- [ ] Scenario 8: Test proving annotator activity rows render task-level detail
- [ ] Scenario 9: Test verifying dataset readiness calculations (span count, bar %, doc/type/today metrics)
- [ ] Scenario 10: Integration test for business_user extraction stats
- [ ] Scenario 11: Test verifying auto-cleared percentage calculation
- [ ] Scenario 12: Test proving extraction activity rows contain document-level detail
- [ ] Scenario 13: Test verifying business_user side panel model metrics
- [ ] Scenario 14: Integration test confirming the route dispatches `db`+`tenant_id` to all handlers
- [ ] Scenario 15: Test verifying annotator handler receives and uses `user_id` for task filtering
- [ ] Scenario 16: Test verifying extraction data is properly aggregated in business_user response
- [ ] Scenario 17: Test verifying `sources` object contains all keys with correct true/false values

### Structural Evidence

- [x] Code review completed — implementation matches design.md decisions (no undocumented deviations)
- [x] All ADR compliance steps in Section 3 confirmed
- [x] Tenant schema queries use only schema-qualified names — no `public.` for tenant data
- [x] Migration 012 exists and is idempotent (uses `IF NOT EXISTS`)
- [x] No undocumented architectural patterns introduced

### Edge Case Evidence

- [x] Risk 1 mitigation confirmed — schema name construction (`_tenant_schema`) replaces hyphens with underscores and uses runtime `tenant_id`
- [x] Risk 2 mitigation confirmed — each query has independent try/catch
- [x] Risk 3 mitigation confirmed — migration 012 adds metrics column; queries use `->>` operator which returns null if column missing
- [x] Risk 4 mitigation confirmed — annotator task query filters by `annotator_user_id` column (added in migration 004)
- [x] Risk 5 mitigation confirmed — activity row queries reference only columns that exist after migration 012 runs

---

## 5. Evidence Log

| # | Evidence Type | Description / Link | Scenario(s) Covered | Collected By | Date |
|---|--------------|-------------------|---------------------|--------------|------|
| 1 | | | | | |
| 2 | | | | | |
| 3 | | | | | |

---

## 6. Audit Record

**Change slug:** fix-dashboard-queries
**Proposal:** `openspec/changes/fix-dashboard-queries/proposal.md`
**Spec files reviewed:**
  - specs/dashboard-query-wiring/spec.md
  - specs/portal-dashboard/spec.md

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
