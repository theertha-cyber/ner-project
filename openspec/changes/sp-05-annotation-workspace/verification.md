# Verification Plan

**Change:** sp-05-annotation-workspace
**Generated:** 2026-06-17
**Status:** 🔴 Incomplete — Evidence Log and Audit Record must be filled by a human reviewer before archive.

---

## 1. Spec Alignment

Map every requirement and every scenario in this change to a testable acceptance criterion.

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | portal-annotation | Layout and Navigation | Default layout renders three columns | Given an annotator navigates to `/annotation` with no localStorage preference, when the page loads, then three columns (task queue, document viewer, entity palette) are visible and the layout toggle shows "3-pane" | Manual browser check | - [ ] |
| 2 | portal-annotation | Layout and Navigation | Focus mode hides queue and floats palette | Given 3-pane mode is active, when the user switches to "Focus", then the task queue is hidden, the entity palette renders fixed at `top: 140px; right: 30px`, and localStorage is updated | Manual browser check | - [ ] |
| 3 | portal-annotation | Layout and Navigation | Layout preference is restored on reload | Given the user previously set "Focus" mode in localStorage, when they navigate to `/annotation`, then focus mode is active without user interaction | Manual browser check / localStorage inspection | - [ ] |
| 4 | portal-annotation | Annotation Task Queue | Annotator sees only assigned tasks | Given an annotator with 2 assigned tasks and 3 tasks assigned to others, when the workspace loads, then exactly 2 task rows appear in the queue | API mock / integration test | - [ ] |
| 5 | portal-annotation | Annotation Task Queue | Tenant admin sees all tasks | Given a tenant_admin with 5 tasks across the tenant, when the workspace loads, then all 5 task rows appear | API mock / integration test | - [ ] |
| 6 | portal-annotation | Annotation Task Queue | Selecting a task loads the document | Given ≥2 tasks in the queue, when the user clicks the second task row, then `GET /documents/{id}/text`, `GET /documents/{id}/spans`, and `GET /documents/{id}/spans?type=suggested` are called for that document and the viewer updates | Network trace / integration test | - [ ] |
| 7 | portal-annotation | Annotation Task Queue | Empty queue shows contextual message | Given no annotation tasks for the current user, when the workspace loads, then "No tasks assigned" is displayed in the queue panel | Manual browser check | - [ ] |
| 8 | portal-annotation | Document Viewer and Token Rendering | Confirmed span tokens are highlighted | Given a document with "Acme Corp" (ORG) and "John Doe" (PER) as confirmed spans, when the viewer renders, then those tokens have the respective entity color backgrounds | Visual regression / manual check | - [ ] |
| 9 | portal-annotation | Document Viewer and Token Rendering | Suggested span tokens show dashed overlay | Given a suggested span for "Acme Corp" (ORG), when the viewer renders, then those tokens have a dashed border in a muted ORG color | Visual regression / manual check | - [ ] |
| 10 | portal-annotation | Document Viewer and Token Rendering | Unannotated tokens render without highlight | Given a token "hired" not covered by any span, when the viewer renders, then "hired" has default text color and no background highlight | Visual regression / manual check | - [ ] |
| 11 | portal-annotation | Entity Type Palette and Armed Mode | Palette shows entity types with span counts | Given 3 PER spans and 1 ORG span on the active document, when the palette renders, then PER shows count 3, ORG shows count 1, other types show count 0 | Unit test on count computation | - [ ] |
| 12 | portal-annotation | Entity Type Palette and Armed Mode | Clicking a chip arms the entity type | Given no type is armed, when the user clicks "PER", then the PER chip shows an active ring and the armed-mode banner appears | Manual browser check | - [ ] |
| 13 | portal-annotation | Entity Type Palette and Armed Mode | Escape key disarms the palette | Given "PER" is armed, when the user presses Escape, then the armed type is cleared and the banner disappears | Manual browser check | - [ ] |
| 14 | portal-annotation | Entity Type Palette and Armed Mode | Clicking the armed chip again disarms it | Given "PER" is armed, when the user clicks the "PER" chip, then the armed type is cleared | Manual browser check | - [ ] |
| 15 | portal-annotation | Token-Click Span Creation | Clicking a token while armed creates a span | Given "ORG" is armed on "Acme Corp hired John", when the user clicks "Acme", then the token highlights immediately and `POST /documents/{id}/spans` is called with `{entity_type: "ORG", char_start: 0, char_end: 4, text: "Acme"}` | Network trace + visual check | - [ ] |
| 16 | portal-annotation | Token-Click Span Creation | Clicking an already-spanned token while armed does nothing | Given "PER" is armed and "John" is already covered by an ORG span, when the user clicks "John", then no POST request is sent and the ORG color remains | Network trace | - [ ] |
| 17 | portal-annotation | Token-Click Span Creation | API error reverts optimistic span | Given "ORG" is armed and the user clicks a token, when the POST returns a 4xx/5xx, then the token highlight is removed and a toast with the error message is shown | Network mock + visual check | - [ ] |
| 18 | portal-annotation | Token-Click Span Creation | Clicking a token while no type is armed opens the span inspector | Given no type is armed and the user clicks a confirmed-span token, when the click fires, then the span inspector opens for that span | Manual browser check | - [ ] |
| 19 | portal-annotation | Span Inspector | Clicking a confirmed span opens the inspector | Given a confirmed span "John Doe" (PER) at char offsets 10-18 and no type is armed, when the user clicks "John", then the inspector shows entity_type "PER", char_start 10, char_end 18, text "John Doe", confidence 1.0 | Manual browser check | - [ ] |
| 20 | portal-annotation | Span Inspector | Retype updates the span entity type | Given the inspector is open for "John Doe" (PER), when the user selects "ORG" from the retype dropdown, then `PATCH /documents/{id}/spans/{span_id}` is called with `{entity_type: "ORG"}`, the token color updates, and the inspector closes | Network trace + visual check | - [ ] |
| 21 | portal-annotation | Span Inspector | Delete removes the span | Given the inspector is open for "John Doe" (PER), when the user clicks delete, then `DELETE /documents/{id}/spans/{span_id}` is called, the token highlights are removed, and the inspector closes | Network trace + visual check | - [ ] |
| 22 | portal-annotation | Pre-labeling and Suggestion Flow | Pre-label populates the suggestion panel | Given no existing suggestions, when the user clicks "Pre-label", then `POST /documents/{id}/prelabel` is called and returned suggestions appear in the panel with dashed-border token styling | Network trace + visual check | - [ ] |
| 23 | portal-annotation | Pre-labeling and Suggestion Flow | Promote converts a suggestion to a confirmed span | Given a suggested span "Acme Corp" (ORG, suggest_id "s-1"), when the user clicks "Promote", then `POST /documents/{id}/spans/promote/s-1` is called, the dashed styling becomes solid ORG color, and the suggestion row is removed | Network trace + visual check | - [ ] |
| 24 | portal-annotation | Pre-labeling and Suggestion Flow | Dismiss removes the suggestion locally | Given a suggested span "John Doe" (PER) in the panel, when the user clicks "Dismiss", then the suggestion row and dashed token styling are removed with no network request | Network trace (assert no request) + visual check | - [ ] |
| 25 | portal-annotation | Pre-labeling and Suggestion Flow | Pre-label button is disabled during in-flight request | Given a pre-label request is in-flight, when the button renders, then it is visually disabled and non-interactive | Manual browser check / throttled network test | - [ ] |
| 26 | portal-annotation | Task Status Lifecycle | First span creation triggers in-progress transition | Given a task with status `unannotated` and no spans, when the first span is created, then `PATCH /annotation-tasks/{id}` is called with `{status: "in-progress"}` and the queue badge updates | Network trace | - [ ] |
| 27 | portal-annotation | Task Status Lifecycle | Mark Complete is disabled with no spans | Given a task with status `in-progress` and zero confirmed spans, when the workspace renders, then the "Mark Complete" button is disabled and its tooltip reads "Add at least one confirmed span before completing" | Manual browser check | - [ ] |
| 28 | portal-annotation | Task Status Lifecycle | Mark Complete transitions task to completed | Given a task with ≥1 confirmed span in `in-progress` status, when the user clicks "Mark Complete", then `PATCH /annotation-tasks/{id}` is called with `{status: "completed"}`, the badge updates, and the next non-completed task is auto-selected | Network trace + visual check | - [ ] |
| 29 | portal-annotation | Char-Offset to Token-Index Conversion | Token index maps to correct char offsets | Given document text "Hello World Foo", when the user clicks token index 1 ("World"), then `char_start = 6` and `char_end = 11` are computed | Unit test on `buildTokenMap()` | - [ ] |
| 30 | portal-annotation | Char-Offset to Token-Index Conversion | Multi-token span covers correct token range | Given a confirmed span with `char_start: 0, char_end: 11` on "Hello World Foo", when the viewer maps the span, then tokens 0 and 1 are highlighted and token 2 is not | Unit test on span-to-token mapping | - [ ] |

