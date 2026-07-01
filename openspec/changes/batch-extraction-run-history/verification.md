# Verification Plan

**Change:** batch-extraction-run-history
**Generated:** 2026-07-01
**Status:** 🔴 Incomplete — Evidence Log and Audit Record must be filled by a human reviewer before archive.

---

## 1. Spec Alignment

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | extraction-service | List extraction runs | List batch extraction runs for a tenant | Given a tenant with a completed, a queued, and a failed run, when a Tenant Admin GETs `/api/v1/extract-batch`, then the response is 200 with a `runs` array containing all three, each including `run_id`, `status`, `total_documents`, `processed_count`, `skipped_count`, `failed_count`, `started_at`, `completed_at`, and `model_version` | tests/test_batch_extraction.py::test_list_batch_runs_returns_all_fields (task 3.1) | - [ ] |
| 2 | extraction-service | List extraction runs | Runs are ordered most-recent-first | Given a tenant with runs started at different times, when a Tenant Admin GETs `/api/v1/extract-batch`, then the `runs` array is ordered by `started_at` descending | tests/test_batch_extraction.py::test_list_batch_runs_ordered_desc (task 3.1) | - [ ] |
| 3 | extraction-service | List extraction runs | List is scoped to the requesting tenant | Given tenant A has runs and tenant B has none, when tenant B's Tenant Admin GETs `/api/v1/extract-batch`, then the response is 200 with an empty `runs` array | tests/test_batch_extraction.py::test_list_batch_runs_tenant_isolated (task 3.1) | - [ ] |
| 4 | extraction-service | List extraction runs | List returns empty array when no runs exist | Given a tenant with no extraction runs, when a Tenant Admin GETs `/api/v1/extract-batch`, then the response is 200 with an empty `runs` array | tests/test_batch_extraction.py::test_list_batch_runs_empty_for_new_tenant (task 3.1) | - [ ] |
| 5 | extraction-service | List extraction runs | List entities as non-admin business user | Given an authenticated `business_user`, when they GET `/api/v1/extract-batch`, then the response is 200 | tests/test_batch_extraction.py::test_list_batch_runs_business_user_allowed (task 3.1) | - [ ] |
| 6 | extraction-service | Gateway Extraction Proxy Uses JWT-Only URL Structure | Proxy forwards single extraction request without tid in URL | Given a valid JWT with `tenant_id` and `role: business_user`, when a POST is sent to gateway `/api/v1/extract` with `{"text": "Acme Corp"}`, then the response is 200 with extracted entities and the proxy forwarded to the extraction service at `/api/v1/extract` | Existing gateway proxy test suite — regression re-run (task 3.2) | - [ ] |
| 7 | extraction-service | Gateway Extraction Proxy Uses JWT-Only URL Structure | Proxy forwards batch run list request without tid in URL | Given a valid JWT with `tenant_id` and `role: business_user`, when a GET is sent to gateway `/api/v1/extract-batch`, then the response is 200 with a `runs` array and the proxy forwarded to the extraction service at `/api/v1/extract-batch` | Gateway proxy test suite::test_gateway_proxies_extract_batch_list (task 3.2) | - [ ] |
| 8 | extraction-service | Gateway Extraction Proxy Uses JWT-Only URL Structure | Proxy returns 403 when JWT is missing | Given no JWT token, when a POST is sent to gateway `/api/v1/extract` with `{"text": "test"}`, then the response is 403 | Existing gateway proxy test suite — regression re-run (task 3.2) | - [ ] |
| 9 | portal-extraction-page | Batch Runs Tab — Batch Extraction Management | Batch Runs tab lists existing runs | Given the user switches to or reloads on the Batch Runs tab, when the tab mounts, then a `GET /api/v1/extract-batch` request is sent, every run in the response's `runs` array appears as a card, and the most recent run is selected by default | Manual browser verification + network trace (task 4.1) | - [ ] |
| 10 | portal-extraction-page | Batch Runs Tab — Batch Extraction Management | Run history persists across page reload | Given a batch run previously completed, when the page is reloaded and the Batch Runs tab mounts, then the completed run appears in the list and the empty state ("No batch runs yet") is not shown | Manual browser verification, before/after reload screenshots (task 4.2) | - [ ] |
| 11 | portal-extraction-page | Batch Runs Tab — Batch Extraction Management | Selecting a batch run shows detail | Given multiple run cards are visible, when the user clicks a card, then it receives a primary border highlight and the right panel shows that run's stats and progress percentage | Manual browser verification screenshot (task 4.3) | - [ ] |
| 12 | portal-extraction-page | Batch Runs Tab — Batch Extraction Management | Triggering a new batch run | Given the Batch Runs tab is active, when the user clicks "New batch run", then a `POST /api/v1/extract-batch` request is sent and on 202 the new run appears at the top of the list as "queued" and is auto-selected | Manual browser verification screenshot/trace (task 4.3) | - [ ] |
| 13 | portal-extraction-page | Batch Runs Tab — Batch Extraction Management | In-progress runs poll for status updates | Given one or more runs have status "running" or "queued", when the tab is mounted and active, then the system polls `GET /api/v1/extract-batch/{run_id}` every 3 seconds per in-flight run until it reaches a terminal state | Manual browser verification, network trace showing polling cadence (task 4.3) | - [ ] |
| 14 | portal-extraction-page | Batch Runs Tab — Batch Extraction Management | Status pills use correct visual styles | Given runs with various statuses, when the list renders, then "completed" uses the good color token, "running"/"queued" use the warning token, and "failed" uses the bad token | Manual browser verification screenshot (task 4.3) | - [ ] |

