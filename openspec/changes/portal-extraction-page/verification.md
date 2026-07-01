# Verification Plan

**Change:** portal-extraction-page
**Generated:** 2026-06-30
**Status:** 🔴 Incomplete — Evidence Log and Audit Record must be filled by a human reviewer before archive.

---

## 1. Spec Alignment

Map every requirement and every scenario in this change to a testable acceptance criterion.
Each row drives one evidence entry in Section 5.

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | portal-extraction-page | Extraction Page Layout and Tab Navigation | Page renders with Playground tab active by default | Given a `business_user` navigates to `/extractions`, when the page mounts, then the "Extraction" heading, the three-tab pill, and the Playground tab content are all visible; the Playground button has the active (filled) style | Component test: `ExtractionPage` default render | - [ ] |
| 2 | portal-extraction-page | Extraction Page Layout and Tab Navigation | Clicking a tab switches the active content | Given the Playground tab is active, when the user clicks "Batch Runs", then the Batch Runs content is rendered and the Playground content is absent from the DOM | Component test: tab switching | - [ ] |
| 3 | portal-extraction-page | Playground Tab — Real-time Extraction | Running extraction displays results | Given text is in the textarea, when "Run extraction" is clicked, then `POST /api/v1/extract` is called, the button disables, and on 200 each entity row shows type chip, value, and confidence | Component test + MSW mock | - [ ] |
| 4 | portal-extraction-page | Playground Tab — Real-time Extraction | Playground shows spinner in results panel during in-flight request | Given a request is in-flight, when the results panel renders, then a spinner is visible and no previous results are shown | Component test: loading state | - [ ] |
| 5 | portal-extraction-page | Playground Tab — Real-time Extraction | Playground shows model version from response | Given the extraction response includes `model_version: "3"`, when the result renders, then the input card header label reads "model v3 · serving" | Component test: model version label | - [ ] |
| 6 | portal-extraction-page | Playground Tab — Real-time Extraction | Empty textarea prevents submission | Given the textarea is empty, when "Run extraction" is clicked, then no `POST /api/v1/extract` request is sent | Component test: empty guard | - [ ] |
| 7 | portal-extraction-page | Batch Runs Tab — Batch Extraction Management | Batch Runs tab lists existing runs | Given the user switches to Batch Runs tab, when the tab mounts, then each batch run appears as a card showing ID, status pill, progress bar, and footer metadata | Component test: run list render | - [ ] |
| 8 | portal-extraction-page | Batch Runs Tab — Batch Extraction Management | Selecting a batch run shows detail | Given multiple run cards, when the user clicks a card, then that card gets a primary border and the right panel shows its total/processed/skipped/failed stats | Component test: run selection | - [ ] |
| 9 | portal-extraction-page | Batch Runs Tab — Batch Extraction Management | Triggering a new batch run | Given the Batch Runs tab is active, when the user clicks "New batch run", then `POST /api/v1/extract-batch` is sent, the new run appears at the top of the list with status "queued", and it is auto-selected | Component test + MSW mock | - [ ] |
| 10 | portal-extraction-page | Batch Runs Tab — Batch Extraction Management | In-progress runs poll for status updates | Given a run with status "running", when the tab is mounted, then `GET /api/v1/extract-batch/{run_id}` is called every 3 seconds, and polling stops when the run reaches a terminal state | Component test: polling with fake timers | - [ ] |
| 11 | portal-extraction-page | Batch Runs Tab — Batch Extraction Management | Status pills use correct visual styles | Given runs with statuses "completed", "running", "queued", and "failed", when the list renders, then each status pill uses the correct color token | Component test: pill style assertions | - [ ] |
| 12 | portal-extraction-page | Entity Review Tab — Entity Listing and Review | Entity Review tab loads entities with default filter | Given the user switches to Entity Review tab, when the tab mounts, then `GET /api/v1/entities` is called with no reviewStatus param and all entities are shown; "all" pill is active | Component test: initial load | - [ ] |
| 13 | portal-extraction-page | Entity Review Tab — Entity Listing and Review | Changing filter re-fetches entities | Given the Entity Review tab is showing all entities, when the user clicks "unreviewed", then `GET /api/v1/entities?reviewStatus=unreviewed` is called and the table updates | Component test: filter change | - [ ] |
| 14 | portal-extraction-page | Entity Review Tab — Entity Listing and Review | Entity rows display type chip, value, confidence, and review status | Given an entity with type "B-ORG", value "Acme Corp", confidence 0.998, review_status "unreviewed", from "invoice-2026-00417.pdf", when the table renders, then all four columns show the correct values | Component test: row render | - [ ] |
| 15 | portal-extraction-page | Entity Review Tab — Entity Listing and Review | Confirming an entity updates its review status optimistically | Given an "unreviewed" entity row, when the confirm button is clicked, then `PATCH /api/v1/entities/{id}` is sent with `{review_status: "confirmed"}` and the REVIEW column immediately shows "confirmed" | Component test: optimistic confirm | - [ ] |
| 16 | portal-extraction-page | Entity Review Tab — Entity Listing and Review | Rejecting an entity updates its review status optimistically | Given an "unreviewed" entity row, when the reject button is clicked, then `PATCH /api/v1/entities/{id}` is sent with `{review_status: "rejected"}` and the REVIEW column immediately shows "rejected" | Component test: optimistic reject | - [ ] |
| 17 | portal-extraction-page | Entity Review Tab — Entity Listing and Review | Confidence color coding reflects thresholds | Given entities with confidence 0.94, 0.75, and 0.62, when the table renders, then they use `var(--good)`, `var(--warn)`, and `var(--bad)` respectively | Component test: confidence colors | - [ ] |
| 18 | portal-extraction-page | Entity Review Tab — Entity Listing and Review | Empty entity list shows empty state | Given no entities exist for the current filter, when the table renders, then an empty state message is shown instead of rows | Component test: empty state | - [ ] |

