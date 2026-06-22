# Verification Plan

**Change:** annotation-ui-fixes
**Generated:** 2026-06-22
**Status:** 🔴 Incomplete — Evidence Log and Audit Record must be filled by a human reviewer before archive.

---

## 1. Spec Alignment

Map every requirement and every scenario in this change to a testable acceptance criterion.

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | drag-annotation | Multi-Token Drag Span Creation | Drag across tokens creates a multi-token span | Given "PER" is armed and text is "John Smith works here", when the user drags from "John" to "Smith" and releases, then POST /spans is called with char_start:0, char_end:10, entity_type:"PER" and both tokens highlight solid PER color | Browser manual test / integration test | - [ ] |
| 2 | drag-annotation | Multi-Token Drag Span Creation | Drag preview highlights range during drag | Given "ORG" is armed, when the user holds mousedown on "Acme" and hovers over "Corp" without releasing, then both tokens show a drag-preview highlight and no POST request is sent yet | Browser manual test | - [ ] |
| 3 | drag-annotation | Multi-Token Drag Span Creation | Single-click (same token mousedown and mouseup) still creates a single-token span | Given "ORG" is armed and "Acme" is unspanned, when the user clicks "Acme" (mousedown + mouseup on same token), then POST /spans is called with "Acme"'s char range (identical to pre-drag behavior) | Browser manual test / unit test | - [ ] |
| 4 | drag-annotation | Multi-Token Drag Span Creation | Drag while unarmed does not create a span | Given no entity type is armed, when the user drags across tokens, then no POST /spans request is sent and no preview highlight appears | Browser manual test | - [ ] |
| 5 | drag-annotation | Multi-Token Drag Span Creation | Drag ending on an already-confirmed token is blocked | Given "PER" is armed and "John" is already a confirmed span, when the user drags a range including "John", then no POST /spans request is sent | Browser manual test | - [ ] |
| 6 | drag-annotation | Multi-Token Drag Span Creation | Drag direction is agnostic (right-to-left = left-to-right) | Given "LOC" is armed, when the user drags from token index 5 to token index 2, then the span covers tokens 2–5 with char_start from token 2 and char_end from token 5 | Browser manual test / unit test | - [ ] |
| 7 | bio-tag-storage | BIO Tag Persistence on Spans | BIO tags are stored when a span is created | Given text "John Smith works here" and entity "PER", when POST /spans is called with char_start:0 char_end:10, then the span row has bio_tags=["B-PER","I-PER"] and the response includes bio_tags | API integration test | - [ ] |
| 8 | bio-tag-storage | BIO Tag Persistence on Spans | Single-token span gets a B-tag only | Given text "Acme Corp" and entity "ORG", when POST /spans is called with char_start:0 char_end:4, then bio_tags=["B-ORG"] | API integration test / unit test | - [ ] |
| 9 | bio-tag-storage | BIO Tag Persistence on Spans | BIO tags are recomputed on entity type retype | Given a span with bio_tags=["B-PER","I-PER"], when PATCH /spans/{id} is called with entity_type:"ORG", then bio_tags updates to ["B-ORG","I-ORG"] | API integration test | - [ ] |
| 10 | bio-tag-storage | BIO Tag Persistence on Spans | Export reads stored bio_tags from spans | Given a document with spans having non-NULL bio_tags, when GET /annotation-export is called, then the JSONL output uses the stored bio_tags values without running _bio_tags() computation | API integration test / log trace | - [ ] |
| 11 | bio-tag-storage | BIO Tag Persistence on Spans | Export falls back to computed BIO for legacy spans with NULL bio_tags | Given a span with bio_tags=NULL, when GET /annotation-export is called, then the export computes BIO correctly using the fallback path and produces correct tags | API integration test | - [ ] |
| 12 | bio-tag-storage | BIO Tag Schema Migration | Migration adds nullable column without data loss | Given an existing spans table with rows, when migration 009 is applied, then all existing rows retain their data with bio_tags=NULL; the migration is reversible | Migration test (apply + downgrade) | - [ ] |
| 13 | portal-annotation | Span Deselection | Clicking an unannotated token closes the span inspector | Given the span inspector is open and no entity type is armed, when the user clicks a token not covered by any span, then the inspector closes and no API request is sent | Browser manual test | - [ ] |
| 14 | portal-annotation | Span Deselection | Clicking unannotated token while armed does not deselect | Given an entity type is armed and the inspector is open, when the user clicks an unannotated token, then span creation proceeds and the inspector is not force-closed | Browser manual test | - [ ] |
| 15 | portal-annotation | Task Display Name | Task queue shows Task N labels | Given three tasks in the queue, when the queue renders, then rows show "Task 1", "Task 2", "Task 3" top-to-bottom; raw doc IDs do not appear as labels | Browser manual test / snapshot | - [ ] |
| 16 | portal-annotation | Task Display Name | Toolbar shows Task N for the selected task | Given the second task in the queue is selected, when the toolbar renders, then the task label reads "Task 2" | Browser manual test | - [ ] |
| 17 | portal-annotation | Layout and Navigation | Default layout renders three columns | Given first-time navigation to /annotation with no localStorage key, when the page mounts, then three columns render and the "Focus" button appears in its inactive state | Browser manual test | - [ ] |
| 18 | portal-annotation | Layout and Navigation | Focus toggle enters fullscreen and hides queue | Given 3-pane mode, when the user clicks the "Focus" button, then the task queue hides, the entity palette floats, the document expands, document.documentElement.requestFullscreen() is called, localStorage is updated, and the button renders active | Browser manual test | - [ ] |
| 19 | portal-annotation | Layout and Navigation | Clicking Focus toggle again exits focus mode | Given focus mode active, when the user clicks the "Focus" button again, then 3-pane layout restores and document.exitFullscreen() is called | Browser manual test | - [ ] |
| 20 | portal-annotation | Layout and Navigation | Browser-native fullscreen exit (Escape) syncs layout state | Given focus mode with fullscreen active, when the user presses Escape (browser exits fullscreen), then the fullscreenchange event fires and layoutMode reverts to 3pane automatically | Browser manual test | - [ ] |
| 21 | portal-annotation | Layout and Navigation | Fullscreen API rejection falls back gracefully | Given the browser blocks requestFullscreen(), when the user clicks Focus, then CSS focus mode activates (queue hidden, palette floating) without an error displayed | Browser manual test (block API via iframe or mock) | - [ ] |
| 22 | portal-annotation | Layout and Navigation | Layout preference is restored on reload | Given localStorage has "focus" stored, when navigating to /annotation, then the workspace renders in focus mode without re-selecting | Browser manual test | - [ ] |
| 23 | portal-annotation | Task Status Lifecycle | First span creation triggers in-progress transition | Given an unannotated task with no confirmed spans, when the first span is created, then PATCH /annotation-tasks/{id} is sent with status:"in-progress" and the queue badge updates | Browser manual test / API trace | - [ ] |
| 24 | portal-annotation | Task Status Lifecycle | Mark Complete button is visible but disabled with no spans | Given a selected task with zero confirmed spans, when the toolbar renders, then the "Mark Complete" button is visible with a distinct border and text (not transparent/invisible) and shows the tooltip on hover | Browser manual test / screenshot | - [ ] |
| 25 | portal-annotation | Task Status Lifecycle | Mark Complete becomes enabled when spans exist | Given a selected task with at least one confirmed span, when the toolbar renders, then the "Mark Complete" button is enabled and styled with the primary action color | Browser manual test | - [ ] |
| 26 | portal-annotation | Task Status Lifecycle | Mark Complete transitions task to completed | Given in-progress task with spans, when the user clicks Mark Complete, then PATCH /annotation-tasks/{id} is sent with status:"completed", the badge updates, and the next non-completed task is selected | Browser manual test / API trace | - [ ] |
| 27 | app-shell | Topbar Layout | Topbar remains visible after scrolling | Given a page with content taller than the viewport, when the user scrolls down past the topbar height, then the topbar remains fixed at the top of the viewport | Browser manual test on Documents or Users page | - [ ] |
| 28 | app-shell | Topbar Layout | screen title matches pathname | Given pathname is /admin/tenants, when the topbar renders, then title reads "Tenants" and path reads "/admin/tenants" | Browser manual test | - [ ] |
| 29 | app-shell | Topbar Layout | role-switcher hidden in production mode | Given NEXT_PUBLIC_DEMO_MODE is not "true", when the topbar renders, then no SA/TA/AN/BU chips are visible | Browser manual test (production env) | - [ ] |
| 30 | app-shell | Topbar Layout | role-switcher visible in demo mode | Given NEXT_PUBLIC_DEMO_MODE="true", when the topbar renders, then four chips are visible | Browser manual test (demo env) | - [ ] |
| 31 | app-shell | Topbar Layout | dark mode toggle switches theme | Given light theme, when the dark mode button is clicked, then useDarkMode().toggle() is called and dark class is applied | Browser manual test | - [ ] |
| 32 | app-shell | Topbar Layout | search placeholder is non-interactive | Given the topbar is rendered, when the user clicks the search area, then no dialog opens | Browser manual test | - [ ] |