> **Rule:** Every `#### Scenario:` block in every `specs/**/*.md` file for this change
> MUST appear as a row in this table. A missing scenario is a P1 gap that blocks archive.

---

## 2. Hallucination Risk Register

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|-------------------|----------------------|
| 1 | Tenant scoping on the new list query (ADR-001) | AI may write the list query without scoping to `_schema(tenant_id)`, or interpolate `tenant_id` unsafely, risking a cross-tenant data leak | Read the new query in `entity_store.py`/`extraction.py`; confirm it targets `{schema}.extraction_runs` using the same `_schema()` helper as existing endpoints, and confirm scenario 3 (tenant isolation) passes with two distinct tenants |
| 2 | Response field drift from `BatchRunStatus` | AI may invent extra fields (e.g., `document_id`) or rename existing ones instead of reusing `BatchRunStatus` fields plus `run_id` | Diff the new response schema against `BatchRunStatus` in `schemas.py`; confirm no fields exist beyond those named in the "List extraction runs" requirement |
| 3 | Gateway proxy route wiring | AI may add the new proxy route with the wrong HTTP method, forget to forward the `Authorization` header, or accidentally shadow the existing `/api/v1/extract-batch/{run_id}` route (path collision with the no-ID list route) | Manually call `GET /api/v1/extract-batch` and `GET /api/v1/extract-batch/{run_id}` through the gateway and confirm both route correctly and both forward the JWT |
| 4 | Ordering and cap correctness | AI may omit `ORDER BY started_at DESC` or implement an unbounded query instead of the agreed `LIMIT 50` | Insert runs with distinct `started_at` values and confirm response order; confirm a `LIMIT` clause exists in the query |
| 5 | `model_version` passthrough for base-model runs (ADR-008) | AI may special-case `model_version = "0"` (e.g., convert to `null` or omit it) instead of passing it through as-is | Trigger or seed a run with `model_version = "0"` and confirm it appears unmodified in the list response |
| 6 | Scope creep into frontend code | Proposal states no frontend code change is needed since `use-batch-runs.ts` already calls the endpoint; AI may unnecessarily modify the hook or components anyway | Diff review: confirm `src/portal/src/hooks/use-batch-runs.ts` and `BatchRunsTab.tsx` are unchanged (or changes are justified against a real discrepancy found during implementation) |

> Aim for 3–7 entries. Do not invent risks without basis in design.md.

---

## 3. Pattern & ADR Compliance

