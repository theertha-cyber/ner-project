# Verification Plan

**Change:** redesign-system-admin-dashboard
**Generated:** 2026-08-06 (revised after stakeholder review)
**Status:** 🔴 Incomplete — Evidence Log and Audit Record must be filled by a human reviewer before archive.

---

## 1. Spec Alignment

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | dashboard-summary-endpoint | Dashboard Summary Endpoint | system_admin summary returns role-specific data | Given a caller with role `system_admin`, when `GET /api/v1/dashboard/summary` is called, then `stats` contains exactly Active Tenants, Active Users, Pending Approvals, Training Jobs Running; `pTitle` is "Platform Activity"; `sideTop` is "Platform Health" with a deterministic Healthy/Degraded/Critical status; no field references model F1/precision/recall/loss | `tests/test_dashboard_summary.py` (tasks 2.7, 3.3) | - [ ] |
| 2 | dashboard-summary-endpoint | Dashboard Summary Endpoint | tenant_admin summary returns pipeline data | Given a caller with role `tenant_admin`, when the endpoint is called, then the existing 4 pipeline stats, "Pipeline activity" panel, and "Active model" side panel are unchanged | `tests/test_dashboard_summary_roles.py` (task 3.4) | - [ ] |
| 3 | dashboard-summary-endpoint | Dashboard Summary Endpoint | annotator summary returns task data | Given a caller with role `annotator`, when the endpoint is called, then the existing 4 task stats, "My tasks" panel, and "Dataset readiness" side panel are unchanged | `tests/test_dashboard_summary_roles.py` (task 3.4) | - [ ] |
| 4 | dashboard-summary-endpoint | Dashboard Summary Endpoint | business_user summary returns extraction data | Given a caller with role `business_user`, when the endpoint is called, then the existing 4 extraction stats, "Recent extractions" panel, and "Active model" side panel are unchanged | `tests/test_dashboard_summary_roles.py` (task 3.4) | - [ ] |
| 5 | dashboard-summary-endpoint | Dashboard Summary Endpoint | unavailable training service returns null values | Given the training service errors/times out, when a `tenant_admin` calls the endpoint, then training-dependent stats are `null`, `sources.training` is `false`, and HTTP status is 200 | `tests/test_dashboard_summary.py` (task 4.6) | - [ ] |
| 6 | dashboard-summary-endpoint | Dashboard Summary Endpoint | unauthenticated request rejected | Given no valid JWT, when the endpoint is called, then the response is 401 | `tests/test_dashboard_summary.py` (task 4.6) | - [ ] |
| 7 | dashboard-summary-endpoint | Dashboard Summary Endpoint | one tenant schema failure does not blank out other tenants' stats | Given one active tenant's schema is broken while others are healthy, when a `system_admin` calls the endpoint, then response is 200 and Pending Approvals/Training Jobs Running reflect the healthy tenants, and no aborted-transaction error blocks subsequent queries | `tests/test_dashboard_summary.py` (task 4.2) | - [ ] |
| 8 | dashboard-summary-endpoint | Dashboard Summary Endpoint | The virtual system tenant is excluded from schema iteration | Given `public.tenants` has row `id='system'` with no `tenant_system` schema, when a `system_admin` calls the endpoint, then no query is issued against `tenant_system`, no exception is logged, and response is 200 | `tests/test_dashboard_summary.py` (task 4.3) | - [ ] |
| 9 | dashboard-summary-endpoint | Dashboard Summary Endpoint | Tenant rows without a backing schema are excluded from aggregates | Given `public.tenants` has active rows with no corresponding schema, when a `system_admin` calls the endpoint, then those rows contribute nothing to pending-approval or Training Jobs Running counts, and zero exceptions are logged for them | `tests/test_dashboard_summary.py` (task 4.4) | - [ ] |
| 10 | dashboard-summary-endpoint | Dashboard Summary Endpoint | A partial aggregate is not reported as a complete total | Given one tenant schema's `training_jobs` query fails, when a `system_admin` calls the endpoint, then "Training Jobs Running" is not presented as complete and `sources.training` is `false` | `tests/test_dashboard_summary.py` (task 4.5) | - [ ] |
| 11 | dashboard-summary-endpoint | Dashboard Summary Endpoint | Platform Activity is a generic feed of recent audit events, not a fixed list of event types | Given `public.audit_events` has rows across multiple tenants including an `action` with no special-cased title, when a `system_admin` calls the endpoint, then `pRows` contains the most recent rows ordered by `created_at` regardless of `action`/`kind`, known actions show a friendly title, unmapped actions show a humanized fallback (never omitted), and rows from more than one tenant appear when applicable | `tests/test_dashboard_summary.py` (tasks 1.4, 1.5) | - [ ] |
| 12 | dashboard-summary-endpoint | Dashboard Summary Endpoint | Platform Health status is a deterministic function of per-service reachability | Given a caller with role `system_admin`, when the endpoint is called, then the overall status is computed solely from Gateway/Chat API/Extraction Service/Training Service/Model Serving reachability via the fixed Healthy/Degraded/Critical rules — never manually assigned | `tests/test_dashboard_summary.py` (task 2.8) | - [ ] |
| 13 | dashboard-summary-endpoint | Dashboard Summary Endpoint | An unreachable non-critical service degrades status without failing the request | Given Training Service's `/health` is unreachable while the other 4 respond 200, when a `system_admin` calls the endpoint, then Training Service reports "Offline", the other 4 report "Online", `big` is "Degraded", and the response is 200 within a bounded time | `tests/test_dashboard_summary.py` (task 2.9) | - [ ] |
| 14 | dashboard-summary-endpoint | Dashboard Summary Endpoint | An unreachable critical service reports Critical status | Given Model Serving's `/health` is unreachable while Gateway, Chat API, Extraction Service, and Training Service respond 200, when a `system_admin` calls the endpoint, then `big` is "Critical" (not "Degraded"), and the response is still 200 | `tests/test_dashboard_summary.py` (task 2.8) | - [ ] |
| 15 | dashboard-summary-endpoint | Dashboard Summary Endpoint | Active Users count reflects tenant_users status | Given `public.tenant_users` has a mix of active/non-active rows, when a `system_admin` calls the endpoint, then "Active Users" equals the count of `status='active'` rows, not the total row count | `tests/test_dashboard_summary.py` (task 2.7) | - [ ] |
| 16 | portal-dashboard | Dashboard Data Shape | system_admin data shape | Given role `system_admin`, when the endpoint is called, then `kicker`/`title`/`line` reference platform operations/tenant management/approvals, `stats` are Active Tenants/Active Users/Pending Approvals/Training Jobs Running, `pTitle` is "Platform Activity" (generic recent-events feed), side panel is "Platform Health" with a deterministic status and per-service status, and no SLA/p95/GPU metrics | `tests/test_dashboard_summary.py` (task 3.3) | - [ ] |
| 17 | portal-dashboard | Dashboard Data Shape | tenant_admin data shape | Given role `tenant_admin`, when the endpoint is called, then the existing pipeline stats/activity rows/"Active model" side panel are unchanged | `tests/test_dashboard_summary_roles.py` (task 3.4) | - [ ] |
| 18 | portal-dashboard | Dashboard Data Shape | annotator data shape | Given role `annotator`, when the endpoint is called, then the existing task stats/rows/"Dataset readiness" side panel are unchanged | `tests/test_dashboard_summary_roles.py` (task 3.4) | - [ ] |
| 19 | portal-dashboard | Dashboard Data Shape | business_user data shape | Given role `business_user`, when the endpoint is called, then the existing extraction stats/rows/"Active model" side panel are unchanged | `tests/test_dashboard_summary_roles.py` (task 3.4) | - [ ] |
| 20 | portal-dashboard | Dashboard Data Shape | partial service failure degrades gracefully | Given the training service is unavailable, when the dashboard renders, then dependent stat cards show `—`, other cards show real values, and no full-page error screen appears | manual dev-server check (task 5.8) | - [ ] |
| 21 | portal-dashboard | Dashboard Summary Endpoint | system_admin summary returns real data from wired sources | Given role `system_admin`, when the endpoint is called, then `stats[0].value` is the real active-tenant count, `sources.tenants` is `true`, Active Users comes from `tenant_users`, Pending Approvals/Training Jobs Running come from tenant schema iteration, Platform Activity comes generically from `audit_events`, and Platform Health reflects live, concurrent `/health` checks with a deterministically derived status | `tests/test_dashboard_summary.py` (task 3.3) | - [ ] |
| 22 | portal-dashboard | Dashboard Summary Endpoint | tenant_admin summary returns real data from wired sources | Given role `tenant_admin` with documents/annotations/models/training data, when the endpoint is called, then `stats[0..3]` reflect the real document count, annotation %, promoted F1, and training job count | `tests/test_dashboard_summary_roles.py` (task 3.4) | - [ ] |
| 23 | portal-dashboard | Dashboard Summary Endpoint | annotator summary returns real task data | Given role `annotator` with assigned tasks, when the endpoint is called, then `stats[0]`, `stats[1]`, `stats[3]` reflect real assigned-task count, confirmed-span count, and completion % | `tests/test_dashboard_summary_roles.py` (task 3.4) | - [ ] |
| 24 | portal-dashboard | Dashboard Summary Endpoint | business_user summary returns real extraction data | Given role `business_user` with extraction data, when the endpoint is called, then `stats[0..3]` reflect real extracted-doc count, entity count, avg confidence, auto-cleared % | `tests/test_dashboard_summary_roles.py` (task 3.4) | - [ ] |
| 25 | portal-dashboard | Dashboard Summary Endpoint | sources map includes all data domains | Given the summary is generated for any role, when the response is inspected, then `sources` contains keys for all data domains relevant to that role, each `true`/`false` per query success | `tests/test_dashboard_summary.py` (task 3.3) | - [ ] |
| 26 | portal-dashboard | Dashboard Summary Endpoint | unauthenticated request rejected | Given no valid JWT, when the endpoint is called, then the response is 401 | `tests/test_dashboard_summary.py` (task 4.6) | - [ ] |
| 27 | portal-dashboard | Activity Panel | activity row navigates on click | Given a `system_admin` activity row with `go: "training"`, when clicked, then the router navigates to `/training-jobs` | `src/portal/src/components/dashboard/ActivityPanel.test.tsx` (task 5.4) | - [ ] |
| 28 | portal-dashboard | Activity Panel | tenant lifecycle activity row navigates to tenant admin console | Given a `system_admin` Platform Activity row for a tenant.create/deactivate event with `go: "tenants"`, when clicked, then the router navigates to `/admin/tenants` | `src/portal/src/hooks/use-dashboard-data.test.ts` (task 5.3) | - [ ] |
| 29 | portal-dashboard | Activity Panel | status dot and tag render correct colours | Given a row with `tk: "pending_approval"`, when it renders, then dot/tag use amber/warn colours; `tk: "completed"` uses green/good; `tk: "running"` shows a pulsing dot | `src/portal/src/components/dashboard/ActivityPanel.test.tsx` (task 5.4) | - [ ] |
| 30 | portal-dashboard | Secondary Metrics Panel | progress bar fills to correct percentage | Given `bar: 62`, when the panel renders, then the bar fills to 62% at 8px height with the growBar animation from 0 to 62% | `src/portal/src/components/dashboard/MetricsPanel.test.tsx` (task 5.7) | - [ ] |
| 31 | portal-dashboard | Secondary Metrics Panel | sideMetrics render as inline row | Given three sideMetrics, when the top section renders, then they appear in a single inline flex row (space-between) each showing `k`/`v` in JetBrains Mono | `src/portal/src/components/dashboard/MetricsPanel.test.tsx` (task 5.7) | - [ ] |
| 32 | portal-dashboard | Secondary Metrics Panel | sideRows mini bars render correct colours | Given `sideRows[0].c` is a specific CSS colour string, when the mini bar renders, then its background matches that colour | `src/portal/src/components/dashboard/MetricsPanel.test.tsx` (task 5.7) | - [ ] |
| 33 | portal-dashboard | Secondary Metrics Panel | system_admin service status renders with status colour | Given role `system_admin` and a `sideMetrics` entry with `v: "Offline"`, when the panel renders, then that value renders in the red/bad status colour, not the default secondary text colour | `src/portal/src/components/dashboard/MetricsPanel.test.tsx` (task 5.5) | - [ ] |
| 34 | portal-dashboard | Secondary Metrics Panel | system_admin overall Platform Health status renders with severity colour | Given role `system_admin`, when `big` is "Critical"/"Degraded"/"Healthy", then it renders red/bad, amber/warn, or green/good respectively | `src/portal/src/components/dashboard/MetricsPanel.test.tsx` (task 5.6) | - [ ] |