> **Rule:** Every `#### Scenario:` block in every `specs/**/*.md` file for this change
> MUST appear as a row in this table. A missing scenario is a P1 gap that blocks archive.

---

## 2. Hallucination Risk Register

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|-------------------|----------------------|
| 1 | API endpoint shape | AI may call `/api/v1/tenants/{tid}/extract` (the old spec URL) instead of `/api/v1/extract` (the current gateway route) | Grep generated code for any URL containing `tenants` in the extract call path; confirm it routes to `/api/v1/extract` |
| 2 | Optimistic update pattern | AI may await the PATCH response before updating entity row state, violating the optimistic update requirement | Check `useEntities` hook: the row status must update in state *before* the `await authFetch(PATCH)` resolves; test with a delayed mock |
| 3 | Polling teardown | AI may not clear the `setInterval` on component unmount or when all runs reach terminal states, causing memory leaks and stale updates | Verify `useEffect` returns a cleanup that calls `clearInterval`; run the polling test and confirm no interval fires after terminal state |
| 4 | model_version label default | AI may hardcode "model v3" or omit the label when no extraction has been run yet | Check that the label is derived from the last API response's `model_version` field; assert the label updates correctly after a successful extraction |
| 5 | Confidence threshold boundaries | AI may use `>` instead of `>=` at the 0.90 threshold, causing 0.90 to display as `var(--warn)` instead of `var(--good)` | Add a specific test case for confidence exactly equal to 0.90 and assert `var(--good)` |
| 6 | Tab isolation | AI may share fetch state between tabs (e.g., entity list data visible in playground), leaking data between panels | Verify each tab's hook or component unmounts or resets its local state when the tab is deselected |

---

## 3. Pattern & ADR Compliance

| ADR | Decision Summary | Constraint on This Change | Verification Step |
|-----|-----------------|--------------------------|-------------------|
| ADR-001: Tenant Data Isolation | All tenant data is schema-isolated; no cross-tenant leakage | All API calls MUST use `authFetch` (which attaches the JWT) and MUST NOT include a hardcoded tenant ID in the URL | Grep `components/extractions/` for any hardcoded tenant ID or direct `fetch()` calls bypassing `authFetch` |
| ADR-003: Per-Tenant Model Serving | Each tenant's extraction routes to their promoted model via the serving pool | Frontend calls `/api/v1/extract` — the gateway handles routing; frontend MUST NOT attempt to route to a specific model serving URL directly | Confirm no `localhost:8005` or internal model serving URL appears in frontend component code |
| ADR-008: Base Model as Default | If no promoted model, base model (v0) is used; 200 is returned (not 400/404) | Frontend MUST handle `model_version: "0"` and CoNLL entity types (PER, ORG, LOC, MISC) as valid extraction results — no error state for v0 | Test with a mocked response returning `model_version: "0"` and CoNLL types; assert no error UI is shown |

