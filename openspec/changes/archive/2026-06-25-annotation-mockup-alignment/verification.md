# Verification Plan

**Change:** annotation-mockup-alignment
**Generated:** 2026-06-25
**Status:** 🔴 Incomplete — Evidence Log and Audit Record must be filled by a human reviewer before archive.

---

## 1. Spec Alignment

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | portal-annotation | Layout and Navigation | Default layout renders three columns | Given an authenticated annotator on first visit, when the page mounts, then a 228px task queue column, a center document column, and a 326px entity panel column are all visible, and the "3-pane" button is in its active state | - [ ] |
| 2 | portal-annotation | Layout and Navigation | Clicking "Focus" button enters CSS focus mode | Given 3-pane mode is active, when the user clicks "Focus", then the task queue is hidden, the document viewer expands to max-width 760px centered, the floating bottom palette appears, requestFullscreen is NOT called, and the preference is written to localStorage | - [ ] |
| 3 | portal-annotation | Layout and Navigation | Clicking "3-pane" button exits focus mode | Given focus mode is active, when the user clicks "3-pane", then the three-column layout is restored and the floating bottom palette is removed from the DOM | - [ ] |
| 4 | portal-annotation | Layout and Navigation | Layout preference is restored on reload | Given "focus" is stored in localStorage under "ner-annotation-layout", when the page loads, then the workspace renders in focus mode without any user interaction | - [ ] |
| 5 | portal-annotation | Task Display Name | Task queue shows document filename | Given the queue contains tasks for "invoice-2026-00417.pdf" and "contract-northwind.pdf", when the queue renders, then "invoice-2026-00417.pdf" and "contract-northwind.pdf" appear as the primary row labels, and no "Task 1"/"Task 2" text appears | - [ ] |
| 6 | portal-annotation | Task Display Name | Toolbar shows document filename for the selected task | Given the user selects the task for "invoice-2026-00417.pdf", when the toolbar renders, then "invoice-2026-00417.pdf" is displayed in JetBrains Mono with a status badge next to it | - [ ] |
| 7 | portal-annotation | Annotation Task Queue | Task row shows filename and document metadata | Given the active document has status "processed" and 12 confirmed spans, when the queue row renders, then the subtitle reads "processed · 12 spans" | - [ ] |
| 8 | portal-annotation | Annotation Task Queue | Active task row is highlighted | Given a task is selected, when the queue renders, then only the selected row has a left border in --color-primary and a soft primary-tinted background; all other rows have no border or tint | - [ ] |
| 9 | portal-annotation | Annotation Task Queue | Annotator sees only assigned tasks | Given an annotator with 2 assigned tasks and 3 assigned to others, when the workspace loads, then exactly 2 task rows are visible | - [ ] |
| 10 | portal-annotation | Annotation Task Queue | Empty queue shows contextual message | Given there are no tasks for the current user, when the workspace loads, then the queue panel displays "No tasks assigned" and a prompt to contact a tenant admin | - [ ] |
| 11 | portal-annotation | Annotation Toolbar | Toolbar renders all elements for an active task | Given "invoice-2026-00417.pdf" is selected with status "in-progress", 3 confirmed and 2 suggested spans, when the toolbar renders, then the filename, status badge, status group showing "in_progress" active with solid primary fill, span counter "3 confirmed · 2 suggested", "✦ Pre-label" button, and layout toggle are all visible | - [ ] |
| 12 | portal-annotation | Annotation Toolbar | Clicking a status button updates the task optimistically | Given an active task with status "in-progress", when the user clicks "completed" in the status group, then PATCH /annotation-tasks/{id} is called with {status: "completed"} and the "completed" button immediately shows solid primary fill | - [ ] |
| 13 | portal-annotation | Annotation Toolbar | Status transition rejected by backend reverts selection | Given a PATCH /annotation-tasks/{id} returns 4xx/5xx, when the request settles, then the status group reverts to the previous active button and a toast displays the error message | - [ ] |
| 14 | portal-annotation | Document Viewer and Token Rendering | Document renders inside a card container | Given a task is selected and document text is loaded, when the document viewer renders, then the token content appears inside a card with border-radius: 16px, box-shadow, and max-width: 680px centered in the column | - [ ] |
| 15 | portal-annotation | Document Viewer and Token Rendering | Confirmed span tokens are highlighted | Given a confirmed span "Acme Corp" (ORG), when the document viewer renders, then "Acme" and "Corp" tokens have the ORG entity color as background | - [ ] |
| 16 | portal-annotation | Document Viewer and Token Rendering | Suggested span tokens show dashed overlay | Given a suggested span "Acme Corp" (ORG), when the document viewer renders, then "Acme" and "Corp" tokens show a dashed border in a muted ORG color, and confirmed spans take precedence if they overlap | - [ ] |
| 17 | portal-annotation | Entity Type Palette and Armed Mode | Palette shows entity types with correct visual elements | Given entity type "vendor_name" with target_table "ORG" and 3 confirmed spans, when the palette renders, then each entity button shows an 11×11px dot with border-radius 3px, the label "vendor_name" in JetBrains Mono, the sub-label "base: ORG", and count "3" right-aligned | - [ ] |
| 18 | portal-annotation | Entity Type Palette and Armed Mode | Armed banner shows instructional text | Given the palette is idle, when the user clicks "vendor_name", then the armed banner appears with the text "Labeling mode · click words to tag as vendor_name", a pulsing dot animation, and an "esc · done" control on the right | - [ ] |
| 19 | portal-annotation | Entity Type Palette and Armed Mode | Escape key disarms via banner | Given "vendor_name" is armed, when the user presses Escape or clicks "esc · done", then the armed type is cleared and the armed banner disappears | - [ ] |
| 20 | portal-annotation | Entity Type Palette and Armed Mode | Clicking the armed chip again disarms it | Given "vendor_name" is armed, when the user clicks the "vendor_name" button again, then the armed type is cleared | - [ ] |
| 21 | portal-annotation | Span Inspector | Clicking a confirmed span opens inspector in right panel (3-pane) | Given a confirmed span "Acme Corp" (ORG) and 3-pane mode is active, when the user clicks "Acme" with no type armed, then the span inspector opens inside the right entity panel (not the center column) and shows a colored chip "Acme Corp" with a 2×2 metadata grid | - [ ] |
| 22 | portal-annotation | Span Inspector | Focus mode inspector renders condensed at fixed position | Given focus mode is active and the user clicks a confirmed-span token, when the inspector mounts, then it renders at position: fixed; top: 140px; right: 30px; width: 290px with backdrop-filter blur, and the header is a single-line format "<span_text> · [charStart, charEnd] · conf <confidence>" | - [ ] |
| 23 | portal-annotation | Span Inspector | Retype chip updates the span | Given the inspector is open for "Acme Corp" (ORG) and the user clicks the "vendor_name" chip, then PATCH /documents/{id}/spans/{span_id} is sent with {entity_type: "vendor_name"}, on success the token highlight changes to vendor_name color, and the inspector closes | - [ ] |
| 24 | portal-annotation | Span Inspector | Delete removes the span | Given the inspector is open for "Acme Corp" and the user clicks "Delete span", then DELETE /documents/{id}/spans/{span_id} is sent, on success (204) the token highlights are removed and the inspector closes | - [ ] |
| 25 | portal-annotation | Pre-labeling and Suggestion Flow | Suggestion panel renders in right panel (3-pane) | Given 3-pane mode and 3 suggested spans from pre-labeling, when the suggestion panel renders, then suggestion cards appear in the right entity panel below the entity palette, and the center column contains no suggestion cards | - [ ] |
| 26 | portal-annotation | Pre-labeling and Suggestion Flow | Pre-label populates suggestion cards | Given no existing suggestions, when the user clicks "✦ Pre-label", then POST /documents/{id}/prelabel is sent and on success each returned suggestion appears as a card showing span text, entity type, and confidence | - [ ] |
| 27 | portal-annotation | Pre-labeling and Suggestion Flow | Promote converts a suggestion to a confirmed span | Given a suggestion card for "Acme Corp" (vendor_name, suggest_id "s-1"), when the user clicks "Promote", then POST /documents/{id}/spans/promote/s-1 is sent and on success (201) the confirmed span replaces the suggestion in the viewer and the card is removed | - [ ] |
| 28 | portal-annotation | Pre-labeling and Suggestion Flow | Dismiss removes suggestion locally | Given a suggestion card for "Acme Corp", when the user clicks "✕", then the card is removed from the panel, the dashed-border token highlight is removed from the document viewer, and no API request is sent | - [ ] |
| 29 | portal-annotation | Task Status Lifecycle | First span creation triggers in-progress transition | Given an active task with status "unannotated" and no confirmed spans, when the user creates the first confirmed span (token click, drag, or promote), then PATCH /annotation-tasks/{id} is sent with {status: "in-progress"} and the toolbar status badge updates | - [ ] |
| 30 | portal-annotation | Task Status Lifecycle | In-progress transition fires only once per session | Given an active task with status "unannotated", when the user creates multiple spans in the same session, then the PATCH in-progress request is sent exactly once across all span creation events | - [ ] |
| 31 | portal-annotation | Focus Mode Entity Palette | Bottom palette renders in focus mode | Given focus mode is active, when the layout renders, then a fixed bottom-center pill is visible containing the label "LABEL AS", one chip per entity type (colored dot + name + count), and a "✦ Pre-label" button | - [ ] |
| 32 | portal-annotation | Focus Mode Entity Palette | Bottom palette is hidden in 3-pane mode | Given 3-pane mode is active, when the layout renders, then the bottom-center fixed pill is not present in the DOM | - [ ] |
| 33 | portal-annotation | Focus Mode Entity Palette | Arming from bottom palette triggers armed banner | Given focus mode is active, when the user clicks an entity chip in the bottom palette, then the entity type becomes armed and the armed banner appears below the toolbar with instructional text | - [ ] |