> **Rule:** Every `#### Scenario:` block in every `specs/**/*.md` file for this change MUST appear as a row in this table. A missing scenario is a P1 gap that blocks archive.

---

## 2. Hallucination Risk Register

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|---------------------|------------------------|
| 1 | Audit-event → activity-row title mapping and its generic contract (design.md Decision 2) | AI may re-introduce a fixed allowlist of `action` values (silently dropping or filtering out unmapped ones) instead of a generic "most recent, any action" feed with a cosmetic title map, contradicting the stakeholder-mandated genericity requirement | Confirm the query has no `WHERE action IN (...)` or `kind IN (...)` filter; feed an unmapped `action` value through the code path and confirm it produces a humanized fallback row, not an omitted one (task 1.5) |
| 2 | Platform Health tier-priority logic (design.md Decision 4) | AI may check tiers in the wrong order or treat all 5 services as equally weighted, e.g. reporting "Degraded" when Model Serving is down but a non-critical service is up, instead of correctly reporting "Critical" — the Critical check must take priority regardless of the other three services' state | Run a test matrix over all 8 combinations of {Gateway, Model Serving} × {both up, one down, both down} against varying non-critical service states, confirming Critical is reported whenever Gateway or Model Serving is Offline, regardless of the others (task 2.8) |
| 3 | Parallel health-check implementation (design.md Decision 4) | AI may implement the 5 service checks sequentially (defeating the latency bound), forget the gateway self-check special case (issuing a real HTTP call to itself), let one service's exception propagate and fail the whole endpoint, or use a timeout other than 3s | Read the implementation and confirm `asyncio.gather` (or equivalent concurrent construct) is used for the 4 outbound checks, each wrapped so a timeout/exception is caught locally, the gateway status is hard-coded `"Online"` without a network call, and each `httpx` call sets a 3-second timeout (task 2.10) |
| 4 | Fixed-shape `sideMetrics`/`sideRows` reuse (design.md Decision 5) | AI may widen `sideMetrics` from a 3-tuple to a variable-length array to fit all 5 services, breaking the shared `DashboardData` type consumed by `tenant_admin`/`annotator`/`business_user` | Diff `src/portal/src/types/dashboard.ts` — confirm `sideMetrics` is unchanged as `[SideMetric, SideMetric, SideMetric]` and no other role's TypeScript usage needed adjustment (task 6.1) |
| 5 | Schema iteration reuse (ADR-001 / existing `_all_tenant_schemas` pattern) | AI may write a new ad-hoc schema-listing query for the Training Jobs Running count instead of reusing `_all_tenant_schemas` (and the same loop pass as Pending Approvals), reintroducing the `tenant_system`/missing-schema bug the current code already guards against | Grep the diff for any new `SELECT ... FROM public.tenants` / `pg_namespace` query outside `_all_tenant_schemas`; confirm Training Jobs Running is computed in the same schema-iteration pass already producing Pending Approvals (task 4.1) |
| 6 | Removal of Documents(all)/Avg Model F1 leaves dead code | AI may leave the old `doc_count_all`/`avg_f1` computation in place (still running the removed `documents`/`model_versions` queries) even though the stat is no longer surfaced, wasting queries with no UI benefit | Read the rewritten `_system_admin_data` and confirm no unused variable still runs the old documents-sum or F1-average SQL, and no `model_versions` query remains anywhere in the system_admin branch (task 6.2) |
| 7 | `sources` dict key set and reuse across the shared Pending-Approvals/Training-Jobs-Running query pass (existing `_null_sources()` / TS `DashboardSummaryResponse.sources` type) | AI may add a new `sources` key (e.g. `"users"`, `"audit"`, `"health"`) for the new data reads instead of reusing the existing keys, which the TypeScript `Record<"tenants" \| "training" \| "documents" \| "annotations" \| "models" \| "feedback", boolean>` type does not include; or may fail to set `sources.training` to `false` when the shared Pending-Approvals/Training-Jobs-Running query fails for a schema | Confirm the implementation maps Active Users/Platform Activity/Platform Health reads onto the existing `sources` keys (`tenants`, `training`) rather than inventing new keys, and that `sources.training` reflects failures in either of the two stats sharing that query pass (task 3.2) |

