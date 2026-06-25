# Verification Plan

**Change:** analytics-and-reporting
**Generated:** 2026-06-24
**Status:** 🔴 Incomplete — Evidence Log and Audit Record must be filled by a human reviewer before archive.

---

## 1. Spec Alignment

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | analytics-query-api | Structured Query API | Successful query with entity type and date range filter | Given entities of types PERSON and ORG in a date range, when POST with matching filters, then results contain only entities of those types in range | tasks.md 2.7 — integration test: query with entity type + date range | - [ ] |
| 2 | analytics-query-api | Structured Query API | Query with confidence filter | Given entities at various confidence scores, when POST with confidence min/max, then only entities in that range are returned | tasks.md 2.7 — integration test: query with confidence filter | - [ ] |
| 3 | analytics-query-api | Structured Query API | Query with document source and annotator filter | Given entities from specific sources and annotators, when POST with those filters, then only matching entities are returned | tasks.md 2.7 — integration test: document source + annotator filter | - [ ] |
| 4 | analytics-query-api | Structured Query API | Query returns empty results for non-matching filters | Given no entities match the filter, when POST with that filter, then empty results array is returned | tasks.md 2.7 — integration test: empty results | - [ ] |
| 5 | analytics-query-api | Structured Query API | Query timeouts gracefully | Given a filter that triggers a long query, when the 5s timeout elapses, then HTTP 504 is returned | tasks.md 2.6 — unit test: timeout scenario | - [ ] |
| 6 | analytics-query-api | Query Parameter Validation | Invalid entity type returns 422 | Given a non-existent entity type, when POST with it in entity_types, then HTTP 422 is returned | tasks.md 2.6 — unit test: invalid entity type validation | - [ ] |
| 7 | analytics-query-api | Query Parameter Validation | Invalid date format returns 422 | Given an invalid date format, when POST with it, then HTTP 422 is returned | tasks.md 2.6 — unit test: invalid date format | - [ ] |
| 8 | analytics-query-api | Tenant-scoped Query Execution | Query filters by tenant schema | Given two tenants with different entities, when same filter is sent for each, then each response contains only that tenant's data | tasks.md 2.7 — integration test: cross-tenant isolation | - [ ] |
| 9 | analytics-query-api | Tenant-scoped Query Execution | Unauthenticated request returns 401 | Given no valid JWT, when POST to query endpoint, then HTTP 401 is returned | tasks.md 2.7 — integration test: unauthenticated request | - [ ] |
| 10 | analytics-dashboard | Dashboard Aggregation API | Dashboard returns all widget data | Given a tenant with extracted entities and refreshed materialized views, when GET dashboard, then response contains entity_coverage, confidence_distribution, extraction_volume, and document_entity_counts | tasks.md 3.9 — integration test: dashboard endpoint | - [ ] |
| 11 | analytics-dashboard | Entity Coverage Widget | Entity coverage returns correct percentages | Given 100 documents with 80 having PERSON and 40 having ORG entities, when GET dashboard, then entity_coverage shows 80.0 and 40.0 | tasks.md 3.9 — integration test: entity coverage | - [ ] |
| 12 | analytics-dashboard | Confidence Distribution Widget | Confidence distribution returns correct bucket counts | Given entities with varying confidence scores, when GET dashboard, then confidence_distribution has correct bucket labels and counts | tasks.md 3.9 — integration test: confidence distribution | - [ ] |
| 13 | analytics-dashboard | Extraction Volume Over Time Widget | Extraction volume returns daily counts | Given 50 entities on 2026-05-01 and 30 on 2026-05-02, when GET dashboard, then extraction_volume includes entries with correct counts | tasks.md 3.9 — integration test: extraction volume | - [ ] |
| 14 | analytics-dashboard | Per-Document Entity Counts Widget | Per-document entity counts returned | Given 10 documents with avg 3.5 PERSON and 1.2 ORG per doc, when GET dashboard, then document_entity_counts shows those values | tasks.md 3.9 — integration test: per-doc entity counts | - [ ] |
| 15 | analytics-dashboard | Materialized View Refresh on Extraction Event | Materialized view refreshes after extraction | Given existing materialized views with entity_coverage.PERSON=80.0, when ExtractionCompleted event consumed, then views reflect updated count within 5s | tasks.md 3.8 — unit test: event-driven refresh | - [ ] |
| 16 | analytics-dashboard | On-Demand Materialized View Refresh | On-demand refresh succeeds | Given stale materialized views, when POST to refresh endpoint, then HTTP 202 is returned and views are refreshed | tasks.md 3.8 — unit test: on-demand refresh | - [ ] |
| 17 | analytics-dashboard | On-Demand Materialized View Refresh | Unauthenticated refresh request returns 401 | Given no valid JWT, when POST to refresh endpoint, then HTTP 401 is returned | tasks.md 3.9 — integration test: unauthenticated refresh | - [ ] |
| 18 | analytics-export | CSV Export Endpoint | Export returns valid CSV | Given matching entities, when POST export with format:csv, then Content-Type is text/csv and body is valid CSV with header row | tasks.md 4.6 — unit test: CSV serialization | - [ ] |
| 19 | analytics-export | CSV Export Endpoint | Empty export returns header-only CSV | Given no matching entities, when POST export CSV, then response contains only CSV header row | tasks.md 4.6 — unit test: empty CSV export | - [ ] |
| 20 | analytics-export | JSON Export Endpoint | Export returns valid JSON | Given matching entities, when POST export with format:json, then Content-Type is application/json and body is valid JSON array | tasks.md 4.6 — unit test: JSON serialization | - [ ] |
| 21 | analytics-export | Export Filter Validation | Invalid export filter returns 422 | Given invalid entity type in filter, when POST export, then HTTP 422 is returned | tasks.md 4.7 — integration test: invalid filter | - [ ] |
| 22 | analytics-export | Export Result Size Limit | Export exceeds size limit | Given >10000 matching entities, when POST export, then only 10000 rows returned with X-Result-Truncated: true header | tasks.md 4.6 — unit test: size limit truncation | - [ ] |
| 23 | analytics-ui | Analytics Dashboard Page | Dashboard page loads widgets | Given a logged-in user with analytics permission, when navigating to /tenants/{tid}/analytics, then all four widgets display with data from dashboard API | tasks.md 5.13 — E2E test: page load with widgets | - [ ] |
| 24 | analytics-ui | Analytics Dashboard Page | Dashboard page handles empty data gracefully | Given a tenant with no extracted entities, when navigating to analytics page, then widgets show empty state messages | tasks.md 5.12 — component test: empty state | - [ ] |
| 25 | analytics-ui | Dashboard Page Loading State | Loading state displayed during fetch | Given dashboard API has not responded, when analytics page loads, then a loading indicator is visible per widget | tasks.md 5.12 — component test: loading skeleton | - [ ] |
| 26 | analytics-ui | Ad-Hoc Query Controls | Filter controls execute query | Given a user on analytics page, when they select filters and click Query, then results table displays with pagination | tasks.md 5.13 — E2E test: filter and paginate | - [ ] |
| 27 | analytics-ui | Ad-Hoc Query Controls | Query with no results shows empty state | Given filters returning zero results, when user clicks Query, then "No matching entities found" is displayed | tasks.md 5.12 — component test: no results state | - [ ] |
| 28 | analytics-ui | Export Button | CSV export downloads file | Given applied filters, when user clicks Export CSV, then a CSV file is downloaded | tasks.md 5.13 — E2E test: CSV export | - [ ] |
| 29 | analytics-ui | Export Button | JSON export downloads file | Given applied filters, when user clicks Export JSON, then a JSON file is downloaded | tasks.md 5.13 — E2E test: JSON export | - [ ] |
| 30 | analytics-ui | Error State Handling | API error shows error banner | Given dashboard API returns HTTP 500, when page loads, then error banner with retry button is displayed | tasks.md 5.12 — component test: error banner | - [ ] |