---

## 2. Hallucination Risk Register

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|-------------------|----------------------|
| 1 | Task filename field | AI may invent a `document_name` or `doc_title` field instead of `filename`, or read from a nested object | Confirm the `AnnotationTask` TypeScript type uses exactly `filename: string` and that TaskQueue.tsx reads `task.filename`, not a derived or nested value |
| 2 | Task queue subtitle format | AI may format the subtitle as "12 spans · processed" or "status: processed" instead of the exact "processed · 12 spans" format | Search for the subtitle string in TaskQueue.tsx and confirm it matches `"${task.document_status} · ${task.span_count} spans"` |
| 3 | SpanInspector column placement | AI may leave SpanInspector in the center document column even while saying it moved it, or add it to both columns | Inspect AnnotationPage.tsx JSX structure — SpanInspector must be a child of the right-panel div in 3-pane mode, not the center-column div |
| 4 | Focus mode inspector format | AI may apply the condensed format to both 3-pane and focus modes, or keep the 2×2 grid in focus mode | Test the inspector in both layout modes: 2×2 grid in 3-pane, single-line header in focus mode |
| 5 | Armed banner text template | AI may render just the entity type name without the "Labeling mode · click words to tag as" prefix, or use the entity description instead | Assert the exact string in ArmedBanner tests or render output |
| 6 | Fullscreen API removal | AI may leave residual `requestFullscreen` calls or `fullscreenchange` listeners | `grep -r "requestFullscreen\|exitFullscreen\|fullscreenchange" src/portal/src/components/annotation/` — must return zero results |
| 7 | Status button active style | AI may use a CSS variable that resolves to something close to primary but is actually `--color-surface-overlay`, or confuse the active/inactive states | Visually confirm in the browser that the active status button has a clearly filled primary background (`var(--primary)` or equivalent), not a subtle overlay |

