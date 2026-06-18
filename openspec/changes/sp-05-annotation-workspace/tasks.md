## 1. Setup and Route Scaffolding

- [x] 1.1 Verify `GET /api/v1/documents/{id}/text` endpoint exists and confirm the response shape (plain text string vs. structured object) in the document/extraction service source
- [x] 1.2 Verify `POST /api/v1/documents/{id}/spans/promote/{suggest_id}` endpoint exists and confirm its response shape in the annotation service source
- [x] 1.3 Create `src/portal/src/app/(auth)/annotation/page.tsx` that exports the `AnnotationPage` component and registers the `/annotation` route inside the authenticated layout
- [x] 1.4 Add `/annotation` to the sidebar nav config in `src/portal/src/components/shell/nav-config.ts` for `annotator` and `tenant_admin` roles

## 2. State Management — Span Reducer

- [x] 2.1 Create `src/portal/src/components/annotation/span-reducer.ts` defining the `SpanState` type (confirmed spans, suggested spans, armed entity type, selected span) and action union (`SPAN_ADD_OPTIMISTIC`, `SPAN_CONFIRM`, `SPAN_REVERT`, `SPAN_DELETE`, `SPAN_RETYPE`, `SPAN_SET_SELECTED`, `SUGGESTION_PROMOTE`, `SUGGESTION_DISMISS`, `SUGGESTIONS_LOAD`, `SPANS_LOAD`, `ARM`, `DISARM`)
- [x] 2.2 Implement each reducer case in `span-reducer.ts`, including the optimistic ID (`"optimistic-<uuid>"`) strategy and confirmation/revert logic
- [x] 2.3 Write unit tests for `span-reducer.ts` covering optimistic add → confirm, optimistic add → revert, delete, retype, suggestion promote, and dismiss

## 3. Char-Offset Utility

- [x] 3.1 Create `src/portal/src/lib/token-map.ts` that exports `buildTokenMap(text: string): TokenMap` where `TokenMap = Array<{ token: string; charStart: number; charEnd: number }>`
- [x] 3.2 Implement `buildTokenMap` using whitespace-split (`text.split(/\s+/)`) with cumulative offset accounting for single-space separators
- [x] 3.3 Export `spanToTokenRange(tokenMap: TokenMap, charStart: number, charEnd: number): number[]` that returns the array of token indices covered by a span (inclusive range scan)
- [x] 3.4 Write unit tests covering: single token, multi-token span, token at start, token at end, "Hello World Foo" example from spec scenarios 29 and 30 (verification artifact for scenarios 29–30)

## 4. Layout and Task Queue

- [x] 4.1 Create `src/portal/src/components/annotation/AnnotationPage.tsx` owning the `useReducer(spanReducer, initialState)`, layout toggle state (read from `localStorage`), and task selection state; wire to the route's page component
- [x] 4.2 Create `src/portal/src/components/annotation/TaskQueue.tsx` rendering a list of annotation task rows (filename, status badge) with an `onSelect` callback; show "No tasks assigned" empty state when task list is empty (covers scenarios 4, 5, 7)
- [x] 4.3 Implement the `GET /api/v1/annotation-tasks` fetch in `AnnotationPage.tsx` using `useQuery`; for `annotator` role pass no filter (backend scopes to current user), for `tenant_admin` fetch all tasks
- [x] 4.4 Implement the 3-pane CSS layout and the focus-mode toggle; persist preference to `localStorage` under `"ner-annotation-layout"`; restore on mount (covers scenarios 1, 2, 3)
- [x] 4.5 Implement task selection: on row click, fetch `GET /documents/{id}/text`, `GET /documents/{id}/spans`, and `GET /documents/{id}/spans?type=suggested`; dispatch `SPANS_LOAD` and `SUGGESTIONS_LOAD` to reset span state (covers scenario 6)

## 5. Document Viewer and Token Rendering

- [x] 5.1 Create `src/portal/src/components/annotation/DocumentViewer.tsx` that receives `tokenMap`, `spanState`, `armedType`, and token click callback; renders tokens as a flex-wrapped list
- [x] 5.2 Create `src/portal/src/components/annotation/Token.tsx` that receives a token, its highlight state (confirmed entity type | suggested entity type | none), and `onClick`; renders with solid background for confirmed, dashed-border overlay for suggested, and default styling for unannotated (covers scenarios 8, 9, 10)
- [x] 5.3 Compute per-token highlight state in `DocumentViewer.tsx` by running `spanToTokenRange` over all confirmed and suggested spans; confirmed spans take visual precedence over suggested ones
- [x] 5.4 Wire the armed-mode banner above the document viewer: render when `armedType !== null`, show entity type name, include an "× Disarm" affordance

## 6. Entity Type Palette