> Aim for 3–7 entries. Do not invent risks without basis in design.md.

---

## 3. Pattern & ADR Compliance

| ADR | Decision Summary | Constraint on This Change | Verification Step |
|-----|---------------------|------------------------------|------------------------|
| ADR-001: Tenant Data Isolation via Separate Database Schemas | Each tenant's operational data lives in its own `tenant_<id>` schema; cross-tenant aggregation must iterate schemas derived from what actually exists | The "Training Jobs Running" count and any other per-tenant aggregation must reuse the existing `_all_tenant_schemas` schema-existence-checked list, not assume schemas from `public.tenants` rows alone | Confirm (Hallucination Risk #5) that the Training Jobs Running query iterates the same schema list already used for Pending Approvals, and that the `tenant_system`/missing-schema exclusion scenarios (rows 8–9 in Section 1) pass |
| ADR-003: Per-Tenant Model Serving Topology | A single shared Model Serving Layer serves all tenants — not one deployment per tenant | The "Model Serving" row in Platform Health must be exactly ONE `/health` check against `settings.model_serving_url`, not a per-tenant loop; it is also one of the two services whose failure alone drives the "Critical" tier | Grep the implementation for the Model Serving health check and confirm it is a single outbound call, not iterated per tenant schema (task 6.3) |
| ADR-004: OpenSpec Spec-Driven Development Governance | Requirement changes need delta specs before implementation | This change's delta specs (`dashboard-summary-endpoint`, `portal-dashboard`) must exist and be archived/synced before the corresponding code ships | Confirm both delta spec files exist under this change's `specs/` directory and that `openspec status` shows the specs artifact as done prior to archive |

