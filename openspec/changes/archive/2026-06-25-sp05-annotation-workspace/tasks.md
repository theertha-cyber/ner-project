## 1. Layout and View-Mode Toggle

- [x] 1.1 In `AnnotationPage.tsx`: replace the single "Focus" toggle button with a two-button radio group ("3-pane" / "Focus") styled as a pill container using `var(--surface-3)` background, `var(--line)` border, and `border-radius: 9px` with `padding: 3px`; active button gets filled background + shadow
- [x] 1.2 In `AnnotationPage.tsx`: remove any call to `document.documentElement.requestFullscreen()` and `document.exitFullscreen()`, and remove the `fullscreenchange` event listener — focus mode is CSS-only
- [x] 1.3 In `AnnotationPage.tsx`: update the 3-pane grid to `grid-template-columns: 228px 1fr 326px` (left/center/right) and wire the "3-pane" button to set layout to `"3pane"`, "Focus" to `"focus"`; persist to `localStorage` key `"ner-annotation-layout"`
- [x] 1.4 Write a test in `AnnotationPage.test.tsx` (create if absent): verify that clicking "Focus" does not call `requestFullscreen`, task queue column is absent, and the "Focus" button is marked active (scenarios 2, 3)
- [x] 1.5 Write a test: verify that on first mount with no localStorage preference, three columns are visible and the "3-pane" button is active (scenario 1)
- [x] 1.6 Write a test: verify that when localStorage has the focus-mode preference, the workspace renders in focus mode on mount (scenario 4)

## 2. Annotation Toolbar Redesign

- [x] 2.1 Create `src/portal/src/components/annotation/AnnotationToolbar.tsx` with the following slots from left to right: document filename (`JetBrains Mono` font-weight 600 + status badge), status button group (three pill buttons: "pending" / "in_progress" / "completed"), flex spacer, span counter ("N confirmed · N suggested" in `JetBrains Mono` font-size 11px), "✦ Pre-label" button, view-mode toggle (delegated from `AnnotationPage`)
- [x] 2.2 In `AnnotationToolbar.tsx`: implement the status group so clicking a button sends `PATCH /api/v1/annotation-tasks/{id}` with the new status; apply the update optimistically and revert + show a toast on 4xx/5xx
- [x] 2.3 In `AnnotationPage.tsx`: remove the existing "Mark Complete" button; replace with `<AnnotationToolbar>` receiving `task`, `confirmedCount`, `suggestedCount`, `onStatusChange`, `layoutMode`, `onLayoutChange`, `onPrelabel` as props
- [x] 2.4 Write tests in `AnnotationToolbar.test.tsx`: scenario 5 (all six elements visible), scenario 6 (PATCH sent and button goes active optimistically), scenario 7 (PATCH 422 reverts selection and shows toast)

## 3. Armed Banner Update

- [x] 3.1 Create `src/portal/src/components/annotation/ArmedBanner.tsx`: renders a sticky bar below the toolbar with `background: var(--primary-soft)`, `border-bottom: 1px solid var(--primary-line)`, a pulsing dot (`animation: pulse 1.3s infinite`), the armed entity type name and description, and an "esc · done" text button that calls `onDisarm`
- [x] 3.2 In `AnnotationPage.tsx`: replace any existing armed-mode indicator with `<ArmedBanner>` (render only when an entity type is armed); wire Escape key handler to call `onDisarm` on the banner
- [x] 3.3 Add a `@keyframes pulse` CSS definition in the global styles or the component's CSS module (scale 1 → 1.2 → 1 over 1.3s)
- [x] 3.4 Write tests: scenario 13 (banner appears on arm with pulse class present), scenario 14 (Escape and "esc · done" click both clear armed state and dismiss banner)

## 4. Entity Type Palette Redesign

- [x] 4.1 In `EntityPalette.tsx`: update each entity type button to render three elements — (a) a colored dot (`width: 8px; height: 8px; border-radius: 50%`), (b) a flex column with the entity name (`JetBrains Mono` font-weight 600) and a `base: <base_type>` sub-label (`font-size: 9.5px; color: var(--ink-3)`), (c) a right-aligned span count
- [x] 4.2 In `EntityPalette.tsx`: ensure clicking an already-armed chip calls the disarm handler (toggle-off), and clicking an unarmed chip calls the arm handler
- [x] 4.3 Write tests: scenario 12 (base sub-label rendered), scenario 15 (toggle-off behavior)

## 5. Span Inspector Redesign

