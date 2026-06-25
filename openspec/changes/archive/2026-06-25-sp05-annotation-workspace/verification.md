# Verification Plan

**Change:** sp05-annotation-workspace
**Generated:** 2026-06-24
**Status:** 🔴 Incomplete — Evidence Log and Audit Record must be filled by a human reviewer before archive.

---

## 1. Spec Alignment

Map every requirement and every scenario in this change to a testable acceptance criterion.

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | portal-annotation | Layout and Navigation | Default layout renders three columns | Given an authenticated annotator visits `/annotation` for the first time, when the page mounts, then three columns are visible (task queue 228px, document viewer, entity panel 326px), and the "3-pane" button in the view toggle is in its active state | | - [ ] |
| 2 | portal-annotation | Layout and Navigation | Clicking "Focus" button enters CSS focus mode | Given the workspace is in 3-pane mode, when the user clicks the "Focus" button, then the task queue column is hidden, the document viewer expands, the bottom-center fixed palette appears, the "Focus" button is active, the localStorage key is written, and `requestFullscreen` is NOT called | | - [ ] |
| 3 | portal-annotation | Layout and Navigation | Clicking "3-pane" button exits focus mode | Given the workspace is in focus mode, when the user clicks the "3-pane" button, then the three-column layout is restored, the bottom palette disappears, and the "3-pane" button is active | | - [ ] |
| 4 | portal-annotation | Layout and Navigation | Layout preference is restored on reload | Given the user previously selected focus mode (stored in localStorage), when they navigate to `/annotation`, then the workspace renders in focus mode without re-selection | | - [ ] |
| 5 | portal-annotation | Annotation Toolbar | Toolbar renders all elements for an active task | Given a task is selected with filename "invoice-2026-00417.pdf", status "in_progress", 3 confirmed spans, and 2 suggested spans, when the toolbar renders, then all six elements are visible: filename, status group (in_progress active), span counter "3 confirmed · 2 suggested", Pre-label button, and view-mode toggle | | - [ ] |
| 6 | portal-annotation | Annotation Toolbar | Clicking a status button transitions the task | Given an active task with status "in_progress", when the user clicks "completed" in the status group, then PATCH /annotation-tasks/{id} is sent with `{status:"completed"}`, the "completed" button renders active immediately, and on 200 the task badge shows "completed" | | - [ ] |
| 7 | portal-annotation | Annotation Toolbar | Status transition rejected by backend reverts selection | Given an active task with status "in_progress" and zero confirmed spans, when the user clicks "completed", then PATCH is sent, the API returns 422, the status group reverts to "in_progress" active, and a toast displays the error message | | - [ ] |
| 8 | portal-annotation | Annotation Task Queue | Annotator sees only assigned tasks | Given an annotator with two assigned tasks and three tasks assigned to others, when the annotation workspace loads, then the queue shows exactly two task rows | | - [ ] |
| 9 | portal-annotation | Annotation Task Queue | Task row shows document filename | Given the task queue is populated with tasks, when the queue panel renders, then each row displays the document filename (e.g. "invoice-2026-00417.pdf") and raw document UUID fragments do not appear as the primary label | | - [ ] |
| 10 | portal-annotation | Annotation Task Queue | Selecting a task loads the document | Given at least two tasks in the queue, when the user clicks the second task row, then GET /documents/{id}/text, GET /documents/{id}/spans, and GET /documents/{id}/spans?type=suggested are all fetched for the selected task's document | | - [ ] |
| 11 | portal-annotation | Annotation Task Queue | Empty queue shows contextual message | Given no annotation tasks exist for the current user, when the workspace loads, then the queue panel displays "No tasks assigned" | | - [ ] |
| 12 | portal-annotation | Entity Type Palette and Armed Mode | Palette shows entity types with base label and span count | Given an active document with 3 confirmed "vendor_name" spans and entity type base "ORG", when the entity palette renders, then the vendor_name button shows "vendor_name" as primary label, "base: ORG" as secondary sub-label, and count "3" right-aligned | | - [ ] |
| 13 | portal-annotation | Entity Type Palette and Armed Mode | Clicking a chip arms the entity type and shows animated banner | Given the palette is idle, when the user clicks the "vendor_name" button, then the button renders with an active ring highlight, the armed banner appears with a pulsing dot animation, and an "esc · done" control is visible on the right of the banner | | - [ ] |
| 14 | portal-annotation | Entity Type Palette and Armed Mode | Escape key disarms via banner | Given "vendor_name" is armed and the banner is visible, when the user presses Escape or clicks "esc · done", then the armed type is cleared and the banner disappears | | - [ ] |
| 15 | portal-annotation | Entity Type Palette and Armed Mode | Clicking the armed chip again disarms it | Given "vendor_name" is armed, when the user clicks the "vendor_name" button again, then the armed type is cleared (toggle-off) | | - [ ] |
| 16 | portal-annotation | Span Inspector | Clicking a confirmed span opens the inspector with metadata grid | Given a confirmed span "Acme Corp" (ORG, char_start:0, char_end:9, confidence:1.0, base:ORG) and no armed type, when the user clicks "Acme", then the inspector opens showing a colored chip with "Acme Corp" and a 2×2 grid with char_start:0, char_end:9, confidence:1.0, base:ORG | | - [ ] |
| 17 | portal-annotation | Span Inspector | Retype chips are shown for all entity types | Given the inspector is open for "Acme Corp" (ORG) and the tenant has entity types vendor_name, customer_name, invoice_number, when the REASSIGN TYPE section renders, then one inline chip appears for each entity type (excluding the current type), each with a colored dot and name | | - [ ] |
| 18 | portal-annotation | Span Inspector | Clicking a retype chip updates the span | Given the inspector is open for "Acme Corp" (ORG), when the user clicks the "vendor_name" retype chip, then PATCH /documents/{id}/spans/{span_id} is sent with `{entity_type:"vendor_name"}`, on success the token highlight changes to vendor_name color, and the inspector closes | | - [ ] |
| 19 | portal-annotation | Span Inspector | Delete removes the span | Given the inspector is open for "Acme Corp", when the user clicks "Delete span", then DELETE /documents/{id}/spans/{span_id} is sent, on success (204) token highlights are removed, and the inspector closes | | - [ ] |
| 20 | portal-annotation | Span Inspector | Focus mode inspector renders as fixed glass card | Given the workspace is in focus mode and the user clicks a confirmed-span token, when the inspector mounts, then it renders at position:fixed top:140px right:30px width:290px with backdrop-filter:blur(20px) and background:var(--glass) | | - [ ] |
| 21 | portal-annotation | Pre-labeling and Suggestion Flow | Pre-label populates suggestion cards | Given an active document with no suggested spans, when the user clicks "✦ Pre-label", then POST /documents/{id}/prelabel is sent, and on success each returned suggestion appears as a dashed-border card showing span text, entity type name, and confidence value | | - [ ] |
| 22 | portal-annotation | Pre-labeling and Suggestion Flow | Promote converts a suggestion to a confirmed span | Given a suggestion card for "Acme Corp" (vendor_name, suggest_id "s-1"), when the user clicks "Promote", then POST /documents/{id}/spans/promote/s-1 is sent, on success (201) the token highlight changes to solid vendor_name color, and the suggestion card is removed | | - [ ] |
| 23 | portal-annotation | Pre-labeling and Suggestion Flow | Dismiss removes suggestion locally | Given a suggestion card for "Acme Corp", when the user clicks "✕", then the card is removed from the panel, the dashed-border token highlight disappears, and no API request is sent | | - [ ] |
| 24 | portal-annotation | Pre-labeling and Suggestion Flow | Pre-label button disabled during in-flight request | Given a POST /documents/{id}/prelabel request is in-flight, when the Pre-label button renders, then it is visually disabled and non-interactive until the request settles | | - [ ] |
| 25 | portal-annotation | Focus Mode Entity Palette | Bottom palette renders in focus mode | Given the workspace is in focus mode, when the layout renders, then a horizontal pill container appears at position:fixed bottom:28px left:50% transform:translateX(-50%) containing entity type chips (dot + name + count) and a "✦ Pre-label" button | | - [ ] |
| 26 | portal-annotation | Focus Mode Entity Palette | Bottom palette is hidden in 3-pane mode | Given the workspace is in 3-pane mode, when the layout renders, then the bottom-center fixed pill is not present in the DOM | | - [ ] |
| 27 | portal-annotation | Focus Mode Entity Palette | Arming from the bottom palette works identically | Given the workspace is in focus mode, when the user clicks an entity type chip in the bottom palette, then the entity type becomes armed, the armed banner appears below the toolbar, and token clicks create spans for that entity type | | - [ ] |

