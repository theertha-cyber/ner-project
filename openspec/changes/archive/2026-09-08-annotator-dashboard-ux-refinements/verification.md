# Verification Plan

**Change:** annotator-dashboard-ux-refinements
**Generated:** 2026-08-05
**Status:** 🔴 Incomplete — Evidence Log and Audit Record must be filled by a human reviewer before archive.

---

## 1. Spec Alignment

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | dashboard-summary-endpoint | Dashboard Summary Endpoint | system_admin summary returns role-specific data | Given caller role `system_admin`, when GET `/api/v1/dashboard/summary` is called, then response has `kicker: "Platform control plane"`, 4 stats, `pTitle: "Approval queue"` with 4 rows, `sideTop: "Platform health"` with SLA/p95/err/GPU metrics | `tests/test_dashboard_summary_roles.py::test_system_admin_summary_returns_role_specific_data` | - [ ] |
| 2 | dashboard-summary-endpoint | Dashboard Summary Endpoint | tenant_admin summary returns pipeline data | Given caller role `tenant_admin`, when GET `/api/v1/dashboard/summary` is called, then response has 4 pipeline stats, `pTitle: "Pipeline activity"` with 4 rows, `sideTop: "Active model"` with eval F1/precision/recall/loss and quota rows | `tests/test_dashboard_summary_roles.py::test_tenant_admin_summary_returns_pipeline_data` | - [ ] |
| 3 | dashboard-summary-endpoint | Dashboard Summary Endpoint | annotator summary returns task data with entity terminology | Given caller role `annotator`, when GET `/api/v1/dashboard/summary` is called, then response has 3 stats (Assigned tasks, Entities Annotated, Completion %), `pTitle: "My tasks"` with 4 rows, `sideTop: "Dataset readiness"` | `tests/test_dashboard_summary_roles.py::test_annotator_summary_returns_task_data` (updated) | - [x] |
| 4 | dashboard-summary-endpoint | Dashboard Summary Endpoint | annotator dataset readiness reflects real progress and threshold purpose | Given caller role `annotator` and 113 rows in tenant `spans`, when GET `/api/v1/dashboard/summary` is called, then `bar` is `22.6` (not `0`), `sideMeta` conveys 387 more entities needed, `sideBot` conveys 500 entities unlocks training | `tests/test_dashboard_summary_roles.py::test_annotator_dataset_readiness_shows_progress` (new) | - [x] |
| 5 | dashboard-summary-endpoint | Dashboard Summary Endpoint | annotator dataset readiness at or above threshold | Given caller role `annotator` and ≥500 rows in tenant `spans`, when GET `/api/v1/dashboard/summary` is called, then `bar` is `100` and `sideMeta` conveys the threshold has been reached, not a "more needed" count | `tests/test_dashboard_summary_roles.py::test_annotator_dataset_readiness_at_threshold` (new) | - [x] |
| 6 | dashboard-summary-endpoint | Dashboard Summary Endpoint | business_user summary returns extraction data | Given caller role `business_user`, when GET `/api/v1/dashboard/summary` is called, then response has 4 stats, `pTitle: "Recent extractions"` with 4 rows, `sideTop: "Active model"` with eval F1/precision/recall/loss and top extracted fields | `tests/test_dashboard_summary_roles.py::test_business_user_summary_returns_extraction_data` | - [ ] |
| 7 | dashboard-summary-endpoint | Dashboard Summary Endpoint | unavailable training service returns null values | Given the training service returns 5xx/times out, when GET `/api/v1/dashboard/summary` is called by `tenant_admin`, then training-dependent stat values are `null`, `sources.training` is `false`, and HTTP status is 200 | `tests/test_dashboard_summary_roles.py::test_unavailable_training_service_returns_null_values` | - [ ] |
| 8 | dashboard-summary-endpoint | Dashboard Summary Endpoint | unauthenticated request rejected | Given no valid JWT, when GET `/api/v1/dashboard/summary` is called, then response is `401 Unauthorized` | `tests/test_dashboard_summary_roles.py::test_unauthenticated_request_rejected` | - [ ] |
| 9 | portal-dashboard | Dashboard Data Shape | system_admin data shape | Given user role `system_admin`, when GET `/api/v1/dashboard/summary` is called, then response has `kicker: "Platform control plane"`, 4 stats, `pTitle: "Approval queue"` with 4 rows, side panel "Platform health" with SLA/latency/error/GPU, and `sideRows` with storage-by-tenant | `tests/test_dashboard_summary_roles.py::test_system_admin_summary_returns_role_specific_data` | - [ ] |
| 10 | portal-dashboard | Dashboard Data Shape | tenant_admin data shape | Given user role `tenant_admin`, when GET `/api/v1/dashboard/summary` is called, then response has 4 pipeline stats, `pTitle: "Pipeline activity"` with 4 rows, side panel "Active model" with eval F1/precision/recall/loss and quota rows | `tests/test_dashboard_summary_roles.py::test_tenant_admin_summary_returns_pipeline_data` | - [ ] |
| 11 | portal-dashboard | Dashboard Data Shape | annotator data shape | Given user role `annotator`, when GET `/api/v1/dashboard/summary` is called, then response has 3 stats (Assigned tasks, Entities Annotated, Completion %), `pTitle: "My tasks"` with 4 rows, side panel "Dataset readiness" with a progress bar reflecting actual percent complete, copy conveying entities still needed, copy conveying 500 unlocks training, doc/type/today metrics, and span-by-entity-type breakdown | `tests/test_dashboard_summary_roles.py::test_annotator_summary_returns_task_data` (updated) + manual screenshot of rendered card | - [ ] (API-level covered; screenshot outstanding) |
| 12 | portal-dashboard | Dashboard Data Shape | business_user data shape | Given user role `business_user`, when GET `/api/v1/dashboard/summary` is called, then response has 4 stats, `pTitle: "Recent extractions"` with 4 rows, side panel "Active model" with eval F1/precision/recall/loss and top extracted fields | `tests/test_dashboard_summary_roles.py::test_business_user_summary_returns_extraction_data` | - [ ] |
| 13 | portal-dashboard | Dashboard Data Shape | partial service failure degrades gracefully | Given the training service is unavailable, when the dashboard renders, then dependent stat cards show `—`, other cards show real values, and no full-page error screen appears | `src/portal/src/components/dashboard/MetricsPanel.test.tsx` / `StatCard.test.tsx` (existing, unchanged) | - [ ] |
| 14 | portal-dashboard | Dashboard Summary Endpoint | system_admin summary returns real data from wired sources | Given caller role `system_admin`, when GET `/api/v1/dashboard/summary` is called, then `stats[0].value` is the real tenant count, `sources.tenants` is `true`, training-dependent fields are fetched from the training service | `tests/test_dashboard_summary_roles.py::test_system_admin_summary_returns_role_specific_data` | - [ ] |
| 15 | portal-dashboard | Dashboard Summary Endpoint | tenant_admin summary returns real data from wired sources | Given caller role `tenant_admin` with documents/annotations/model versions/training jobs, when GET `/api/v1/dashboard/summary` is called, then `stats[0..3].value` reflect real document count, annotation completion %, promoted model F1, training job count | `tests/test_dashboard_summary_roles.py::test_tenant_admin_summary_returns_pipeline_data` | - [ ] |
| 16 | portal-dashboard | Dashboard Summary Endpoint | annotator summary returns real task data and a live progress bar | Given caller role `annotator` with assigned tasks, when GET `/api/v1/dashboard/summary` is called, then `stats[0].value` is assigned task count, `stats[1].value` is annotated-entity count under label "Entities Annotated", `stats[2].value` is completion %, and `bar` reflects actual percent of the 500-entity threshold reached (not `0`) | `tests/test_dashboard_summary_roles.py::test_annotator_dataset_readiness_shows_progress` + `::test_annotator_dataset_readiness_at_threshold` (new) | - [x] |
| 17 | portal-dashboard | Dashboard Summary Endpoint | business_user summary returns real extraction data | Given caller role `business_user` with extraction data, when GET `/api/v1/dashboard/summary` is called, then `stats[0..3].value` reflect extracted doc count, entity count, avg confidence, auto-cleared % | `tests/test_dashboard_summary_roles.py::test_business_user_summary_returns_extraction_data` | - [ ] |
| 18 | portal-dashboard | Dashboard Summary Endpoint | sources map includes all data domains | Given the dashboard summary is generated for any role, when the response is inspected, then `sources` contains keys for all relevant data domains, each `true`/`false` per query outcome | `tests/test_dashboard_summary.py` (existing, unchanged) | - [ ] |
| 19 | portal-dashboard | Dashboard Summary Endpoint | unauthenticated request rejected | Given no valid JWT, when GET `/api/v1/dashboard/summary` is called, then response is `401 Unauthorized` | `tests/test_dashboard_summary_roles.py::test_unauthenticated_request_rejected` | - [ ] |