- [x] 5.1 In `SpanInspector.tsx`: replace the retype `<select>` / dropdown with a flex-wrapped row of inline `<button>` chips (one per entity type, excluding the current type); each chip shows a colored dot + entity type name; clicking sends `PATCH /documents/{id}/spans/{span_id}` with the new entity type
- [x] 5.2 In `SpanInspector.tsx`: update the metadata display from any existing layout to a `display: grid; grid-template-columns: 1fr 1fr` 2×2 grid showing `char_start`, `char_end`, `confidence`, `base` with `JetBrains Mono` labels and values
- [x] 5.3 In `SpanInspector.tsx`: add `animation: popIn 0.25s ease both` to the inspector container; add `@keyframes popIn` (scale from 0.92 → 1, opacity 0 → 1)
- [x] 5.4 In `AnnotationPage.tsx` / focus-mode layout: render `<SpanInspector>` at `position: fixed; top: 140px; right: 30px; width: 290px` with `backdrop-filter: blur(20px)` and `background: var(--glass)` when in focus mode; in 3-pane mode render it as a card within the right panel
- [x] 5.5 Write tests: scenario 16 (metadata 2×2 grid values), scenario 17 (inline retype chips present), scenario 18 (PATCH request and inspector close), scenario 19 (DELETE request and highlight removal), scenario 20 (focus mode inspector position and glass styles)

## 6. Focus Mode Bottom Palette

- [x] 6.1 In `EntityPalette.tsx` (or create `FocusPalette.tsx`): implement a horizontal variant of the palette rendered at `position: fixed; bottom: 28px; left: 50%; transform: translateX(-50%); z-index: 200` with `backdrop-filter: blur(22px) saturate(1.4)` and `background: var(--glass); border: 1px solid var(--glass-line); border-radius: 18px; padding: 9px 11px`; contains a "LABEL AS" label, entity chips (dot + name + count), a vertical divider, and the "✦ Pre-label" button
- [x] 6.2 In `AnnotationPage.tsx`: conditionally render the bottom palette only when `layoutMode === "focus"`; in 3-pane mode render only the right-panel entity palette
- [x] 6.3 Ensure arming from the bottom palette chips sets the same `armedEntityType` state and triggers the armed banner (same behavior as right-panel palette)
- [x] 6.4 Write tests: scenario 25 (bottom palette visible in focus mode with correct elements), scenario 26 (bottom palette absent in 3-pane DOM), scenario 27 (arming from bottom palette shows armed banner)

## 7. Task Queue and Filename Display

- [x] 7.1 In `TaskQueue.tsx`: update each task row to display `task.document_filename` (or the equivalent filename field from the API response) as the primary label; remove any `Task ${index + 1}` ordinal label generation
- [x] 7.2 In `AnnotationToolbar.tsx`: display the active task's `document_filename` in the filename slot, not an ordinal label
- [x] 7.3 Verify that the annotation-task list API response (`GET /api/v1/annotation-tasks`) includes a `document_filename` field; if not, add it to the backend response in `src/gateway/api/v1/` (small backend addition)
- [x] 7.4 Write tests: scenario 8 (annotator filter), scenario 9 (filename label visible, no "Task N" pattern), scenario 10 (three GET requests on task selection), scenario 11 (empty queue message)

## 8. Pre-labeling and Suggestion Panel

- [x] 8.1 In `SuggestionPanel.tsx`: update suggestion card layout to render as a `border: 1px dashed var(--line); border-radius: 12px` card with a colored dot, the matched text, entity type name + confidence (e.g. "vendor_name · conf 0.85"), and "Promote" / "✕" buttons; "Promote" uses the primary button style, "✕" uses the dismiss style
- [x] 8.2 Update the "✦ Pre-label" button in `AnnotationToolbar.tsx` (or `AnnotationPage.tsx`) to be disabled (`pointer-events: none; opacity reduced`) while a pre-label request is in-flight
- [x] 8.3 Write tests: scenario 21 (dashed cards with text/type/confidence), scenario 22 (promote API call and style change), scenario 23 (dismiss removes card without API call), scenario 24 (pre-label button disabled while in-flight)

## 9. Verification & Evidence

- [ ] 9.1 Run all acceptance-criteria tests for every scenario in verification.md § Spec Alignment and confirm all pass
- [ ] 9.2 Collect functional evidence (screenshot / test output / log) for each scenario — record one entry per row in verification.md § Evidence Log
- [ ] 9.3 Confirm every Hallucination Risk mitigation step in verification.md § Hallucination Risk Register
- [ ] 9.4 Confirm all ADR compliance steps in verification.md § Pattern & ADR Compliance
- [ ] 9.5 Complete Audit Record sign-off in verification.md § Audit Record (human reviewer required — this task cannot be marked complete by an agent)
- [ ] 9.6 Run `openspec validate sp05-annotation-workspace --type change --strict` and confirm it exits clean before archive