---

## 4. Evidence Requirements

### Functional Evidence

- [ ] Scenario 1 (default tab): Test output showing `ExtractionPage` renders with Playground tab active and "Extraction" heading visible on mount
- [ ] Scenario 2 (tab switch): Test output showing Batch Runs content renders and Playground is absent after clicking "Batch Runs"
- [ ] Scenario 3 (run extraction): Test output showing `POST /api/v1/extract` called with textarea text, button disabled during request, entity rows rendered on 200
- [ ] Scenario 4 (spinner during in-flight): Test output showing spinner visible in results panel while request is in-flight
- [ ] Scenario 5 (model version label): Test output showing label reads "model v3 · serving" when response contains `model_version: "3"`
- [ ] Scenario 6 (empty guard): Test output confirming no API call is made when textarea is empty
- [ ] Scenario 7 (batch run list): Test output showing run cards with ID, status, progress bar, and footer on Batch Runs tab mount
- [ ] Scenario 8 (run selection): Test output showing primary border on selected card and updated detail panel stats
- [ ] Scenario 9 (new batch run): Test output showing `POST /api/v1/extract-batch` called, new run at top of list, auto-selected
- [ ] Scenario 10 (polling): Test output with fake timers showing `GET /api/v1/extract-batch/{id}` called at 3s intervals; interval cleared on terminal state
- [ ] Scenario 11 (status pills): Test output asserting correct color token class on each status pill
- [ ] Scenario 12 (entity load): Test output showing `GET /api/v1/entities` called without reviewStatus param, "all" pill active
- [ ] Scenario 13 (filter change): Test output showing `GET /api/v1/entities?reviewStatus=unreviewed` after clicking "unreviewed"
- [ ] Scenario 14 (entity row): Test output showing all four column values rendered correctly for a known entity fixture
- [ ] Scenario 15 (confirm): Test output showing PATCH called with `{review_status: "confirmed"}` and row status updating optimistically
- [ ] Scenario 16 (reject): Test output showing PATCH called with `{review_status: "rejected"}` and row status updating optimistically
- [ ] Scenario 17 (confidence colors): Test output asserting `var(--good)`, `var(--warn)`, `var(--bad)` for confidences 0.94, 0.75, 0.62 — plus boundary test at exactly 0.90
- [ ] Scenario 18 (empty state): Test output showing empty state message when entity list is empty

### Structural Evidence

- [ ] Code review completed — implementation matches design.md decisions (no undocumented deviations)
- [ ] All ADR compliance steps in Section 3 confirmed ✓
- [ ] No undocumented architectural patterns introduced
- [ ] No AI-invented requirements present in generated code (cross-checked against spec files)

### Edge Case Evidence

- [ ] Risk 1 (API URL): Grep result showing no `/tenants/{id}/extract` in `components/extractions/`
- [ ] Risk 2 (optimistic update): Test with delayed PATCH mock confirms row updates before response resolves
- [ ] Risk 3 (polling teardown): Test confirms `clearInterval` called on unmount and on terminal state
- [ ] Risk 4 (model_version default): Test with `model_version: "0"` response confirms label updates to "model v0 · serving"
- [ ] Risk 5 (confidence boundary): Test with confidence exactly 0.90 asserts `var(--good)` color
- [ ] Risk 6 (tab isolation): Verify no shared state bleeds between tabs when switching

---

## 5. Evidence Log

Record collected evidence here. Every row in Section 1 must have at least one matching
entry. Do not pre-fill — entries must describe real observations.

| # | Evidence Type | Description / Link | Scenario(s) Covered | Collected By | Date |
|---|--------------|-------------------|---------------------|--------------|------|
| 1 | | | | | |
| 2 | | | | | |
| 3 | | | | | |

---

## 6. Audit Record

> ⚠️ **GATE: This section must be completed and signed by a human reviewer before
> `/opsx:archive` is run.** An unsigned or incomplete Audit Record is a hard block on archive.

**Change slug:** portal-extraction-page
**Proposal:** `openspec/changes/portal-extraction-page/proposal.md`
**Spec files reviewed:**
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
<!-- Any observations, caveats, or follow-up items for future changes. -->