---

## 2. Hallucination Risk Register

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|-------------------|----------------------|
| 1 | Char-offset arithmetic | Agent may compute `char_end` as `char_start + token.length - 1` (off-by-one — inclusive vs exclusive) causing span boundary mismatches with the backend | Unit test scenarios 29 and 30; compare against backend annotation export BIO tags for the same document |
| 2 | Optimistic span rollback | Agent may implement optimistic updates without the rollback path, leaving ghost highlights when the API returns an error (scenario 17) | Simulate a network error on `POST /spans` with devtools; confirm the highlight is removed and a toast appears |
| 3 | Multi-token span highlighting | Agent may only highlight the first token of a multi-token span (e.g. only "Acme" but not "Corp") due to incorrect range scan over the tokenMap | Manual test with a confirmed span that spans ≥2 tokens; verify both tokens highlight |
| 4 | Armed-type event listener cleanup | Agent may add the `keydown` Escape listener but omit the cleanup function in `useEffect`, causing stale listeners after route navigation | Navigate away from `/annotation` and back; verify no duplicate Escape handlers accumulate (check devtools event listeners panel) |
| 5 | Entity palette span counts | Agent may count all spans in the system rather than spans for the currently active document only | Switch between two tasks with different span sets; confirm counts update for each document |
| 6 | Task auto-selection on complete | Agent may auto-select the first task in the list (including the just-completed task) rather than the next non-completed task | Complete a task mid-queue; verify the auto-selected task is a non-completed one |