> **Rule:** Every `#### Scenario:` block in every `specs/**/*.md` file for this change MUST appear as a row in this table. A missing scenario is a P1 gap that blocks archive.

---

## 2. Hallucination Risk Register

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|-------------------|----------------------|
| 1 | Drag state management | AI may implement drag as a CSS text-selection override (using `window.getSelection()`) instead of token-level mousedown/mouseEnter/mouseup state, producing incorrect char offsets | Verify that drag logic reads from `tokenMap[index].charStart/charEnd` (not from a DOM selection range) and that char offsets match the whitespace-split tokenizer |
| 2 | BIO tag computation at write time | AI may compute BIO tags from the request body alone (treating the single span's char range as if tokens start at 0) rather than querying document_text_spans for the full text and computing the correct absolute token indices | Confirm that the spans.py POST handler queries document_text_spans for the document's stored text before computing bio_tags; verify with a span that does not start at char_start=0 |
| 3 | Export fallback for NULL bio_tags | AI may skip the NULL check and pass bio_tags=None to a function that expects a list, raising a TypeError at export time | Check export.py for an explicit `if bio_tags is not None:` guard (or equivalent) before using stored tags; test with a NULL-bio_tags span via the export endpoint |
| 4 | Fullscreen API Escape key conflict | AI may wire the Escape key handler for DISARM to also exit fullscreen, or the fullscreenchange handler to also dispatch DISARM — creating double-firing on Escape | Verify that DISARM (Escape keydown listener) and fullscreenchange listener are separate event handlers and do not call each other; test Escape in focus mode to confirm only DISARM fires, and that browser-native fullscreen exit only toggles layoutMode |
| 5 | AppShell height chain break on non-annotation pages | AI may change `height: 100vh` correctly on AppShell but forget that other pages rely on the main element for scrolling — and may add `overflow: hidden` to main accidentally | Confirm main retains `overflow: auto`; manually scroll a long list page (e.g. Documents) to verify content is still accessible below the fold |
| 6 | Task index calculation when tasks are filtered | AI may compute task index from the unfiltered `allTasks` list instead of the filtered `filteredTasks` list, causing "Task 3" to appear for a task at position 1 in the visible queue | Test as an `annotator` user who can only see 2 of 5 tasks — verify the visible tasks are "Task 1" and "Task 2", not "Task 3" and "Task 5" |
| 7 | bio_tags column in tenant_template vs public schema | AI may target the wrong schema in the migration (e.g. `public.spans` instead of `tenant_template.spans`) | Read the generated migration file and confirm it targets `tenant_template.spans`; run `\d tenant_template.spans` in psql after migration |

---

## 3. Pattern & ADR Compliance

| ADR | Decision Summary | Constraint on This Change | Verification Step |
|-----|-----------------|--------------------------|-------------------|
| ADR-001-tenant-data-isolation | All tenant data lives in per-tenant Postgres schemas; no cross-tenant data access | BIO migration must target `tenant_template.spans`; spans.py must use the per-tenant schema variable (`_schema(tenant_id)`) when querying document_text_spans | Inspect migration 009 — confirm it targets `tenant_template.spans`. Inspect the bio_tags computation in spans.py — confirm it uses `_schema(tenant_id)` for the text query |
| ADR-004-openspec-governance | All changes must follow the OpenSpec artifact workflow | This change is tracked with proposal, design, specs, verification, tasks artifacts | Confirm all artifacts exist and are linked in this change directory before archive |
| ADR-005-opencode-agent-boundaries | Agent-generated code must not touch gateway auth, shared middleware, or infra outside defined scope | No changes to gateway, auth middleware, or shared services | Inspect git diff — confirm changes are scoped to portal components, annotation_service/api/v1/, and alembic/versions/ only |

---

## 4. Evidence Requirements

### Functional Evidence

- [ ] Scenario 1 (drag multi-token span): Browser test showing drag from "John" to "Smith" creates a span with char_start:0, char_end:10 and both tokens highlight
- [ ] Scenario 2 (drag preview): Browser test showing live preview highlights during drag before mouseup
- [ ] Scenario 3 (single-click preserved): Browser test showing single-token click still creates a single-token span
- [ ] Scenario 4 (drag unarmed blocked): Browser test showing drag with no armed entity type produces no span and no highlight
- [ ] Scenario 5 (drag over confirmed blocked): Browser test showing drag range including a confirmed token is rejected
- [ ] Scenario 6 (drag direction agnostic): Browser test or unit test showing right-to-left drag covers the same range as left-to-right
- [ ] Scenario 7 (bio_tags stored on create): API test or DB query showing new span row has bio_tags=["B-PER","I-PER"] after POST
- [ ] Scenario 8 (single token B-tag): API test showing bio_tags=["B-ORG"] for a single-token span
- [ ] Scenario 9 (bio_tags recomputed on retype): API test showing PATCH updates bio_tags to new entity type prefix
- [ ] Scenario 10 (export reads stored tags): API integration test confirming export uses stored bio_tags (add a log or counter to verify the fallback path is not taken)
- [ ] Scenario 11 (export NULL fallback): API test with a manually nulled bio_tags span — confirm export output matches expected BIO tags
- [ ] Scenario 12 (migration non-breaking): Migration apply + downgrade run confirming no data loss and correct column state
- [ ] Scenario 13 (deselect on unannotated token click): Browser test showing inspector closes on click of unspanned token
- [ ] Scenario 14 (armed mode preserves priority over deselect): Browser test showing click-while-armed triggers span creation, not deselect
- [ ] Scenario 15 (Task N queue labels): Browser screenshot showing "Task 1", "Task 2" etc. in the queue sidebar
- [ ] Scenario 16 (Task N toolbar label): Browser test showing toolbar reads "Task 2" when second task is selected
- [ ] Scenario 17 (default 3-pane layout): Browser test on first load confirming three columns render and Focus button shows inactive
- [ ] Scenario 18 (Focus enters fullscreen): Browser test showing fullscreen activates on toggle, queue hides, palette floats
- [ ] Scenario 19 (Focus toggle exits): Browser test showing toggle reverts to 3-pane and calls exitFullscreen
- [ ] Scenario 20 (browser Escape syncs state): Browser test showing pressing Escape in fullscreen reverts layoutMode to "3pane"
- [ ] Scenario 21 (Fullscreen API rejection graceful): Browser test (mock or iframe) showing CSS focus mode activates without error
- [ ] Scenario 22 (localStorage restored): Browser test showing reload restores focus mode from localStorage
- [ ] Scenario 23 (in-progress transition): Browser test + API trace showing PATCH /annotation-tasks/{id} sent on first span
- [ ] Scenario 24 (Mark Complete visible when disabled): Browser screenshot showing the button is clearly visible with border+text when confirmedCount===0
- [ ] Scenario 25 (Mark Complete enabled with spans): Browser test showing button activates and shows primary color when spans exist
- [ ] Scenario 26 (Mark Complete completes task): Browser test + API trace showing PATCH with status:"completed" and next task auto-selected
- [ ] Scenario 27 (topbar sticky): Browser test on Documents page — scroll to bottom, confirm topbar remains visible
- [ ] Scenario 28 (topbar title): Browser test on /admin/tenants confirming title and path text
- [ ] Scenario 29 (role-switcher hidden): Production env browser check confirming no SA/TA/AN/BU chips
- [ ] Scenario 30 (role-switcher visible): Demo env browser check confirming chips visible
- [ ] Scenario 31 (dark mode toggle): Browser test confirming dark class applied on toggle click
- [ ] Scenario 32 (search placeholder): Browser test confirming no dialog opens on click

### Structural Evidence

- [ ] Code review completed — implementation matches design.md decisions (no undocumented deviations)
- [ ] All ADR compliance steps in Section 3 confirmed ✓
- [ ] No undocumented architectural patterns introduced
- [ ] No AI-invented requirements present in generated code (cross-checked against spec files)

### Edge Case Evidence

- [ ] Risk 1 (drag char offsets from tokenMap): Confirmed drag handler reads tokenMap[index].charStart/charEnd, not DOM selection
- [ ] Risk 2 (BIO computation queries full document text): Confirmed spans.py POST queries document_text_spans before computing bio_tags; tested with non-zero char_start span
- [ ] Risk 3 (NULL bio_tags guard in export): Confirmed export.py has explicit NULL guard; tested export with legacy NULL span
- [ ] Risk 4 (Escape key handlers independent): Confirmed DISARM and fullscreenchange listeners are separate; tested Escape in focus mode
- [ ] Risk 5 (AppShell overflow unchanged): Confirmed main retains overflow:auto; long-list page scrolls correctly
- [ ] Risk 6 (filtered task index): Confirmed annotator user sees "Task 1"/"Task 2" (not higher indices from unfiltered list)
- [ ] Risk 7 (migration targets tenant_template): Confirmed migration 009 targets tenant_template.spans; verified in psql

---

## 5. Evidence Log

Record collected evidence here. Every row in Section 1 must have at least one matching entry. Do not pre-fill — entries must describe real observations.

| # | Evidence Type | Description / Link | Scenario(s) Covered | Collected By | Date |
|---|--------------|-------------------|---------------------|--------------|------|
| 1 | | | | | |
| 2 | | | | | |
| 3 | | | | | |

---

## 6. Audit Record

> ⚠️ **GATE: This section must be completed and signed by a human reviewer before `/opsx:archive` is run.** An unsigned or incomplete Audit Record is a hard block on archive.

**Change slug:** annotation-ui-fixes
**Proposal:** `openspec/changes/annotation-ui-fixes/proposal.md`
**Spec files reviewed:**
- specs/drag-annotation/spec.md
- specs/bio-tag-storage/spec.md
- specs/portal-annotation/spec.md
- specs/app-shell/spec.md

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