---

## 2. Hallucination Risk Register

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|-------------------|----------------------|
| 1 | Query filter field names | AI may invent filter field names not in spec (e.g., `sort_by`, `group_by`) without specification | Compare generated query parser/validator against spec.md §Structured Query API — any field not listed in the filter body description is suspect |
| 2 | Materialized view SQL | AI may write aggregation SQL that queries across tenant schemas (missing search_path enforcement) | Verify every materialized view definition includes a `WHERE tenant_id = ...` or is scoped via search_path |
| 3 | Error path handling | AI may implement only the happy path for query/export, omitting timeout, validation error, and empty result paths | Verify each WHEN/THEN failure scenario in Section 1 has a corresponding code path and a failing test |
| 4 | Export format correctness | AI may produce malformed CSV (unquoted commas in entity text, missing header) or JSON that fails to parse correctly | Verify CSV output handles escaping of special characters; verify JSON output round-trips through json.loads |
| 5 | UI empty vs error states | AI may conflate empty data (no entities) with error states (API returns 500), showing wrong UI message | Verify the analytics page renders different content for empty response vs HTTP error response |
| 6 | Materialized view refresh race | AI may implement synchronous refresh that blocks the event handler, causing message processing backpressure | Verify the ExtractionCompleted handler dispatches refresh asynchronously (background task or separate queue) |

---

