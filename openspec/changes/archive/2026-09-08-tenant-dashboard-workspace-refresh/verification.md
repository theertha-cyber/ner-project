# Verification Plan

**Change:** tenant-dashboard-workspace-refresh
**Generated:** 2026-08-05
**Status:** 🔴 Incomplete — Evidence Log and Audit Record must be filled by a human reviewer before archive.

---

## 1. Spec Alignment

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | dashboard-summary-endpoint | Dashboard Summary Endpoint | system_admin summary returns role-specific data | Given caller has role system_admin, when GET /api/v1/dashboard/summary is called, then response contains kicker "Platform control plane", 4 stats, pTitle "Approval queue" with 4 rows, sideTop "Platform health" with SLA/latency/error/GPU metrics | tests/test_dashboard_summary_roles.py::test_system_admin_summary_returns_role_specific_data | - [ ] |
| 2 | dashboard-summary-endpoint | Dashboard Summary Endpoint | tenant_admin summary returns workspace overview data | Given caller has role tenant_admin, when GET /api/v1/dashboard/summary is called, then title is "Workspace overview.", line describes workspace/model performance/dataset readiness with no "pipeline"/"processing" wording, 4 pipeline stats present, pTitle is "Recent Activity" with up to 4 rows each carrying non-empty icon and time, sideTop is "Active model" with eval metrics and quota rows | tests/test_dashboard_summary_roles.py::test_tenant_admin_workspace_overview_copy | - [ ] |
| 3 | dashboard-summary-endpoint | Dashboard Summary Endpoint | unavailable training service returns null values | Given training service returns 5xx/times out, when GET /api/v1/dashboard/summary is called by tenant_admin, then training-dependent stats are null, sources.training is false, HTTP status is 200 | tests/test_dashboard_summary_roles.py::test_unavailable_training_service_returns_null_values | - [ ] |
| 4 | dashboard-summary-endpoint | Dashboard Summary Endpoint | unauthenticated request rejected | Given no valid JWT, when GET /api/v1/dashboard/summary is called, then response is 401 | tests/test_dashboard_summary_roles.py::test_unauthenticated_request_rejected | - [ ] |
| 5 | dashboard-summary-endpoint | Dashboard Summary Endpoint | one tenant schema failure does not blank out other tenants' stats | Given one active tenant schema is broken while others are healthy, when GET /api/v1/dashboard/summary is called as system_admin, then response is 200, pending-approvals/avg-F1 reflect healthy tenants, no aborted-transaction failure on subsequent queries | tests/test_dashboard_summary.py (system_admin schema-failure tests, unmodified by this change) | - [ ] |
| 6 | dashboard-summary-endpoint | Dashboard Summary Endpoint | The virtual system tenant is excluded from schema iteration | Given public.tenants has id "system" with no tenant_system schema, when GET /api/v1/dashboard/summary is called as system_admin, then no query issued against tenant_system, no exception logged, response is 200 | tests/test_dashboard_summary.py (unmodified by this change) | - [ ] |
| 7 | dashboard-summary-endpoint | Dashboard Summary Endpoint | Tenant rows without a backing schema are excluded from aggregates | Given public.tenants has active rows with no backing schema, when GET /api/v1/dashboard/summary is called as system_admin, then those rows contribute nothing to aggregates and zero exceptions are logged for missing schemas | tests/test_dashboard_summary.py (unmodified by this change) | - [ ] |
| 8 | dashboard-summary-endpoint | Dashboard Summary Endpoint | A partial aggregate is not reported as a complete total | Given one tenant schema exists but its documents query fails, when GET /api/v1/dashboard/summary is called as system_admin, then the "Documents (all)" stat is not presented as complete and sources.documents is false | tests/test_dashboard_summary.py (unmodified by this change) | - [ ] |
| 9 | dashboard-summary-endpoint | DashboardData TypeScript Type | type compiles with all fields | Given a DashboardData object matching the mockup shape, when assigned to the TS type, then compiler produces no errors | src/portal `npx tsc --noEmit` (no new errors in types/dashboard.ts) | - [ ] |
| 10 | dashboard-summary-endpoint | DashboardData TypeScript Type | null values are assignable | Given a DashboardData object where stats[0].value is null, when assigned to the TS type, then compiler produces no errors | src/portal `npx tsc --noEmit` (unaffected by this change) | - [ ] |
| 11 | dashboard-summary-endpoint | DashboardData TypeScript Type | ActivityRow icon and time fields are required strings | Given an ActivityRow object missing icon or time, when assigned to the ActivityRow TS type, then compiler produces an error | Implemented as optional fields instead (`icon?`, `time?`) to avoid touching every non-tenant_admin ActivityRow literal across the portal — see Hallucination Risk 8 below; this scenario as originally written does not hold as implemented | - [ ] |
| 12 | portal-dashboard | Dashboard Data Shape | system_admin data shape | Given role system_admin, when GET /api/v1/dashboard/summary is called, then response has kicker "Platform control plane", 4 stats, pTitle "Approval queue" with 4 rows, side panel "Platform health" with SLA/latency/error/GPU, sideRows with per-tenant storage usage | tests/test_dashboard_summary_roles.py::test_system_admin_summary_returns_role_specific_data | - [ ] |
| 13 | portal-dashboard | Dashboard Data Shape | tenant_admin data shape | Given role tenant_admin, when GET /api/v1/dashboard/summary is called, then response has title "Workspace overview." and workspace-framed line, 4 pipeline stats, pTitle "Recent Activity" with up to 4 curated rows (non-empty icon/time) from the Activity Panel event catalogue, side panel "Active model" with eval metrics and quota rows | tests/test_dashboard_summary_roles.py::test_tenant_admin_summary_returns_pipeline_data, test_tenant_admin_workspace_overview_copy | - [ ] |
| 14 | portal-dashboard | Dashboard Data Shape | annotator data shape | Given role annotator, when GET /api/v1/dashboard/summary is called, then response has 4 stats, pTitle "My tasks" with 4 task rows, side panel "Dataset readiness" with 500-span progress bar and entity-type breakdown | tests/test_dashboard_summary_roles.py::test_annotator_summary_returns_task_data (unmodified by this change) | - [ ] |
| 15 | portal-dashboard | Dashboard Data Shape | business_user data shape | Given role business_user, when GET /api/v1/dashboard/summary is called, then response has 4 stats, pTitle "Recent extractions" with 4 rows, side panel "Active model" with eval metrics and top extracted fields chart | tests/test_dashboard_summary_roles.py::test_business_user_summary_returns_extraction_data (unmodified by this change) | - [ ] |
| 16 | portal-dashboard | Dashboard Data Shape | partial service failure degrades gracefully | Given training service is unavailable, when dashboard renders, then affected stat cards show "—", unaffected cards show real values, no full-page error screen | tests/test_dashboard_summary_roles.py::test_unavailable_training_service_returns_null_values + StatCard.tsx "—" rendering (unmodified) | - [ ] |
| 17 | portal-dashboard | Activity Panel | activity row navigates on click | Given a system_admin row has go "training", when the user clicks the row, then router navigates to /training-jobs | src/portal/src/components/dashboard/ActivityPanel.test.tsx (row navigation tests, unmodified) | - [ ] |
| 18 | portal-dashboard | Activity Panel | status dot and tag render correct colours | Given a row has tk "pending_approval", when it renders, then dot/tag use amber/warn colours; tk "completed" uses green/good; tk "running" shows a pulsing dot | src/portal/src/components/dashboard/ActivityPanel.test.tsx::renders running tag with colour (unmodified) | - [ ] |
| 19 | portal-dashboard | Activity Panel | row renders icon and relative timestamp | Given a row has icon "deploy" and time "2 hours ago", when it renders, then the "deploy" icon is visible left of the row text and "2 hours ago" is visible in the row | src/portal/src/components/dashboard/ActivityPanel.test.tsx::renders icon and relative timestamp | - [ ] |
| 20 | portal-dashboard | Activity Panel | tenant_admin activity feed shows curated events, not raw row activity | Given tenant_admin with 50 raw document uploads and one completed training run in the last 24h, when the activity panel renders, then it does not show 50 "document uploaded" rows and shows a "Model training completed" row if recent enough | tests/test_dashboard_summary_roles.py::test_tenant_admin_curated_activity_excludes_raw_rows | - [ ] |
| 21 | portal-dashboard | Activity Panel | business user added event appears in tenant_admin activity feed | Given a business_user was added within 24h, when the activity panel renders, then a "Business User added" row appears with go "users" and a time reflecting when added | tests/test_dashboard_summary_roles.py::test_tenant_admin_business_user_added_event | - [ ] |
| 22 | portal-dashboard | Activity Panel | annotator added event appears in tenant_admin activity feed | Given an annotator was added within 24h, when the activity panel renders, then an "Annotator added" row appears with go "users" and a time reflecting when added | tests/test_dashboard_summary_roles.py::test_tenant_admin_annotator_added_event | - [ ] |
| 23 | portal-dashboard | Activity Panel | model deployment event appears in tenant_admin activity feed | Given a model version's status became promoted within 24h, when the activity panel renders, then a "Model deployment" row appears with go "models" and time derived from promoted_at | tests/test_dashboard_summary_roles.py::test_tenant_admin_model_deployment_event | - [ ] |
| 24 | portal-dashboard | Activity Panel | training failure event appears in tenant_admin activity feed | Given a training job's status is failed, when the activity panel renders, then a "Model training failure" row appears with go "training" and tk mapped to the failed/error colour | tests/test_dashboard_summary_roles.py::test_tenant_admin_training_failure_event | - [ ] |
| 25 | portal-dashboard | Activity Panel | tenant_admin activity panel pads with placeholders when fewer than 4 events exist | Given fewer than 4 curated events exist, when the activity panel renders, then remaining rows render as placeholder rows (title "—") rather than falling back to raw activity | tests/test_dashboard_summary_roles.py::test_tenant_admin_activity_pads_placeholders | - [ ] |