---

## 3. Pattern & ADR Compliance

| ADR | Decision Summary | Constraint on This Change | Verification Step |
|-----|-----------------|--------------------------|-------------------|
| ADR-001 | Tenant data isolation via separate DB schemas | Task queue filtering by `annotator_user_id` must remain — annotators must NOT see tasks from other tenants or other users within the same tenant | Confirm `filteredTasks` filter in AnnotationPage.tsx still applies `user.role === "annotator"` filter; add/retain test for annotator task visibility |
| ADR-004 | OpenSpec spec-driven governance | All implementation follows the spec artifacts created in this change | Confirm implementation tasks reference spec scenarios; no code changes without a spec-backed requirement |
| ADR-005 | OpenCode agent permission boundaries | Frontend-only edits; no infrastructure changes without explicit approval | Confirm no changes to docker-compose.yml, gateway infrastructure, or deployment configuration other than the gateway annotation-task response shape |

---

## 4. Evidence Requirements

### Functional Evidence

- [ ] Scenario 1 (Default layout): Test or browser screenshot confirms three columns render with "3-pane" active on first visit
- [ ] Scenario 2 (Focus button): Test confirms task queue hidden, 760px max-width, bottom palette visible, requestFullscreen NOT called, localStorage updated
- [ ] Scenario 3 (3-pane button from focus): Test confirms layout reverts to three columns and bottom palette is removed
- [ ] Scenario 4 (Preference restore): Test simulates localStorage with "focus" value and confirms focus mode on mount
- [ ] Scenario 5 (Filename in queue): Test asserts task row primary label matches `task.filename`, not "Task N"
- [ ] Scenario 6 (Filename in toolbar): Test asserts toolbar shows "invoice-2026-00417.pdf" for the selected task
- [ ] Scenario 7 (Queue subtitle): Test asserts subtitle reads "processed · 12 spans" given `document_status: "processed"` and `span_count: 12`
- [ ] Scenario 8 (Active row highlight): Test asserts selected row has left border; other rows do not
- [ ] Scenario 9 (Annotator filtering): Existing test or new test confirms annotator sees only their assigned tasks
- [ ] Scenario 10 (Empty queue): Existing test confirms "No tasks assigned" message
- [ ] Scenario 11 (Toolbar elements): Test confirms all toolbar elements present with correct active state and span counter
- [ ] Scenario 12 (Optimistic status update): Test confirms PATCH is called and button active style updates immediately
- [ ] Scenario 13 (Status revert on error): Test simulates 4xx response and confirms status reverts and toast fires
- [ ] Scenario 14 (Document card): Browser screenshot or snapshot test confirms card wrapper with border-radius, shadow, max-width 680px
- [ ] Scenario 15 (Confirmed span highlight): Existing test confirms confirmed span tokens have entity color background
- [ ] Scenario 16 (Suggested span dashed): Existing test confirms suggested span tokens have dashed border style
- [ ] Scenario 17 (Entity palette visual): Test confirms dot is 11×11px with border-radius 3px, "base: ORG" sub-label visible, count right-aligned
- [ ] Scenario 18 (Armed banner text): Test asserts banner text equals "Labeling mode · click words to tag as vendor_name" (not entity description)
- [ ] Scenario 19 (Escape disarms): Existing Escape key test confirms armed type cleared and banner gone
- [ ] Scenario 20 (Toggle-off armed chip): Existing test confirms clicking armed chip again disarms
- [ ] Scenario 21 (Inspector in right panel 3-pane): Test confirms SpanInspector is rendered as child of right entity panel, not center column
- [ ] Scenario 22 (Focus inspector condensed): Test confirms inspector renders single-line header format in focus mode at fixed top: 140px right: 30px
- [ ] Scenario 23 (Retype chip): Existing test confirms PATCH is sent and inspector closes on success
- [ ] Scenario 24 (Delete span): Existing test confirms DELETE is sent and inspector closes on success
- [ ] Scenario 25 (Suggestion panel placement): Test confirms SuggestionPanel is a child of the right-panel div, not center column
- [ ] Scenario 26 (Pre-label populates): Existing test confirms POST /prelabel is sent and suggestion cards appear
- [ ] Scenario 27 (Promote): Existing test confirms POST /promote is sent and suggestion card removed
- [ ] Scenario 28 (Dismiss): Existing test confirms no API call and suggestion removed from DOM
- [ ] Scenario 29 (In-progress transition): Existing test confirms PATCH in-progress fires on first span creation
- [ ] Scenario 30 (In-progress fires once): Existing test confirms PATCH fires only once per session across multiple span creations
- [ ] Scenario 31 (Focus palette renders): Test confirms FocusPalette is in DOM with "LABEL AS" label, entity chips, pre-label button
- [ ] Scenario 32 (Focus palette hidden in 3-pane): Test confirms FocusPalette is not in DOM in 3-pane mode
- [ ] Scenario 33 (Arm from focus palette): Test confirms clicking focus palette chip arms entity type and banner appears

