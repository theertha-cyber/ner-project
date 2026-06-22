## 1. DB Migration — BIO Tag Column

- [ ] 1.1 Create `alembic/versions/009_add_bio_tags_to_spans.py` with `revision = "009"`, `down_revision = "008"`: upgrade adds `ALTER TABLE tenant_template.spans ADD COLUMN IF NOT EXISTS bio_tags TEXT[]`; downgrade removes it with `DROP COLUMN IF EXISTS bio_tags` (covers scenarios 12)
- [ ] 1.2 Run `alembic upgrade head` in the dev environment and confirm `\d tenant_template.spans` shows the nullable `bio_tags TEXT[]` column with all pre-existing rows intact

## 2. Annotation Service — BIO Tag Storage

- [ ] 2.1 Add a `_compute_bio_tags(doc_text: str, char_start: int, char_end: int, entity_type: str) -> list[str]` helper in `spans.py`: tokenize `doc_text` with `.split()`, walk tokens tracking char offset (same logic as export's `_bio_tags`), return `["B-{entity_type}", "I-{entity_type}", ...]` for all tokens in `[char_start, char_end)` (covers scenarios 7, 8)
- [ ] 2.2 In the `create_span` POST handler, after validating entity_type: query `document_text_spans` for the document's text (`SELECT text FROM {schema}.document_text_spans WHERE document_id = :doc_id LIMIT 1`), call `_compute_bio_tags()`, and include `bio_tags` in the INSERT and the 201 response (covers scenario 7)
- [ ] 2.3 In the `update_span` PATCH handler, when `entity_type` is in the request body: query `document_text_spans` for text, call `_compute_bio_tags()` with the existing `char_start`/`char_end` and new entity_type, add `bio_tags = :bio_tags` to the UPDATE statement, and include `bio_tags` in the response (covers scenario 9)
- [ ] 2.4 Write unit tests for `_compute_bio_tags`: single-token B-only case, two-token B+I case, non-zero char_start span to verify absolute offset is handled correctly (covers scenarios 7, 8)

## 3. Annotation Service — Export Reads Stored Tags

- [ ] 3.1 Update the `list_spans` SELECT in `export.py` to also retrieve `bio_tags` from the spans table: `SELECT id, entity_type, char_start, char_end, bio_tags FROM {schema}.spans WHERE ...`
- [ ] 3.2 In the export JSONL assembly loop, for each span: if `bio_tags is not None`, use the stored array to map tokens directly; if `bio_tags is None`, fall back to the existing `_bio_tags()` computation (covers scenarios 10, 11)
- [ ] 3.3 Integration test: create a span via POST (verifying bio_tags is stored), then call GET /annotation-export and confirm the tags match the stored values; separately test a NULL bio_tags span and confirm the fallback computes correctly

## 4. AppShell — Sticky Navbar

- [ ] 4.1 In `src/portal/src/components/app-shell/AppShell.tsx`, change the outer div style from `minHeight: "100vh"` to `height: "100vh"` — this pins the flex column to the viewport, forcing `<main overflow:auto>` to scroll internally (covers scenario 27)
- [ ] 4.2 In `src/portal/src/components/app-shell/Topbar.tsx`, add `position: "sticky"` and `top: 0` to the `<header>` style (covers scenario 27)
- [ ] 4.3 Verify on the Documents page and Users page that content below the fold is still scrollable and the topbar never scrolls out of view

## 5. Annotation Workspace — Quick UX Fixes (Deselect, Mark Complete, Task Name, Focus Toggle)

- [ ] 5.1 **Deselect**: in `AnnotationPage.tsx` `handleTokenClick`, in the `else` branch (no armedType), add: `else { dispatch({ type: "SPAN_SET_SELECTED", spanId: null }); }` when no confirmed span is found at the clicked token (covers scenarios 13, 14)
- [ ] 5.2 **Mark Complete visibility**: update the disabled-state style of the "Mark Complete" button in `AnnotationPage.tsx` to use `border: "1px solid var(--color-border)"` and `background: "transparent"` so it renders as a clearly visible outlined button when disabled; remove the current `background: var(--color-surface-raised)` that blends into the toolbar (covers scenario 24)
- [ ] 5.3 **Task display name**: in `TaskQueue.tsx`, replace `doc-{shortId}` in the button label with `Task {index + 1}` using the `tasks.map((task, index) => ...)` callback's index; update the `AnnotationPage.tsx` toolbar to show `Task {filteredTasks.indexOf(selectedTask) + 1}` instead of `doc-{selectedTask.document_id.slice(0, 8)}` (covers scenarios 15, 16)
- [ ] 5.4 **Focus mode toggle**: replace the 2-button radio group (`[3-pane] [Focus]`) in the `AnnotationPage.tsx` toolbar with a single `<button>` that calls `toggleLayout(layoutMode === "focus" ? "3pane" : "focus")`; style as outlined/inactive when layoutMode is "3pane" and filled/primary when layoutMode is "focus" (covers scenarios 17, 19)

## 6. Annotation Workspace — Fullscreen Focus Mode

- [ ] 6.1 Add a `fullscreenChange` `useEffect` in `AnnotationPage.tsx` that listens to the `fullscreenchange` document event: if `document.fullscreenElement === null` and `layoutMode === "focus"`, dispatch `setLayoutMode("3pane")` and update localStorage; clean up the listener on unmount (covers scenario 20)
- [ ] 6.2 Update the `toggleLayout` function: when switching to `"focus"`, call `document.documentElement.requestFullscreen().catch(() => {})` (catch swallows API-rejected errors for iframe environments); when switching to `"3pane"`, call `document.exitFullscreen().catch(() => {})` (covers scenarios 18, 19, 21)
- [ ] 6.3 Browser test: click Focus on the annotation page — confirm the browser enters fullscreen (address bar hides), task queue hides, palette floats, and Focus button appears active; press Escape — confirm 3-pane layout restores and Focus button shows inactive (covers scenarios 18, 19, 20)

## 7. Drag-to-Annotate

- [ ] 7.1 Add drag state to `AnnotationPage.tsx`: `const [isDragging, setIsDragging] = useState(false)`, `const [dragStartIndex, setDragStartIndex] = useState<number | null>(null)`, `const [dragEndIndex, setDragEndIndex] = useState<number | null>(null)`
- [ ] 7.2 Add a `useEffect` in `AnnotationPage.tsx` that listens to `mouseup` on the `document` object: when `isDragging` is true and `dragStartIndex !== null`, compute the span range (min/max of dragStartIndex and dragEndIndex), then run the span creation logic (identical to existing single-token logic but using the full range's `charStart`/`charEnd`); always reset `isDragging`, `dragStartIndex`, `dragEndIndex` on mouseup (covers scenarios 1, 3, 6)
- [ ] 7.3 Add `handleTokenMouseDown(tokenIndex: number)` and `handleTokenMouseEnter(tokenIndex: number)` callbacks to `AnnotationPage.tsx`: mousedown sets `isDragging = true; dragStartIndex = tokenIndex; dragEndIndex = tokenIndex`; mouseEnter (while isDragging) sets `dragEndIndex = tokenIndex` (covers scenario 2)
- [ ] 7.4 Pass `onMouseDown` and `onMouseEnter` props down from `AnnotationPage` → `DocumentViewer` → `Token`; add corresponding props to `DocumentViewerProps` and `TokenProps` interfaces (covers scenario 2)
- [ ] 7.5 Add drag-preview highlight in `DocumentViewer.tsx`: compute the token index range `[min(dragStartIndex, dragEndIndex), max(dragStartIndex, dragEndIndex)]` when `isDragging && armedType`; set highlight to `{ kind: "drag-preview", color: entityColors[armedType] }` for those tokens; add `"drag-preview"` to the `TokenHighlight` union in `Token.tsx` (styled same as confirmed but with reduced opacity, e.g. `33` alpha) (covers scenario 2)
- [ ] 7.6 Guard drag creation: in the mouseup handler, if the drag range covers any already-confirmed token, cancel the span creation (no API call, reset state) (covers scenario 5)
- [ ] 7.7 Write unit tests: drag right-to-left (index 5 → 2) produces min=2, max=5 with correct char offsets; single-click (start === end) falls through to existing click logic; drag while unarmed produces no action (covers scenarios 3, 4, 6)

## 8. Verification & Evidence

- [ ] 8.1 Run all acceptance-criteria tests for every scenario in verification.md § Spec Alignment and confirm all pass
- [ ] 8.2 Collect functional evidence (screenshot / test output / log) for each scenario — record one entry per row in verification.md § Evidence Log
- [ ] 8.3 Confirm every Hallucination Risk mitigation step in verification.md § Hallucination Risk Register
- [ ] 8.4 Confirm all ADR compliance steps in verification.md § Pattern & ADR Compliance
- [ ] 8.5 Complete Audit Record sign-off in verification.md § Audit Record (human reviewer required — this task cannot be marked complete by an agent)
- [ ] 8.6 Run `openspec validate annotation-ui-fixes --type change --strict` and confirm it exits clean before archive
