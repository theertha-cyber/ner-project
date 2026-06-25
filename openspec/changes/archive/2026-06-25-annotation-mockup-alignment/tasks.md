## 1. Backend: Annotation Task List API

- [x] 1.1 In `src/annotation_service/api/v1/tasks.py`, update `list_tasks` (`GET /api/v1/annotation-tasks`) to JOIN with the `documents` table and return `filename`, `document_status` (document's `status` field), and `span_count` (count of confirmed spans from `spans` table) for each task row — update both the raw SQL query and the dict returned per row
- [x] 1.2 Verify `list_tasks` also returns `filename` and `span_count` when filtering by `status` query param (the filtered branch at line 92 also needs the JOIN)
- [x] 1.3 Verify tests or manual call confirms the response shape: `{id, document_id, annotator_user_id, status, filename, document_status, span_count, created_at, updated_at}`

## 2. Frontend: TypeScript Types

- [x] 2.1 In `src/portal/src/components/annotation/TaskQueue.tsx`, add `filename: string`, `document_status?: string`, and `span_count?: number` to the `AnnotationTask` interface
- [x] 2.2 Confirm `AnnotationPage.tsx` imports and passes the updated `AnnotationTask` type without additional changes (it already reads the full task object)

## 3. Task Queue Component

- [x] 3.1 In `TaskQueue.tsx`, replace `"Task {index + 1}"` with `task.filename` as the primary label text (the `<div>` at line 70)
- [x] 3.2 In `TaskQueue.tsx`, replace the status sub-label (line 84) with `"{task.document_status} · {task.span_count} spans"` — handle undefined gracefully (fall back to task status if document_status is absent)
- [x] 3.3 Update `src/portal/src/components/annotation/TaskQueue.test.tsx` — replace any assertions for "Task 1" / "Task 2" with assertions for the filename value; update test data to include `filename`, `document_status`, `span_count` fields
- [x] 3.4 Verify: given `filename: "invoice-2026-00417.pdf"`, `document_status: "processed"`, `span_count: 12`, the row renders "invoice-2026-00417.pdf" and "processed · 12 spans" (covers verification scenarios 5, 7, 8)

## 4. Annotation Toolbar

- [x] 4.1 In `src/portal/src/components/annotation/AnnotationPage.tsx`, remove the `taskLabel` and `taskIndex` computations (lines 483–484); update the `AnnotationToolbar` call to pass `filename={selectedTask?.filename ?? ""}` instead of `taskLabel`
- [x] 4.2 In `src/portal/src/components/annotation/AnnotationToolbar.tsx`, rename the `taskLabel: string` prop to `filename: string` and update the rendered span (line 98) from `{task ? taskLabel : "No task selected"}` to `{task ? filename : "No task selected"}`
- [x] 4.3 In `AnnotationToolbar.tsx`, update the active status button style (line 154) from `background: isActive ? "var(--color-surface-overlay)" : "transparent"` to `background: isActive ? "var(--color-primary, #6366f1)" : "transparent"` and add `color: isActive ? "#fff" : ...` accordingly — the active button must have solid primary fill
- [x] 4.4 Update `src/portal/src/components/annotation/AnnotationToolbar.test.tsx` — update any assertions using "Task 1" / "Task 2" to use the filename; update test props from `taskLabel` to `filename`
- [x] 4.5 Verify: toolbar shows "invoice-2026-00417.pdf" in JetBrains Mono with status badge (covers scenarios 6, 11); verify active status button has solid primary fill (covers scenario 12)

## 5. Layout and Navigation (Fullscreen Removal)

- [x] 5.1 In `AnnotationPage.tsx`, search for any `requestFullscreen`, `exitFullscreen`, or `fullscreenchange` calls and remove them — focus mode should be purely CSS (confirm with `grep -r "requestFullscreen\|exitFullscreen\|fullscreenchange" src/portal/src/components/annotation/` returning zero results)
- [x] 5.2 Verify the 2-button radio group (3-pane / Focus) is already rendered in `AnnotationToolbar.tsx` — if it was already implemented in sp05, confirm it uses `data-testid="layout-btn-3pane"` and `data-testid="layout-btn-focus"` and no fullscreen API is called (covers scenarios 1–4)

## 6. Document Viewer Card Container

- [x] 6.1 In `src/portal/src/components/annotation/DocumentViewer.tsx`, wrap the token rendering area in a card `<div>` with: `border: "1px solid var(--color-border)"`, `borderRadius: 16`, `padding: "36px 40px"`, `boxShadow: "var(--shadow, 0 2px 12px rgba(0,0,0,0.08))"`, `maxWidth: 680`, `margin: "0 auto"`
- [x] 6.2 Verify the card wrapper only applies when tokens exist (the empty-state message should NOT be inside the card)
- [x] 6.3 Verify in the browser or snapshot test that the document content appears inside a card with visible border-radius and shadow (covers scenario 14)

## 7. Right Panel Restructuring (3-pane mode)

- [x] 7.1 In `AnnotationPage.tsx`, remove the `SpanInspector` block from the center document column (lines 593–606 — the `selectedSpan && layoutMode === "3pane"` block inside the document viewer `<div>`) 
- [x] 7.2 In `AnnotationPage.tsx`, move the `SpanInspector` (3-pane mode) into the right entity panel `<div>` (the `layoutMode === "3pane"` right panel at line 643), stacking it below `<EntityPalette>` — wrap in a conditional `{selectedSpan && layoutMode === "3pane" && (...)}` 
- [x] 7.3 In `AnnotationPage.tsx`, remove the `SuggestionPanel` block from the center document column (lines 609–639 — the `layoutMode === "3pane" && spanState.suggested.length > 0` block at the bottom of the center column)
- [x] 7.4 In `AnnotationPage.tsx`, move `SuggestionPanel` (3-pane mode) into the right entity panel `<div>`, stacking it below the SpanInspector — wrap in a conditional `{layoutMode === "3pane" && spanState.suggested.length > 0 && selectedTask && (...)}`
- [x] 7.5 Verify the right panel layout in 3-pane mode stacks: EntityPalette → SpanInspector (when a span is selected) → SuggestionPanel (when suggestions exist) — center column contains only the document viewer and tokens (covers scenarios 21, 25)

## 8. Entity Type Dot Shape

- [x] 8.1 In `src/portal/src/components/annotation/EntityPalette.tsx`, change the dot element (lines 80–87) from `width: 8, height: 8, borderRadius: "50%"` to `width: 11, height: 11, borderRadius: 3`
- [x] 8.2 In `src/portal/src/components/annotation/FocusPalette.tsx`, change the dot element (lines 99–106) from `width: 7, height: 7, borderRadius: "50%"` to `width: 9, height: 9, borderRadius: 3` (proportionate to focus palette chip size)
- [x] 8.3 Verify: entity type buttons in both 3-pane palette and focus palette show a rounded-square dot, not a circle (covers scenario 17)

## 9. Armed Banner Text

- [x] 9.1 In `src/portal/src/components/annotation/ArmedBanner.tsx`, update the banner text to render `"Labeling mode · click words to tag as {entityType}"` — remove or ignore the `description` prop from the display text; the pulsing dot and "esc · done" button remain unchanged
- [x] 9.2 Update `src/portal/src/components/annotation/ArmedBanner.test.tsx` — update test assertions to expect the instructional text format rather than entity description
- [x] 9.3 Verify: armed banner shows "Labeling mode · click words to tag as vendor_name" (not a description string) (covers scenarios 18, 19, 33)

## 10. Focus Mode Span Inspector (Condensed Header)

- [x] 10.1 In `src/portal/src/components/annotation/SpanInspector.tsx`, add a condensed focus-mode header variant: when `layoutMode === "focus"`, replace the 2×2 metadata grid section with a single-line `<div>` rendering `"{span.text} · [{span.charStart}, {span.charEnd}] · conf {span.confidence.toFixed(2)}"` — keep the reassign chips and delete button below unchanged
- [x] 10.2 Verify: in 3-pane mode the 2×2 grid still renders; in focus mode the single-line header replaces the grid (covers scenarios 21, 22)

## 11. Tests: Update Affected Test Files

- [x] 11.1 Update `src/portal/src/components/annotation/AnnotationPage.test.tsx` — update any "Task 1"/"Task 2" assertions to filenames; update test task fixtures to include `filename`, `document_status`, `span_count`; add test confirming SpanInspector renders inside the right entity panel in 3-pane mode; add test confirming SuggestionPanel renders inside the right entity panel in 3-pane mode
- [x] 11.2 Run `npm test -- --testPathPattern=annotation` from `src/portal/` and confirm all annotation-related tests pass with zero failures

## 12. Verification & Evidence

- [ ] 12.1 Run all acceptance-criteria tests for every scenario in verification.md § Spec Alignment and confirm all pass
- [ ] 12.2 Collect functional evidence (screenshot / test output / log) for each scenario — record one entry per row in verification.md § Evidence Log
- [ ] 12.3 Confirm every Hallucination Risk mitigation step in verification.md § Hallucination Risk Register
- [ ] 12.4 Confirm all ADR compliance steps in verification.md § Pattern & ADR Compliance
- [ ] 12.5 Complete Audit Record sign-off in verification.md § Audit Record (human reviewer required — this task cannot be marked complete by an agent)
- [ ] 12.6 Run `openspec validate annotation-mockup-alignment --type change --strict` and confirm it exits clean before archive