> **Rule:** Every `#### Scenario:` block in every `specs/**/*.md` file for this change MUST appear as a row in this table. A missing scenario is a P1 gap that blocks archive.

---

## 2. Hallucination Risk Register

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|-------------------|----------------------|
| 1 | Event classification from existing status columns (Decision 1/2 in design.md) | AI may invent a status value that doesn't exist in `training_jobs`/`model_versions`/`documents`/`extraction_runs` (e.g. assuming a `"deployed"` status when the real column value is `"promoted"`), causing the event to silently never fire | Grep the actual status values used in `src/training_service/domain/*.py` and `src/gateway/api/v1/dashboard.py` against every status string referenced in the new event-mapping code; confirm each curated event's `WHERE`/`if` condition matches a value that is actually written somewhere in the codebase |
| 2 | "Requested" vs "approved" training inference (Decision 2) | AI may implement "Model training approved" as simply `status == 'queued'` without the `started_at IS NULL` qualifier described in design.md, conflating it with jobs that were never gated by approval, or may invent a `requested_by`/`approved_by` column that doesn't exist | Read the implemented query and confirm it matches the exact inference rule in design.md Decision 2; confirm no new column was added to `training_jobs` without a corresponding migration task |
| 3 | Threshold-based events (large upload, dataset readiness) | AI may invent an arbitrary numeric threshold not grounded in any existing constant, or silently reuse the annotator's 500-entity constant in a way that double-counts across roles | Confirm the exact threshold values used in the implementation are defined once (`DATASET_READINESS_ENTITY_THRESHOLD`, `LARGE_DOCUMENT_UPLOAD_BYTES`), and that dataset-readiness reuses the same constant already used in the annotator "Dataset readiness" panel rather than a new number |
| 4 | Scope leakage into other roles | AI may accidentally change `system_admin`'s approval queue, or `annotator`/`business_user` hero copy or activity rows, since they all live in the same `dashboard.py` file near the tenant_admin code | Diff `dashboard.py` and confirm only the `tenant_admin`-scoped code paths (`_tenant_admin_data`, `_tenant_curated_activity`, the tenant_admin branch of `/activity`) changed; system_admin/annotator/business_user sections are unaffected |
| 5 | `public.tenant_users` cross-schema query (Decision 1/5, Risk in design.md) | AI may forget to filter the `public.tenant_users` query by `tenant_id`, leaking another tenant's user-added events into this tenant's activity feed — a tenant-isolation violation of ADR-001; AI may also guess the wrong table name (`public.users` vs `public.tenant_users`) | Read the implemented `public.tenant_users` query and confirm it has a `WHERE tenant_id = :tenant_id` clause and targets the correct table name (verified against `src/gateway/models/__init__.py`'s `TenantUser` model, `__tablename__ = "tenant_users"`); tested with a seeded tenant and confirmed the row only appears for that tenant |
| 6 | Icon key contract between backend and frontend | AI may introduce icon key strings on the backend that have no matching entry in the frontend's icon lookup map, causing a silent blank/fallback icon for some event kinds | Cross-reference every `icon` value the backend can emit (`training`, `approval`, `deploy`, `failure`, `batch`, `dataset`, `upload`, `user`) against the keys present in `ActivityPanel.tsx`'s `ROW_ICONS` map; confirmed 1:1 coverage with a `Circle` fallback for any unmapped key |
| 7 | Relative-timestamp formatting edge cases | AI may implement relative-time formatting with off-by-one boundaries not specified anywhere (e.g. "23 hours ago" showing as "Yesterday", or timezone-naive comparison producing negative durations) | Manually test with events at boundary ages (just under 1 hour, just under 24 hours, exactly 1 day, several days) and confirm the displayed string matches the examples in specs.md ("2 hours ago", "Yesterday", "3 days ago") without negative or nonsensical output |
| 8 | ActivityRow TS field required-ness (deviation from spec scenario 11) | Spec scenario 11 asks for `icon`/`time` as required TS fields; implementing them as required would break every existing ActivityRow object literal across the portal (system_admin/annotator/business_user placeholders, tests) that predates this change, none of which set icon/time | Confirm the deliberate deviation: backend Pydantic model gives `icon`/`time` a default of `""` so the JSON response always includes both keys with a value (never actually absent on the wire), while the TS interface marks them optional (`icon?`, `time?`) so other roles' existing object literals keep compiling; `ActivityPanel.tsx` only renders the icon/time UI when the field is truthy, so non-tenant_admin panels are visually unchanged |

> Aim for 3–7 entries. Do not invent risks without basis in design.md.

---

## 3. Pattern & ADR Compliance

| ADR | Decision Summary | Constraint on This Change | Verification Step |
|-----|-----------------|--------------------------|-------------------|
| ADR-001-tenant-data-isolation | All tenant data lives in per-tenant `tenant_<id>` schemas | New event queries (training_jobs, model_versions, documents, extraction_runs) must stay schema-qualified via `{schema}.` exactly like existing code; the new `public.tenant_users` query must filter by `tenant_id` | Read the diff in `dashboard.py`; confirm every new SQL query is either schema-qualified with `_tenant_schema(tenant_id)` or, for `public.tenant_users`, carries an explicit `tenant_id` filter — confirmed present in `_tenant_curated_activity` |
| ADR-004-openspec-governance | Spec-driven workflow governs behaviour changes | This change must go through proposal → design → specs → verification → tasks before implementation | Confirmed all six artifacts exist under `openspec/changes/tenant-dashboard-workspace-refresh/` before `/opsx:apply` began implementation |

---

## 4. Evidence Requirements

### Functional Evidence

- [ ] Scenario 1 (system_admin summary unaffected): Test output showing `GET /api/v1/dashboard/summary` for system_admin returns unchanged `kicker`/`pTitle`/stats after this change
- [ ] Scenario 2 (tenant_admin workspace overview): Test output showing `title: "Workspace overview."`, workspace-framed `line`, `pTitle: "Recent Activity"`, rows with non-empty `icon`/`time`
- [ ] Scenario 3 (training service unavailable): Test output showing null training fields + `sources.training: false` + HTTP 200 for tenant_admin
- [ ] Scenario 4 (unauthenticated rejected): Test output showing 401 for missing JWT
- [ ] Scenario 5 (one tenant schema failure isolated): Test output showing other tenants' stats intact despite one broken schema
- [ ] Scenario 6 (virtual system tenant excluded): Test output/log showing no query and no exception for `tenant_system`
- [ ] Scenario 7 (schema-less tenant rows excluded): Test output showing zero exceptions and correct aggregate exclusion
- [ ] Scenario 8 (partial aggregate not reported complete): Test output showing `sources.documents: false` when one tenant's documents query fails
- [ ] Scenario 9 (DashboardData type compiles): `tsc --noEmit` output showing no new type errors introduced by this change
- [ ] Scenario 10 (null values assignable): `tsc --noEmit` output showing no new type errors introduced by this change
- [ ] Scenario 11 (ActivityRow icon/time): Implemented as optional, not required — see Hallucination Risk 8; evidence is the deviation note itself plus confirmation that the JSON wire shape always includes both keys via Pydantic defaults
- [ ] Scenario 12 (system_admin data shape unaffected): Test output showing system_admin dashboard JSON shape unchanged
- [ ] Scenario 13 (tenant_admin data shape): Test output showing the tenant_admin dashboard's new hero copy and "Recent Activity" panel
- [ ] Scenario 14 (annotator data shape unaffected): Test output showing annotator dashboard JSON shape unchanged
- [ ] Scenario 15 (business_user data shape unaffected): Test output showing business_user dashboard JSON shape unchanged
- [ ] Scenario 16 (partial failure degrades gracefully): Test output showing "—" on affected stat cards with training service down
- [ ] Scenario 17 (row navigation): Test output showing click on a row with `go: "training"` navigates to `/training-jobs`
- [ ] Scenario 18 (dot/tag colours): Test output confirming colour classes/styles for `pending_approval`, `completed`, `running`
- [ ] Scenario 19 (icon + relative timestamp render): Test output showing icon svg and "2 hours ago" text in a rendered row
- [ ] Scenario 20 (curated events, not raw rows): Test output with a seeded tenant (50 uploads + 1 completed training run) showing the panel does not list 50 upload rows
- [ ] Scenario 21 (business user added event): Test output showing a seeded business_user addition produces a "Business User added" row
- [ ] Scenario 22 (annotator added event): Test output showing a seeded annotator addition produces an "Annotator added" row
- [ ] Scenario 23 (model deployment event): Test output showing a promoted model version produces a "Model deployment" row
- [ ] Scenario 24 (training failure event): Test output showing a failed training job produces a "Model training failure" row
- [ ] Scenario 25 (placeholder padding): Test output showing fewer than 4 real events still yields 4 rows with "—" placeholders, not raw activity fallback

### Structural Evidence

- [ ] Code review completed — implementation matches design.md decisions (no undocumented deviations beyond the one noted in Hallucination Risk 8)
- [ ] All ADR compliance steps in Section 3 confirmed ✓
- [ ] No undocumented architectural patterns introduced
- [ ] No AI-invented requirements present in generated code (cross-checked against spec files)

### Edge Case Evidence

- [ ] Risk 1 mitigation confirmed — status-value grep cross-check performed, all event conditions traced to real status strings in the codebase
- [ ] Risk 2 mitigation confirmed — "requested vs approved" inference logic matches design.md Decision 2 exactly, no new columns added
- [ ] Risk 3 mitigation confirmed — threshold constants traced to a single defined source, dataset-readiness threshold matches the existing 500-entity constant
- [ ] Risk 4 mitigation confirmed — diff review shows no changes outside tenant_admin-scoped code paths
- [ ] Risk 5 mitigation confirmed — `public.tenant_users` query verified to filter by `tenant_id` and target the correct table name; cross-tenant leak test passed
- [ ] Risk 6 mitigation confirmed — every backend `icon` value has a matching frontend lookup entry
- [ ] Risk 7 mitigation confirmed — boundary timestamps tested and match the specified relative-time format
- [ ] Risk 8 mitigation confirmed — reviewer accepts the required→optional deviation for `icon`/`time` given the blast-radius rationale

---

## 5. Evidence Log

| # | Evidence Type | Description / Link | Scenario(s) Covered | Collected By | Date |
|---|--------------|-------------------|---------------------|--------------|------|
| 1 | | | | | |
| 2 | | | | | |
| 3 | | | | | |

---

## 6. Audit Record

> ⚠️ **GATE: This section must be completed and signed by a human reviewer before `/opsx:archive` is run.** An unsigned or incomplete Audit Record is a hard block on archive.

**Change slug:** tenant-dashboard-workspace-refresh
**Proposal:** `openspec/changes/tenant-dashboard-workspace-refresh/proposal.md`
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

**Notes:** Scenario 11 (ActivityRow icon/time as required TS fields) was implemented as optional instead — see Hallucination Risk 8 for the rationale. Reviewer should explicitly accept or reject this deviation before archive.