---

## 4. Evidence Requirements

### Functional Evidence

- [ ] Scenario 1 (system_admin summary returns role-specific data): API test/trace showing the 4 new stats, "Platform Activity" pTitle, and "Platform Health" sideTop with a Healthy/Degraded/Critical status and no F1/precision/recall/loss fields
- [ ] Scenario 2 (tenant_admin summary unchanged): existing tenant_admin test suite passes unmodified
- [ ] Scenario 3 (annotator summary unchanged): existing annotator test suite passes unmodified
- [ ] Scenario 4 (business_user summary unchanged): existing business_user test suite passes unmodified
- [ ] Scenario 5 (unavailable training service): test output showing `tenant_admin` training-dependent fields are `null` with `sources.training: false` and HTTP 200
- [ ] Scenario 6 (unauthenticated rejected): test output showing 401
- [ ] Scenario 7 (one tenant schema failure isolated): test output showing healthy-tenant stats survive one broken tenant schema, no aborted-transaction propagation
- [ ] Scenario 8 (virtual system tenant excluded): test output confirming no query/exception against `tenant_system`
- [ ] Scenario 9 (tenant rows without schema excluded): test output confirming zero contribution and zero logged exceptions
- [ ] Scenario 10 (partial aggregate not reported complete): test output showing `sources.training: false` when a schema's training_jobs query fails
- [ ] Scenario 11 (Platform Activity generic feed): test output/API trace showing ordered, human-readable (or humanized-fallback), multi-tenant, unfiltered activity rows
- [ ] Scenario 12 (Platform Health deterministic derivation): unit test output for `_platform_health_status` covering the rule directly
- [ ] Scenario 13 (non-critical service down → Degraded): test output showing correct per-service reporting and "Degraded" overall status
- [ ] Scenario 14 (critical service down → Critical): test output showing "Critical" overall status even with all non-critical services Online
- [ ] Scenario 15 (Active Users from tenant_users status): test output showing the count matches `status='active'` rows only
- [ ] Scenario 16 (system_admin data shape, portal-dashboard): API/contract test confirming the full new shape and absence of SLA/p95/GPU fields
- [ ] Scenario 17–19 (tenant_admin/annotator/business_user data shape unchanged): existing contract tests pass unmodified
- [ ] Scenario 20 (partial service failure degrades gracefully): UI test or manual verification showing `—` for unavailable-service stats, no full-page error
- [ ] Scenario 21 (system_admin real data from wired sources): API trace against a seeded dev DB showing real tenant/user/activity/health values, not placeholders
- [ ] Scenario 22–24 (other roles real data unchanged): existing tests pass unmodified
- [ ] Scenario 25 (sources map): API trace showing `sources` keys present per role
- [ ] Scenario 26 (unauthenticated rejected, portal-dashboard copy): covered by Scenario 6's evidence
- [ ] Scenario 27 (activity row navigates — training): existing `ActivityPanel` navigation test passes unmodified
- [ ] Scenario 28 (tenant lifecycle row navigates to /admin/tenants): new frontend test or manual click-through confirming navigation for `go: "tenants"`
- [ ] Scenario 29 (status dot/tag colours): existing `ActivityPanel` colour test passes unmodified
- [ ] Scenario 30–32 (progress bar, sideMetrics, sideRows colours): existing `MetricsPanel` tests pass unmodified
- [ ] Scenario 33 (system_admin service status colour): test or screenshot confirming an `"Offline"` sideMetrics value renders in the red/bad status colour
- [ ] Scenario 34 (Platform Health severity colour): test or screenshot confirming "Critical"/"Degraded"/"Healthy" render red/amber/green respectively

