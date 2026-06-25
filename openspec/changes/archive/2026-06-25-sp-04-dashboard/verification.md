# Verification Plan

**Change:** sp-04-dashboard
**Generated:** 2026-06-24
**Status:** 🔴 Incomplete — Evidence Log and Audit Record must be filled by a human reviewer before archive.

---

## 1. Spec Alignment

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | dashboard-summary-endpoint | Dashboard Summary Endpoint | system_admin summary returns role-specific data | Given authenticated system_admin, when GET /api/v1/dashboard/summary, then response contains kicker "Platform control plane", 4 stats, pTitle "Approval queue", sideTop "Platform health" | | - [ ] |
| 2 | dashboard-summary-endpoint | Dashboard Summary Endpoint | tenant_admin summary returns pipeline data | Given authenticated tenant_admin, when GET /api/v1/dashboard/summary, then response contains 4 pipeline stats, pTitle "Pipeline activity", sideTop "Active model" | | - [ ] |
| 3 | dashboard-summary-endpoint | Dashboard Summary Endpoint | annotator summary returns task data | Given authenticated annotator, when GET /api/v1/dashboard/summary, then response contains assigned tasks, spans, suggestions, completion stats, pTitle "My tasks", sideTop "Dataset readiness" | | - [ ] |
| 4 | dashboard-summary-endpoint | Dashboard Summary Endpoint | business_user summary returns extraction data | Given authenticated business_user, when GET /api/v1/dashboard/summary, then response contains extraction stats, pTitle "Recent extractions", sideTop "Active model" | | - [ ] |
| 5 | dashboard-summary-endpoint | Dashboard Summary Endpoint | unavailable training service returns null values | Given training service returns 5xx, when GET /api/v1/dashboard/summary, then training-dependent values are null, sources.training is false, HTTP 200 | | - [ ] |
| 6 | dashboard-summary-endpoint | Dashboard Summary Endpoint | unauthenticated request rejected | Given no valid JWT, when GET /api/v1/dashboard/summary, then 401 Unauthorized | | - [ ] |
| 7 | dashboard-summary-endpoint | DashboardData TypeScript Type | type compiles with all fields | Given a DashboardData object matching mockup shape, when assigned to TypeScript type, then no compiler errors | | - [ ] |
| 8 | dashboard-summary-endpoint | DashboardData TypeScript Type | null values are assignable | Given a DashboardData object with null stat values, when assigned to TypeScript type, then no compiler errors | | - [ ] |
| 9 | portal-dashboard | Dashboard Data Shape | system_admin data shape | Given system_admin, when dashboard summary called, then response includes platform-control-plane kicker, 4 stats, approval queue, platform health side panel with storage by tenant | | - [ ] |
| 10 | portal-dashboard | Dashboard Data Shape | tenant_admin data shape | Given tenant_admin, when dashboard summary called, then pipeline stats, pipeline activity rows (training, dataset, docs, model), active model panel with quota usage | | - [ ] |
| 11 | portal-dashboard | Dashboard Data Shape | annotator data shape | Given annotator, when dashboard summary called, then assigned tasks, spans, suggestions, completion stats, my tasks rows, dataset readiness with span-by-entity breakdown | | - [ ] |
| 12 | portal-dashboard | Dashboard Data Shape | business_user data shape | Given business_user, when dashboard summary called, then extraction stats, recent extractions rows, active model panel with top extracted fields | | - [ ] |
| 13 | portal-dashboard | Dashboard Data Shape | partial service failure degrades gracefully | Given training service unavailable, when dashboard renders, then affected stats show "—", unaffected stats show real values, no full-page error | | - [ ] |
| 14 | portal-dashboard | Dashboard Summary Endpoint | system_admin summary returns real data from wired sources | Given system_admin, when dashboard summary called, then tenant count is real, sources.tenants is true, training fields fetched | | - [ ] |
| 15 | portal-dashboard | Dashboard Summary Endpoint | unauthenticated request rejected | Given no valid JWT, when dashboard summary called, then 401 | | - [ ] |
| 16 | portal-dashboard | Hero Section | editorial layout renders large hero on transparent background | Given layout is "Editorial", when dashboard renders, then kicker/title/line in large typography, transparent bg, SegmentControl shows Editorial active | | - [ ] |
| 17 | portal-dashboard | Hero Section | command layout renders compact hero with dark container | Given layout is "Command", when dashboard renders, then dark container (#161b24), animated gradient orbs, white title text, all 3 elements visible | | - [ ] |
| 18 | portal-dashboard | Hero Section | layout toggle persists across navigation | Given user switches to "Command", when navigating away and back, then Command layout still active | | - [ ] |
| 19 | portal-dashboard | Hero Section | layout toggle does not re-fetch data | Given data loaded, when user toggles layout, then no network request, stat/panel data unchanged | | - [ ] |
| 20 | portal-dashboard | Stat Card Strip | stat cards render with live values | Given dashboard summary loaded, when stat strip renders, then 4 cards with correct value, unit, label, sub, delta | | - [ ] |
| 21 | portal-dashboard | Stat Card Strip | stat cards render skeleton while loading | Given dashboard query in-flight, when stat strip renders, then 4 skeleton shimmer placeholders | | - [ ] |
| 22 | portal-dashboard | Stat Card Strip | warn direction renders amber indicator | Given stat has dir "warn", when card renders, then delta pill is amber/warn colour | | - [ ] |
| 23 | portal-dashboard | Activity Panel | activity row navigates on click | Given system_admin activity row with go "training", when user clicks row, then router navigates to /training | | - [ ] |
| 24 | portal-dashboard | Activity Panel | status tag colours match mockup | Given row with tk "pending_approval", when renders, then amber tag; tk "completed" → green tag; tk "running" → pulsing dot | | - [ ] |
| 25 | portal-dashboard | Secondary Metrics Panel | progress bar fills to correct percentage | Given bar: 62, when secondary panel renders, then progress bar fills to 62% with growBar animation | | - [ ] |
| 26 | portal-dashboard | Secondary Metrics Panel | sideRows mini bars render correct colours | Given sideRows with c colour spec, when mini bar renders, then bg colour matches specification | | - [ ] |
| 27 | portal-dashboard | Data Freshness | data refetches every 30 seconds | Given dashboard open with loaded data, when 30s elapse, then query auto-refetches in background without UI flash | | - [ ] |
| 28 | portal-dashboard | Data Freshness | QueryClientProvider wraps the app | Given any portal page, when useQueryClient() called, then shared QueryClient instance returned | | - [ ] |

---

## 2. Hallucination Risk Register

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|-------------------|----------------------|
| 1 | DashboardData shape fields | AI may invent stat/panel field names not in the mockup's `dashData(role)` shape (e.g., adding `chartUrl`, `entityType` to stat cards) | Cross-check every field in generated `DashboardData` type and backend response against the mockup's `dashData(role)` in `docs/NER Platform.dc.html` — any field not in the mockup is suspect |
| 2 | Role-routing logic | AI may hardcode per-role data construction (if/else chains) instead of using the service-per-role table specified in design.md | Verify the summary endpoint uses a lookup-table pattern for role→service mapping, not repetitive if/else |
| 3 | Error isolation in composite endpoint | AI may wrap all downstream calls in a single try/catch, causing one failing service to return 502 instead of partial data with nulls | Verify each downstream service call is wrapped in its own try/catch with independent null-assignment for its data fields |
| 4 | Layout toggle data reload | AI may invalidate the dashboard query when layout toggles, causing re-fetch on layout switch | Verify toggling Editorial/Command does not call `invalidateQueries` or trigger any network request |
| 5 | Skeleton loading state | AI may use a full-page spinner instead of per-card skeleton shimmers during loading | Verify loading state shows individual skeleton stat cards with shimmer animation, not a `<Spinner size="lg">` |

---

## 3. Pattern & ADR Compliance

| ADR | Decision Summary | Constraint on This Change | Verification Step |
|-----|-----------------|--------------------------|-------------------|
| ADR-001 | Schema-per-tenant data isolation | Dashboard queries must be scoped to the caller's tenant_id; system_admin queries may aggregate | Verify gateway passes tenant_id from JWT to downstream service calls; verify system_admin queries are explicitly scoped to tenant or allowed cross-tenant via tenant_id param |
| ADR-003 | Shared model-serving pool | Active model data comes from model registry, not direct serving layer queries | Verify the summary endpoint fetches active model info from the model registry service, not the model-serving pod directly |
| ADR-004 | OpenSpec SDD governance | All artifacts (proposal, design, spec, verification, tasks) must be created before implementation | Verify all 5 artifacts exist in `openspec/changes/sp-04-dashboard/` |
| ADR-005 | Bounded agent tool access | Implementation must follow task list; no ad-hoc changes without spec coverage | Verify each task in tasks.md maps to a requirement/scenario in the spec files |
| ADR-006 | Celery + RabbitMQ for async GPU jobs | Training job status data fetched from training-orchestrator service | Verify training-dependent fields call the training service, not the celery queue directly |

---

## 4. Evidence Requirements

### Functional Evidence

- [ ] Scenario 1-4: Integration test showing GET /api/v1/dashboard/summary returns correct shape per role
- [ ] Scenario 5: Integration test showing training service failure returns null values + sources.training: false
- [ ] Scenario 6: Integration test showing unauthenticated request returns 401
- [ ] Scenario 7-8: TypeScript compilation check for DashboardData type
- [ ] Scenario 16-19: Unit test / browser test for Editorial/Command layout toggle persistence
- [ ] Scenario 20-22: Unit test for stat card rendering with live data, skeleton state, and warn direction
- [ ] Scenario 23-24: Unit test for activity row click navigation and status tag colours
- [ ] Scenario 25-26: Unit test for progress bar fill percentage and mini bar colours
- [ ] Scenario 27-28: Integration test for TanStack Query refetch interval and QueryClientProvider

### Structural Evidence

- [ ] Code review completed — implementation matches design.md decisions (no undocumented deviations)
- [ ] All ADR compliance steps in Section 3 confirmed ✓
- [ ] No undocumented architectural patterns introduced
- [ ] Role→service mapping uses lookup table (not if/else chain)
- [ ] Each downstream call has independent error handling

### Edge Case Evidence

- [ ] Risk 1 mitigation confirmed — all DashboardData fields cross-checked against mockup `dashData(role)` in NER Platform.dc.html
- [ ] Risk 2 mitigation confirmed — role→service mapping uses lookup table pattern
- [ ] Risk 3 mitigation confirmed — each service call independently try/caught
- [ ] Risk 4 mitigation confirmed — layout toggle triggers no network request
- [ ] Risk 5 mitigation confirmed — loading state uses skeleton shimmers, not spinner

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
> `/opsx-archive` is run.** An unsigned or incomplete Audit Record is a hard block on archive.

**Change slug:** sp-04-dashboard
**Proposal:** `openspec/changes/sp-04-dashboard/proposal.md`
**Spec files reviewed:**
- `specs/dashboard-summary-endpoint/spec.md`
- `specs/portal-dashboard/spec.md`

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