- [x] 6.1 Create `src/portal/src/components/annotation/EntityPalette.tsx` that fetches `GET /api/v1/entity-types` and receives confirmed span list; renders entity type chips with span counts (count = number of confirmed spans of that type on the active document only) (covers scenario 11)
- [x] 6.2 Implement armed-type chip click (toggle arm / disarm) via `ARM` / `DISARM` dispatch; active chip shows ring highlight (covers scenarios 12, 14)
- [x] 6.3 Add a global `keydown` listener in `AnnotationPage.tsx` via `useEffect` that dispatches `DISARM` on `Escape`; include cleanup to remove the listener on unmount (covers scenario 13)

## 7. Token-Click Span Creation

- [x] 7.1 Implement token click handler in `AnnotationPage.tsx`: if `armedType` is set and the token is not already covered by a confirmed span, dispatch `SPAN_ADD_OPTIMISTIC` then call `POST /documents/{id}/spans` with computed `char_start`/`char_end` (covers scenarios 15, 16)
- [x] 7.2 On API success (201), dispatch `SPAN_CONFIRM` with the server-returned span ID replacing the optimistic ID
- [x] 7.3 On API error, dispatch `SPAN_REVERT` to remove the optimistic highlight and call `toast(errorMessage, "bad")` (covers scenario 17)
- [x] 7.4 If `armedType` is null and the clicked token belongs to a confirmed span, dispatch `SPAN_SET_SELECTED` to open the span inspector (covers scenario 18)

## 8. Span Inspector

- [x] 8.1 Create `src/portal/src/components/annotation/SpanInspector.tsx` that renders when `selectedSpan !== null`; display entity_type, char_start, char_end, text, confidence (covers scenario 19)
- [x] 8.2 Implement the retype dropdown in `SpanInspector.tsx`: on selection confirmation call `PATCH /documents/{id}/spans/{span_id}` and dispatch `SPAN_RETYPE` optimistically; close inspector on success (covers scenario 20)
- [x] 8.3 Implement the delete button in `SpanInspector.tsx`: call `DELETE /documents/{id}/spans/{span_id}` and dispatch `SPAN_DELETE` optimistically; close inspector on success (204) (covers scenario 21)

## 9. Pre-labeling and Suggestion Flow

- [x] 9.1 Add a "Pre-label" button in the document viewer area of `AnnotationPage.tsx`; on click, call `POST /documents/{id}/prelabel` with `useMutation`; disable the button while the mutation is in-flight (covers scenario 25)
- [x] 9.2 On pre-label success, dispatch `SUGGESTIONS_LOAD` with the returned suggested spans; the document viewer's token render already handles dashed styling via the `SpanState.suggestedSpans` list (covers scenario 22)
- [x] 9.3 Create `src/portal/src/components/annotation/SuggestionPanel.tsx` rendering the list of suggestions with entity type, text, and Promote / Dismiss buttons
- [x] 9.4 Implement Promote: call `POST /documents/{id}/spans/promote/{suggest_id}` and dispatch `SUGGESTION_PROMOTE` on success (converts suggestion to confirmed span) (covers scenario 23)
- [x] 9.5 Implement Dismiss: dispatch `SUGGESTION_DISMISS` locally (no API call); remove the suggestion row and dashed token styling (covers scenario 24)

## 10. Task Status Lifecycle

- [x] 10.1 In the span creation success handler (task 7.2), after the first confirmed span is added to a task in `unannotated` status, call `PATCH /annotation-tasks/{id}` with `{status: "in-progress"}` and update the task row badge in the queue (covers scenario 26)
- [x] 10.2 Add a "Mark Complete" button in the workspace; disable it when `confirmedSpans.length === 0`; show tooltip "Add at least one confirmed span before completing" on hover (covers scenario 27)
- [x] 10.3 On "Mark Complete" click, call `PATCH /annotation-tasks/{id}` with `{status: "completed"}`; on success, update queue badge and auto-select the next non-completed task if one exists (covers scenario 28)

## 11. Verification & Evidence

- [ ] 11.1 Run all acceptance-criteria tests for every scenario in verification.md § Spec Alignment and confirm all pass — unit tests for scenarios 29/30 (token-map) and reducer (scenarios via unit tests) pass (23/23). Manual browser tests pending for all UI scenarios. Note: 2 pre-existing login.test.tsx failures are unrelated to this change (from login-dashboard-transition work)
- [ ] 11.2 Collect functional evidence (screenshot / test output / log) for each scenario — record one entry per row in verification.md § Evidence Log
- [ ] 11.3 Confirm every Hallucination Risk mitigation step in verification.md § Hallucination Risk Register
- [ ] 11.4 Confirm all ADR compliance steps in verification.md § Pattern & ADR Compliance
- [ ] 11.5 Complete Audit Record sign-off in verification.md § Audit Record (human reviewer required — this task cannot be marked complete by an agent)
- [ ] 11.6 Run `openspec validate sp-05-annotation-workspace --type change --strict` and confirm it exits clean before archive