### Structural Evidence

- [ ] Code review completed — implementation matches design.md decisions (no undocumented deviations)
- [ ] All ADR compliance steps in Section 3 confirmed ✓
- [ ] No undocumented architectural patterns introduced
- [ ] No AI-invented requirements present in generated code (cross-checked against spec files)

### Edge Case Evidence

- [ ] Risk 1 (filename field): Confirmed `task.filename` is the field read, not an invented name — checked in TaskQueue.tsx and AnnotationToolbar.tsx
- [ ] Risk 2 (subtitle format): Confirmed subtitle matches `"${task.document_status} · ${task.span_count} spans"` — checked in TaskQueue.tsx
- [ ] Risk 3 (inspector column): Confirmed SpanInspector JSX is inside right-panel div in AnnotationPage.tsx, not center column div
- [ ] Risk 4 (focus inspector format): Confirmed condensed single-line only in focus mode; 2×2 grid preserved in 3-pane
- [ ] Risk 5 (armed banner text): Confirmed banner renders "Labeling mode · click words to tag as X" — not entity description
- [ ] Risk 6 (fullscreen removal): `grep -r "requestFullscreen\|exitFullscreen\|fullscreenchange" src/portal/src/components/annotation/` returns zero results
- [ ] Risk 7 (status button style): Browser/snapshot confirms active status button has solid primary fill, not a subtle overlay

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

**Change slug:** annotation-mockup-alignment
**Proposal:** `openspec/changes/annotation-mockup-alignment/proposal.md`
**Spec files reviewed:**
- `openspec/changes/annotation-mockup-alignment/specs/portal-annotation/spec.md`

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