---

## 3. Pattern & ADR Compliance

| ADR | Decision Summary | Constraint on This Change | Verification Step |
|-----|-----------------|--------------------------|-------------------|
| ADR-001: Tenant Data Isolation | All data is isolated per tenant via separate DB schemas | All API calls must use the authenticated tenant's token; no cross-tenant document or span data should appear | Inspect every `authFetch` call in the annotation components — confirm all use the `Authorization: Bearer` header from `useAuth()` |
| ADR-004: OpenSpec Governance | All capability changes go through spec-driven workflow | Implementation must not introduce capabilities beyond what is defined in `specs/portal-annotation/spec.md` | Code review: any UI element or API call not traceable to a SHALL clause in the spec is a violation |
| ADR-005: OpenCode Agent Boundaries | Agent edits scoped to repo; no external system calls during implementation | All file edits must stay within `src/portal/` | Confirm no new files are created outside `src/portal/` during apply |

---

## 4. Evidence Requirements

### Functional Evidence

- [ ] Scenario 1: Browser screenshot showing three-column layout on first load with "3-pane" toggle active
- [ ] Scenario 2: Browser screenshot showing focus mode with floating palette and no task queue column
- [ ] Scenario 3: localStorage `ner-annotation-layout` value set to "focus" verified after reload restores focus mode
- [ ] Scenario 4: Network request to `GET /annotation-tasks` shows only 2 tasks returned for annotator user
- [ ] Scenario 5: Network request to `GET /annotation-tasks` shows all 5 tasks for tenant_admin
- [ ] Scenario 6: Network trace showing three sequential requests (text, spans, spans?type=suggested) on task selection
- [ ] Scenario 7: Browser screenshot showing "No tasks assigned" message in empty queue
- [ ] Scenario 8: Browser screenshot showing ORG and PER color highlights on correct tokens
- [ ] Scenario 9: Browser screenshot showing dashed-border styling on suggested span tokens
- [ ] Scenario 10: Browser screenshot showing unhighlighted token between two spans
- [ ] Scenario 11: Unit test output confirming span count computation (PER=3, ORG=1, others=0)
- [ ] Scenario 12: Browser screenshot showing armed-mode banner and ring highlight on PER chip
- [ ] Scenario 13: Browser recording or screenshot showing banner disappears after Escape key
- [ ] Scenario 14: Browser check showing PER chip de-highlights on second click
- [ ] Scenario 15: Network trace showing `POST /spans` with correct `char_start: 0, char_end: 4` and immediate token highlight before response
- [ ] Scenario 16: Network trace showing zero POST requests when clicking an already-spanned token while armed
- [ ] Scenario 17: Browser check with throttled/errored network showing optimistic highlight removed and error toast displayed
- [ ] Scenario 18: Browser screenshot showing inspector opens when clicking a span token with no armed type
- [ ] Scenario 19: Inspector panel screenshot showing correct entity_type, char_start, char_end, text, confidence values
- [ ] Scenario 20: Network trace showing `PATCH /spans/{id}` with `{entity_type: "ORG"}` and updated token color
- [ ] Scenario 21: Network trace showing `DELETE /spans/{id}` (204) and token de-highlighted
- [ ] Scenario 22: Network trace showing `POST /prelabel` and suggestion panel populated with dashed-border tokens
- [ ] Scenario 23: Network trace showing `POST /spans/promote/s-1` (201) and dashed styling converted to solid
- [ ] Scenario 24: Network trace showing zero requests on dismiss, suggestion row removed from panel
- [ ] Scenario 25: Browser screenshot showing disabled Pre-label button with network throttled (request in-flight)
- [ ] Scenario 26: Network trace showing `PATCH /annotation-tasks/{id}` with `{status: "in-progress"}` on first span creation
- [ ] Scenario 27: Browser screenshot showing disabled "Mark Complete" button with tooltip on zero-span document
- [ ] Scenario 28: Network trace showing `PATCH /annotation-tasks/{id}` with `{status: "completed"}` and next task auto-selected
- [ ] Scenario 29: Unit test output for `buildTokenMap("Hello World Foo")` confirming token 1 → char_start=6, char_end=11
- [ ] Scenario 30: Unit test output confirming span `{char_start:0, char_end:11}` maps to token indices [0,1] only