> **Rule:** Every `#### Scenario:` block in every `specs/**/*.md` file for this change MUST appear as a row in this table. A missing scenario is a P1 gap that blocks archive.

---

## 2. Hallucination Risk Register

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|--------------------|-----------------------|
| 1 | `bar_pct` wiring in `_annotator_side_panel` | AI may compute `bar_pct` correctly but forget to thread it through both the function's return tuple and the `_annotator_data` call site, leaving `bar` hardcoded at `0` as it is today | Read the diff for `_annotator_side_panel`'s return statement and `_annotator_data`'s `DashboardData(...)` construction; confirm `bar=bar_pct` (or equivalent) is passed, not a literal `0` |
| 2 | Reworded `sideMeta`/`sideBot`/`big`/`bigUnit` copy | AI may introduce a new field on `DashboardData` (e.g. `progressLabel`) instead of reusing existing fields, silently breaking the shared-component contract with other roles per design.md Decision 1 | Diff `src/gateway/api/v1/schemas`/`DashboardData` model — confirm no new fields were added; confirm only annotator-role string values changed |
| 3 | Threshold-met copy branch | AI may implement the "387 more needed" copy but omit the ≥500 branch (scenario 5 / row 5), leaving stale "X more needed" text (or a negative number) once the threshold is reached | Manually test with a tenant schema seeded to exactly 500 and >500 `spans` rows; confirm `sideMeta` no longer reads "more entities needed" and `bar` clamps at `100` |
| 4 | Stat count mismatch (3 vs. 4) | The pre-existing `portal-dashboard` spec text described 4 annotator stats including a "Suggestions" stat that doesn't exist in the current `_annotator_data` implementation (only 3: Assigned tasks, Spans confirmed, Completion); AI could either "restore" a nonexistent Suggestions stat or leave the stale count uncorrected | Confirm `_annotator_data`'s `stats` list has exactly 3 entries matching row 11/16, and that no unrelated "Suggestions" stat was added |
| 5 | Frontend component changes | AI may add annotator-specific conditional rendering to `MetricsPanel.tsx` (a shared, role-agnostic component) instead of keeping the change entirely in backend copy, violating design.md's "no shared-component changes" goal | Diff `src/portal/src/components/dashboard/MetricsPanel.tsx` and `StatCard.tsx` — confirm zero changes; all differences should be confined to `src/gateway/api/v1/dashboard.py` |
| 6 | Rounding/precision of remaining-entity and percent-complete copy | AI may compute "entities remaining" or percent-complete with off-by-one or inconsistent rounding vs. the `bar` percentage, producing copy that doesn't match the visual bar fill (e.g. "23% complete" next to a bar clearly showing 22%) | Cross-check the numeric value embedded in `sideMeta`/`big` copy against `bar` for the same response — they must derive from the same `total_spans`/500 computation |