## 3. Pattern & ADR Compliance

| ADR | Decision Summary | Constraint on This Change | Verification Step |
|-----|-----------------|--------------------------|-------------------|
| ADR-001 | Separate PostgreSQL schemas per tenant with search_path enforcement | All analytics queries MUST execute within the requesting tenant's schema | Verify every raw SQL query string includes a schema-qualified table reference or search_path injection; verify no cross-schema queries exist |
| ADR-004 | OpenSpec SDD with mandatory artifact gates | This change must follow the full pipeline; all artifacts created before implementation | Verify proposal, design, specs, verification, and tasks artifacts exist and are complete |
| ADR-008 | Base model serves as default inference | Analytics queries entity data regardless of model source; entity storage includes model_version | Not directly constraining — analytics works on extracted entities from any model version |

---

## 4. Evidence Requirements

### Functional Evidence

- [ ] Scenario 1: Test output showing query with entity type + date range returns filtered results
- [ ] Scenario 2: Test output showing confidence filter returns entities within range
- [ ] Scenario 3: Test output showing document source + annotator filter works
- [ ] Scenario 4: Test output showing empty results for non-matching filters
- [ ] Scenario 5: Test output showing query timeout returns HTTP 504
- [ ] Scenario 6: Test output showing invalid entity type returns HTTP 422
- [ ] Scenario 7: Test output showing invalid date format returns HTTP 422
- [ ] Scenario 8: Test output showing query is tenant-scoped (two tenants, no cross-leakage)
- [ ] Scenario 9: Test output showing unauthenticated request returns HTTP 401
- [ ] Scenario 10: Test output showing dashboard endpoint returns all four widget sections
- [ ] Scenario 11: Test output showing entity coverage percentages are correct
- [ ] Scenario 12: Test output showing confidence distribution bucket counts are correct
- [ ] Scenario 13: Test output showing extraction volume daily counts are correct
- [ ] Scenario 14: Test output showing per-document entity counts are correct
- [ ] Scenario 15: Test/log output showing materialized view refreshes after ExtractionCompleted event
- [ ] Scenario 16: Test output showing on-demand refresh returns HTTP 202 and refreshes views
- [ ] Scenario 17: Test output showing unauthenticated refresh returns HTTP 401
- [ ] Scenario 18: Test output showing CSV export returns valid CSV with correct Content-Type
- [ ] Scenario 19: Test output showing empty export returns header-only CSV
- [ ] Scenario 20: Test output showing JSON export returns valid JSON array
- [ ] Scenario 21: Test output showing invalid export filter returns HTTP 422
- [ ] Scenario 22: Test output showing export truncation at 10000 rows with X-Result-Truncated header
- [ ] Scenario 23: Screenshot or E2E test showing analytics page with all four widgets loaded
- [ ] Scenario 24: Screenshot or E2E test showing empty state messages for tenant with no data
- [ ] Scenario 25: Screenshot or E2E test showing loading skeleton/spinner during data fetch
- [ ] Scenario 26: E2E test showing filter controls execute query and display paginated results
- [ ] Scenario 27: E2E test showing "No matching entities found" on zero-result query
- [ ] Scenario 28: E2E test showing CSV export downloads a file
- [ ] Scenario 29: E2E test showing JSON export downloads a file
- [ ] Scenario 30: Screenshot or E2E test showing error banner and retry button on API error

### Structural Evidence

- [ ] Code review completed — implementation matches design.md decisions (no undocumented deviations)
- [ ] All ADR compliance steps in Section 3 confirmed ✓
- [ ] No undocumented architectural patterns introduced
- [ ] No AI-invented requirements present in generated code (cross-checked against spec files)

### Edge Case Evidence

- [ ] Risk 1 mitigation confirmed — query filter field names match spec; no hallucinated fields
- [ ] Risk 2 mitigation confirmed — materialized view SQL is tenant-scoped via search_path
- [ ] Risk 3 mitigation confirmed — all error scenarios (timeout, validation, empty) have code paths and tests
- [ ] Risk 4 mitigation confirmed — CSV escaping and JSON validity verified
- [ ] Risk 5 mitigation confirmed — UI distinguishes empty data from error states
- [ ] Risk 6 mitigation confirmed — materialized view refresh is async, not blocking event handler

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
> `/opsx-apply-archive` is run.** An unsigned or incomplete Audit Record is a hard block on archive.

**Change slug:** analytics-and-reporting
**Proposal:** `openspec/changes/analytics-and-reporting/proposal.md`
**Spec files reviewed:**
  - specs/analytics-query-api/spec.md
  - specs/analytics-dashboard/spec.md
  - specs/analytics-export/spec.md
  - specs/analytics-ui/spec.md

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