### Structural Evidence

- [ ] Code review completed — implementation matches design.md decisions (no undocumented deviations)
- [ ] All ADR compliance steps in Section 3 confirmed ✓
- [ ] No undocumented architectural patterns introduced
- [ ] No AI-invented requirements present in generated code (cross-checked against spec files)

### Edge Case Evidence

- [ ] Risk 1 mitigation confirmed — no `action`/`kind` allowlist filter present; unmapped-action fallback verified
- [ ] Risk 2 mitigation confirmed — Critical/Degraded/Healthy priority-ordering test matrix passes
- [ ] Risk 3 mitigation confirmed — health checks confirmed concurrent, gateway self-check confirmed hard-coded, per-service exception isolation confirmed, 3s timeout confirmed
- [ ] Risk 4 mitigation confirmed — `types/dashboard.ts` `sideMetrics` tuple shape confirmed unchanged
- [ ] Risk 5 mitigation confirmed — Training Jobs Running query confirmed to reuse `_all_tenant_schemas` and the Pending Approvals loop pass, not a new ad-hoc schema query
- [ ] Risk 6 mitigation confirmed — no dead documents/F1/model_versions computation remains in `_system_admin_data`
- [ ] Risk 7 mitigation confirmed — no new `sources` key introduced; `sources.training` correctly reflects both Pending Approvals and Training Jobs Running query health

---

## 5. Evidence Log

| # | Evidence Type | Description / Link | Scenario(s) Covered | Collected By | Date |
|---|--------------|-----------------------|------------------------|------------------|------|
| 1 | | | | | |
| 2 | | | | | |
| 3 | | | | | |

---

## 6. Audit Record

> ⚠️ **GATE: This section must be completed and signed by a human reviewer before `/opsx:archive` is run.** An unsigned or incomplete Audit Record is a hard block on archive.

**Change slug:** redesign-system-admin-dashboard
**Proposal:** `openspec/changes/redesign-system-admin-dashboard/proposal.md`
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