### Structural Evidence

- [ ] Code review completed — implementation matches design.md decisions (reducer pattern, tokenMap memoization, single keydown listener with cleanup, component directory structure)
- [ ] All ADR compliance steps in Section 3 confirmed ✓
- [ ] No undocumented architectural patterns introduced
- [ ] No AI-invented requirements present in generated code (cross-checked against `specs/portal-annotation/spec.md`)

### Edge Case Evidence

- [ ] Risk 1 (char-offset off-by-one): Unit test output for `buildTokenMap` boundary values confirmed correct; annotation export BIO tags cross-checked for matching document
- [ ] Risk 2 (optimistic rollback): Network error simulation confirmed ghost highlight is removed and toast is shown
- [ ] Risk 3 (multi-token highlight): Manual test with ≥2-token span confirms both tokens highlight
- [ ] Risk 4 (event listener cleanup): DevTools event listener count verified stable after multiple route navigations to/from `/annotation`
- [ ] Risk 5 (entity palette counts): Span counts verified to update correctly when switching between two documents with different span sets
- [ ] Risk 6 (task auto-selection): Task completion mid-queue confirmed auto-selects a non-completed task, not the completed one

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

**Change slug:** sp-05-annotation-workspace
**Proposal:** `openspec/changes/sp-05-annotation-workspace/proposal.md`
**Spec files reviewed:**
- `openspec/changes/sp-05-annotation-workspace/specs/portal-annotation/spec.md`

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