---

## 3. Pattern & ADR Compliance

| ADR | Decision Summary | Constraint on This Change | Verification Step |
|-----|-------------------|-----------------------------|--------------------|
| None | design.md identifies no in-force ADR governing dashboard copy or this data shape | N/A | N/A |

> No constraining ADRs.

---

## 4. Evidence Requirements

### Functional Evidence

- [ ] Scenario 3 & 11 & 16 (annotator stats/label): API response or test output showing `stats[1].label == "Entities Annotated"` for role `annotator`
- [ ] Scenario 4 (readiness reflects progress): test/log output for a tenant with 113 `spans` rows showing `bar == 22.6`, `sideMeta` containing "387" and "more"/"needed" wording, `sideBot` referencing the 500-entity threshold
- [ ] Scenario 5 (threshold met): test/log output for a tenant with ≥500 `spans` rows showing `bar == 100` and threshold-met copy (no "more needed" phrasing)
- [ ] Scenarios 1, 2, 6, 9, 10, 12, 13, 14, 15, 17, 18 (unchanged roles/behaviour): regression test output or manual check confirming system_admin, tenant_admin, and business_user dashboards are byte-for-byte unchanged in stats/copy
- [ ] Scenarios 7, 8, 19 (auth/error handling, unchanged): existing test suite run showing these pass (no regression from this change)
- [ ] Screenshot of the rendered annotator Dataset Readiness card showing the progress bar visibly filled (not 0%) and the new copy