| ADR | Decision Summary | Constraint on This Change | Verification Step |
|-----|-----------------|--------------------------|-------------------|
| ADR-001: Tenant Data Isolation via Separate Database Schemas | Each tenant's data lives in its own `tenant_<uuid>` schema | The new list query must scope to `_schema(tenant_id)`, with no cross-tenant reads | Run scenario 3 (list is scoped to the requesting tenant) with two tenants that both have runs; confirm each tenant only sees its own |
| ADR-008: Base Model as Default | Batch runs may legitimately use `model_version: "0"` | The list response must pass through `model_version` unmodified, including `"0"` | Run scenario with a base-model run (`model_version = "0"`) through the list endpoint and confirm the value is `"0"` in the response, not `null` or omitted |

---

## 4. Evidence Requirements

Evidence that **MUST** be collected and logged in Section 5 before this change is archived.
Do not archive while any item below remains unchecked.

### Functional Evidence

- [ ] Scenario 1 (List batch extraction runs for a tenant): API trace or test output showing `GET /api/v1/extract-batch` returning 200 with all three runs and required fields
- [ ] Scenario 2 (Runs ordered most-recent-first): test output or trace showing correct descending order
- [ ] Scenario 3 (List scoped to requesting tenant): test output showing tenant B's list is empty despite tenant A having runs
- [ ] Scenario 4 (Empty array when no runs exist): test output showing empty `runs` array for a fresh tenant
- [ ] Scenario 5 (business_user can list): test output showing 200 for a `business_user` role
- [ ] Scenario 6 (proxy forwards `/extract` without tid): existing test/trace re-confirmed unaffected by this change
- [ ] Scenario 7 (proxy forwards list request without tid): API trace showing gateway `GET /api/v1/extract-batch` reaching the extraction service and returning `runs`
- [ ] Scenario 8 (proxy 403 without JWT): existing test/trace re-confirmed unaffected by this change
- [ ] Scenario 9 (Batch Runs tab lists existing runs): screenshot or browser trace showing populated run list on tab mount, with network trace of `GET /api/v1/extract-batch`
- [ ] Scenario 10 (Run history persists across reload): screenshot before and after a manual page reload showing the completed run still listed, no "No batch runs yet" message
- [ ] Scenario 11 (Selecting a run shows detail): screenshot showing selected card highlight and matching detail panel
- [ ] Scenario 12 (Triggering a new run): screenshot/trace showing new "queued" run appended to top of list and auto-selected
- [ ] Scenario 13 (In-progress runs poll): network trace showing 3-second polling of `GET /api/v1/extract-batch/{run_id}` that stops at a terminal state
- [ ] Scenario 14 (Status pill colors): screenshot showing correct color tokens for each status

### Structural Evidence

- [ ] Code review completed — implementation matches design.md decisions (no undocumented deviations)
- [ ] All ADR compliance steps in Section 3 confirmed ✓
- [ ] No undocumented architectural patterns introduced
- [ ] No AI-invented requirements present in generated code (cross-checked against spec files)

### Edge Case Evidence

- [ ] Risk 1 mitigation confirmed — tenant-scoping check performed with two tenants, no cross-tenant leakage observed
- [ ] Risk 2 mitigation confirmed — response schema diffed against `BatchRunStatus`, no extraneous or renamed fields
- [ ] Risk 3 mitigation confirmed — both `/api/v1/extract-batch` and `/api/v1/extract-batch/{run_id}` gateway routes verified to route correctly with no collision
- [ ] Risk 4 mitigation confirmed — ordering and `LIMIT 50` verified against seeded data
- [ ] Risk 5 mitigation confirmed — `model_version: "0"` run verified to pass through unmodified
- [ ] Risk 6 mitigation confirmed — frontend hook/component diff reviewed, no unnecessary changes

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
> `/opsx:archive` is run.** An unsigned or incomplete Audit Record is a hard block on archive.

**Change slug:** batch-extraction-run-history
**Proposal:** `openspec/changes/batch-extraction-run-history/proposal.md`
**Spec files reviewed:**
  - specs/extraction-service/spec.md
  - specs/portal-extraction-page/spec.md

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