---

## 2. Hallucination Risk Register

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|-------------------|----------------------|
| 1 | View-mode toggle implementation | AI may implement a single toggle button whose label changes between "3-pane" and "Focus", following the old spec rather than the mockup-specified radio group | Inspect the rendered toolbar: two separate buttons labeled "3-pane" and "Focus" must always be visible simultaneously in the view-mode control |
| 2 | Fullscreen API usage | AI may call `document.documentElement.requestFullscreen()` when "Focus" is clicked, following the old spec (Design §Decision 1 explicitly removes this) | Inspect the event handler for the Focus button — grep for `requestFullscreen` in the annotation page/component files; it must not be present |
| 3 | Status group optimistic-update/revert | AI may only update state on success, not optimistically — or may fail to revert state on a 422 response, leaving the status group in an incorrect state | Simulate a 422 response from the mock API for the completed status transition; verify the status group reverts to the previous value and a toast is shown |
| 4 | Span inspector retype interaction | AI may implement a `<select>` dropdown for retype (old spec pattern) instead of inline chip buttons as specified in the mockup | Inspect the span inspector component: retype must render as individual `<button>` chips in a wrapping flex container, not as a `<select>` or dropdown menu |
| 5 | "Task N" label removal | AI may retain "Task N" ordinal labels (from the old spec) alongside or instead of document filenames | Grep for `Task 1`, `Task 2`, or ordinal-generation code (`Task ${index + 1}`) in the annotation components; none should appear in task row or toolbar rendering |
| 6 | Focus mode bottom palette position | AI may place the floating palette on the right side (old spec's fixed right panel) rather than the bottom-center strip specified in the mockup | Inspect the CSS/style props for the focus-mode entity palette: must be `position:fixed; bottom:28px; left:50%; transform:translateX(-50%)`, not `top: 140px; right: 30px` |
| 7 | Entity palette base-type sub-label | AI may omit the `base: <type>` sub-label in entity type buttons, rendering only the entity name | For each entity type button rendered in the palette (both 3-pane and focus mode), verify a secondary element showing `base: <base_type>` is present in the DOM |

---

## 3. Pattern & ADR Compliance

| ADR | Decision Summary | Constraint on This Change | Verification Step |
|-----|-----------------|--------------------------|-------------------|
| ADR-004 — OpenSpec SDD Governance | All changes require the full proposal → design → spec → tasks → evidence → archive pipeline | This change must have all required artifacts completed before archive; implementation evidence must be logged in Section 5 | Confirm all artifact files exist and the Evidence Log in Section 5 is populated before running `/opsx:archive` |
| ADR-005 — OpenCode Agent Boundaries | Portal must not call the Python gateway directly; all data flows through Next.js API routes (`/api/v1/…`) | All API calls from the annotation page (spans, tasks, prelabel, entity-types) must go through the Next.js proxy layer, not direct fetch to the Python backend | Grep annotation components for direct gateway URLs (e.g., `localhost:8000`, `:8080`, `/v1/`); none should appear — all calls must use `/api/v1/` relative paths |

---

## 4. Evidence Requirements

### Functional Evidence

- [ ] Scenario 1 (Default 3-pane layout): Screenshot or Playwright test showing three-column layout on first load with "3-pane" button active
- [ ] Scenario 2 (Focus mode entry): Screenshot or Playwright test showing focus layout after clicking "Focus" — task queue absent, bottom palette visible, no fullscreen call in console
- [ ] Scenario 3 (Focus → 3-pane exit): Screenshot or Playwright test showing restored three-column layout after clicking "3-pane"
- [ ] Scenario 4 (Layout preference restored): Playwright test setting localStorage to focus mode then reloading — workspace renders in focus mode
- [ ] Scenario 5 (Toolbar elements): Screenshot of toolbar with all six elements identified and labeled correctly
- [ ] Scenario 6 (Status button transition): API trace or test showing PATCH /annotation-tasks/{id} sent with `{status:"completed"}` and status button updating optimistically
- [ ] Scenario 7 (422 revert): Test or manual trace showing status group reverts to previous value after 422 response with toast visible
- [ ] Scenario 8 (Annotator task filter): Test output showing annotator role receives only their assigned tasks from the queue
- [ ] Scenario 9 (Filename display): Screenshot of task queue rows showing document filenames — no "Task N" ordinal labels
- [ ] Scenario 10 (Task selection loads document): Network trace showing all three GET requests fired on task row click
- [ ] Scenario 11 (Empty queue message): Screenshot showing "No tasks assigned" message when task list is empty
- [ ] Scenario 12 (Palette base-type sub-label): Screenshot of entity palette showing each entity type with name + "base: X" sub-label + count
- [ ] Scenario 13 (Armed banner with pulse): Screenshot or video showing pulsing dot animation and "esc · done" control in armed banner
- [ ] Scenario 14 (Escape disarms): Test confirming Escape key and "esc · done" click both clear armed state and dismiss banner
- [ ] Scenario 15 (Chip toggle disarms): Test confirming clicking an armed chip again clears the armed state
- [ ] Scenario 16 (Inspector metadata grid): Screenshot of span inspector showing colored chip and 2×2 grid with all four fields
- [ ] Scenario 17 (Retype chips present): Screenshot of REASSIGN TYPE section showing one chip per entity type (excluding current)
- [ ] Scenario 18 (Retype updates span): API trace showing PATCH request with new entity_type and token color change in DOM
- [ ] Scenario 19 (Delete span): API trace showing DELETE request and token highlight removal
- [ ] Scenario 20 (Focus mode inspector position): Screenshot or DOM inspection confirming `position:fixed; top:140px; right:30px; width:290px` with glass background
- [ ] Scenario 21 (Pre-label suggestion cards): Screenshot showing dashed-border suggestion cards with text, entity type, and confidence after pre-label
- [ ] Scenario 22 (Promote suggestion): API trace showing promote request and token style change from dashed to solid
- [ ] Scenario 23 (Dismiss suggestion): Test confirming no API call on dismiss and card + highlight removal
- [ ] Scenario 24 (Pre-label button disabled): Screenshot or test showing Pre-label button in disabled state during in-flight request
- [ ] Scenario 25 (Bottom palette in focus mode): Screenshot of focus mode showing bottom-center pill with entity chips and Pre-label button
- [ ] Scenario 26 (Bottom palette absent in 3-pane): DOM inspection confirming the bottom-center pill is not in the DOM in 3-pane mode
- [ ] Scenario 27 (Arming from bottom palette): Test showing armed banner appears after clicking entity chip in the bottom palette

### Structural Evidence

- [ ] Code review completed — implementation matches design.md decisions (no undocumented deviations)
- [ ] All ADR compliance steps in Section 3 confirmed ✓
- [ ] No undocumented architectural patterns introduced
- [ ] No AI-invented requirements present in generated code (cross-checked against spec files)

### Edge Case Evidence

- [ ] Risk 1 (radio group): Two separate "3-pane" and "Focus" buttons confirmed simultaneously visible in the toolbar DOM — no single-toggle pattern present
- [ ] Risk 2 (no Fullscreen API): `requestFullscreen` confirmed absent from annotation component files via grep
- [ ] Risk 3 (status group revert on 422): 422 simulation confirmed status group reverts and toast appears
- [ ] Risk 4 (inline chips not dropdown): REASSIGN TYPE confirmed as flex-wrapped `<button>` chips — no `<select>` in inspector component
- [ ] Risk 5 (no Task N labels): Grep for ordinal task label code confirmed zero matches in annotation components
- [ ] Risk 6 (bottom palette position): CSS/style props for focus-mode palette confirmed as `bottom:28px; left:50%; transform:translateX(-50%)`
- [ ] Risk 7 (base-type sub-label): `base:` sub-label confirmed present in entity type button DOM for both 3-pane and focus mode renders

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

**Change slug:** sp05-annotation-workspace
**Proposal:** `openspec/changes/sp05-annotation-workspace/proposal.md`
**Spec files reviewed:**
- specs/portal-annotation/spec.md

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