### Structural Evidence

- [ ] Code review completed — implementation matches design.md decisions (no undocumented deviations)
- [ ] All ADR compliance steps in Section 3 confirmed ✓ (N/A — no constraining ADRs)
- [ ] No undocumented architectural patterns introduced
- [ ] No AI-invented requirements present in generated code (cross-checked against spec files)

### Edge Case Evidence

- [ ] Risk 1 mitigation confirmed — diff review shows `bar_pct` (or equivalent) threaded from `_annotator_side_panel` into `DashboardData.bar`
- [ ] Risk 2 mitigation confirmed — `DashboardData`/`StatItem` model diff shows no new fields added
- [ ] Risk 3 mitigation confirmed — manual test at exactly 500 and >500 `spans` rows shows correct threshold-met copy and `bar` clamped at 100
- [ ] Risk 4 mitigation confirmed — `_annotator_data` stats list has exactly 3 entries, no "Suggestions" stat introduced
- [ ] Risk 5 mitigation confirmed — `MetricsPanel.tsx`/`StatCard.tsx` diffs are empty
- [ ] Risk 6 mitigation confirmed — remaining-count/percent-complete copy and `bar` value cross-checked as derived from the same underlying count for a sample response

---

## 5. Evidence Log

| # | Evidence Type | Description / Link | Scenario(s) Covered | Collected By | Date |
|---|---------------|----------------------|------------------------|-----------------|------|
| 1 | Functional | `poetry run pytest tests/test_dashboard_summary_roles.py::TestDashboardSummaryRoles::test_annotator_summary_returns_task_data -q` → 1 passed | Scenario 3 / 11 | agent (session) | 2026-08-05 |
| 2 | Functional | `poetry run pytest tests/test_dashboard_summary_roles.py::TestDashboardSummaryRoles::test_annotator_dataset_readiness_shows_progress -q` → 1 passed (`bar == 22.6`, `sideMeta`/`sideBot` copy asserted) | Scenario 4 / 16 | agent (session) | 2026-08-05 |
| 3 | Functional | `poetry run pytest tests/test_dashboard_summary_roles.py::TestDashboardSummaryRoles::test_annotator_dataset_readiness_at_threshold -q` → 1 passed (`bar == 100`, threshold-met copy asserted) | Scenario 5 / 16 | agent (session) | 2026-08-05 |
| 4 | | (Scenarios 1, 2, 6-10, 12-15, 17-19 — not run cleanly this session; see tasks.md § 4/5 blocker note) | | | |

---

## 6. Audit Record

> ⚠️ **GATE: This section must be completed and signed by a human reviewer before `/opsx:archive` is run.** An unsigned or incomplete Audit Record is a hard block on archive.

**Change slug:** annotator-dashboard-ux-refinements
**Proposal:** `openspec/changes/annotator-dashboard-ux-refinements/proposal.md`
**Spec files reviewed:**
- specs/dashboard-summary-endpoint/spec.md
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
