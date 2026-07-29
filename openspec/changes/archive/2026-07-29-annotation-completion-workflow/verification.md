# Verification Plan

**Change:** annotation-completion-workflow
**Generated:** 2026-07-29
**Status:** 🟢 Complete — Evidence Log populated, Audit Record signed off. Ready to archive.

---

## 1. Spec Alignment

Map every requirement and every scenario in this change to a testable acceptance criterion.
Each row drives one evidence entry in Section 5.

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | portal-annotation | Annotation Toolbar | Toolbar renders all elements for an active task | Given a selected task with filename "invoice-2026-00417.pdf", status in-progress, 3 confirmed and 2 suggested spans, when the toolbar renders, then it shows the filename in JetBrains Mono, a badge reading "in_progress", the counter "3 confirmed · 2 suggested", the Pre-label button, and the 3-pane/Focus toggle | vitest: `AnnotationToolbar.test.tsx` › "Scenario 1 — Toolbar renders all elements for an active task" | - [x] |
| 2 | portal-annotation | Annotation Toolbar | Toolbar exposes no status selection control | Given any selected task, when the toolbar renders, then no status button group exists and no toolbar element issues a PATCH to /api/v1/annotation-tasks/{id} | vitest: `AnnotationToolbar.test.tsx` › "Scenario 2 — Toolbar exposes no status selection control" | - [x] |
| 3 | portal-annotation | Annotation Toolbar | Badge reflects completed status without offering a transition | Given a task with status completed, when the toolbar renders, then the badge reads "completed" and no toolbar control can set status to in_progress | vitest: `AnnotationToolbar.test.tsx` › "Scenario 3 — Badge reflects completed status without offering a transition" | - [x] |
| 4 | portal-annotation | Task Status Lifecycle | Opening an unannotated task promotes it to in-progress | Given a task with status unannotated, when the user selects it in the queue, then a PATCH with {status: "in-progress"} is sent and the badge reads "in_progress" | vitest: `AnnotationPage.test.tsx` › "Scenario 4 — Opening an unannotated task promotes it to in-progress" | - [x] |
| 5 | portal-annotation | Task Status Lifecycle | In-progress transition fires only once per session | Given a task with status unannotated, when the user selects it, switches away, and selects it again in the same session, then exactly one in-progress PATCH is sent | vitest: `AnnotationPage.test.tsx` › "Scenario 5 — In-progress transition fires only once per session" | - [x] |
| 6 | portal-annotation | Task Status Lifecycle | Opening a completed task sends no status request | Given a task with status completed, when the user selects it, then no PATCH is sent, the badge reads "completed", and the document with its confirmed spans renders | vitest: `AnnotationPage.test.tsx` › "Scenario 6 — Opening a completed task sends no status request" | - [x] |
| 7 | portal-annotation | Task Status Lifecycle | Creating a span does not send a status request | Given a task already in-progress, when the user creates a span via click, drag, or promote, then the span request is sent and no status PATCH accompanies it | vitest: `AnnotationPage.test.tsx` › "Scenario 7 — Creating a span does not send a status request" (promote path); code review confirms token-click and drag paths use the same single promotion site (task 3.3 grep) | - [x] |
| 8 | portal-annotation | Annotation Action Bar | Action bar renders at the bottom of the workspace | Given a selected task, when the workspace renders, then an action bar is present at the bottom containing a save indicator and a "Mark as Completed" button | vitest: `AnnotationActionBar.test.tsx` › "Scenario 8 — Action bar renders at the bottom of the workspace" | - [x] |
| 9 | portal-annotation | Annotation Action Bar | Mark as Completed completes the task | Given an in-progress task with at least one confirmed span, when the user clicks "Mark as Completed", then a PATCH with {status: "completed"} is sent, the button is disabled while in flight, and on 200 the badge reads "completed" with a success toast | vitest: `AnnotationPage.test.tsx` › "Scenario 9 — Mark as Completed completes the task" | - [x] |
| 10 | portal-annotation | Annotation Action Bar | Completing with no spans surfaces the error and keeps the task in-progress | Given an in-progress task with zero confirmed spans, when the user clicks "Mark as Completed", then the API returns 422, the badge still reads "in_progress", the API error message is toasted, and the button becomes enabled again | vitest: `AnnotationPage.test.tsx` › "Scenario 10 — Completing with no spans surfaces the error and keeps the task in-progress" | - [x] |
| 11 | portal-annotation | Annotation Action Bar | Re-completing an already completed task saves further edits | Given a completed task that was re-opened and edited, when the user clicks "Mark as Completed", then a PATCH with {status: "completed"} returns 200 and no "Cannot transition" error is shown | vitest: `AnnotationPage.test.tsx` › "Scenario 11 — Re-completing an already completed task saves further edits" | - [x] |
| 12 | portal-annotation | Annotation Action Bar | Action bar disabled with no task selected | Given no task is selected, when the workspace renders, then the "Mark as Completed" button is disabled and clicking it sends no request | vitest: `AnnotationActionBar.test.tsx` › "Scenario 12 — Action bar disabled with no task selected" | - [x] |
| 13 | annotation-workspace | Annotation Task Management | Create an annotation task | Given a processed training-purpose document and an active annotator, when a Tenant Admin POSTs /api/v1/annotation-tasks, then the response is 201 with status "unannotated" | pytest: `tests/test_annotation_workspace.py::test_7_10_task_create_returns_201` | - [x] |
| 14 | annotation-workspace | Annotation Task Management | Create task for already-assigned document returns 409 | Given doc-123 already has an in-progress task, when a Tenant Admin POSTs a task for doc-123, then the response is 409 indicating an active task exists | pytest: `tests/test_annotation_workspace.py::test_7_11_task_conflict_returns_409` | - [x] |
| 15 | annotation-workspace | Annotation Task Management | List annotation tasks with status filter | Given 2 completed and 1 unannotated task, when a Tenant Admin GETs /api/v1/annotation-tasks?status=unannotated, then the response is 200 containing only the unannotated task | pytest: `tests/test_annotation_workspace.py::test_7_12_task_list_with_filter` | - [x] |
| 16 | annotation-workspace | Annotation Task Management | Update annotation task status | Given task-789 with status unannotated, when an annotator PATCHes {status: "in-progress"}, then the response is 200 and the status is in-progress | pytest: `tests/test_annotation_workspace.py::test_7_13_task_update_status` | - [x] |
| 17 | annotation-workspace | Annotation Task Management | Complete a task that has spans | Given task-789 in-progress whose document has at least one confirmed span, when an annotator PATCHes {status: "completed"}, then the response is 200 and the status is completed | pytest: `tests/test_annotation_workspace.py::test_7_14_task_complete_with_spans` | - [x] |
| 18 | annotation-workspace | Annotation Task Management | Complete a task with no spans returns 422 | Given task-789 in-progress whose document has no confirmed spans, when an annotator PATCHes {status: "completed"}, then the response is 422 indicating at least one span is required | pytest: `tests/test_annotation_workspace.py::test_7_15_task_complete_no_spans_422` | - [x] |
| 19 | annotation-workspace | Annotation Task Management | Re-completing a completed task is idempotent | Given task-789 already completed with at least one confirmed span, when an annotator PATCHes {status: "completed"}, then the response is 200 and the status remains completed | pytest: `tests/test_annotation_workspace.py::test_task_recomplete_completed_task_is_idempotent` | - [x] |
| 20 | annotation-workspace | Annotation Task Management | Reopening a completed task is rejected | Given task-789 with status completed, when an annotator PATCHes {status: "in-progress"}, then the response is 422 with code INVALID_TRANSITION | pytest: `tests/test_annotation_workspace.py::test_task_reopen_completed_task_returns_422` | - [x] |

> **Rule:** Every `#### Scenario:` block in every `specs/**/*.md` file for this change
> MUST appear as a row in this table. A missing scenario is a P1 gap that blocks archive.

---

## 2. Hallucination Risk Register

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|-------------------|----------------------|
| 1 | Removal of the three lazy promotion blocks (design Decision 1) | Agent deletes one or two of the three inline `unannotated` → `in-progress` blocks (token click, drag mouseup, promote) and leaves the rest, producing duplicate PATCHes on first edit | Grep `AnnotationPage.tsx` for `"in-progress"` — the only remaining occurrence should be the task-selection effect; confirm `sentInProgressRef` is referenced in exactly one place |
| 2 | Idempotent transition table (design Decision 2) | Agent widens `valid_transitions` too far — e.g. adds `"completed": ["completed", "in-progress"]` or drops the `NO_SPANS` guard on the re-completion path | Read `tasks.py` `valid_transitions`: `completed` must map to `["completed"]` only; confirm the span-count check still runs before the UPDATE for every completed request |
| 3 | Toolbar prop removal | Agent leaves `onStatusChange` in `AnnotationToolbarProps` or keeps `handleStatusClick` dead, or hides the status group with CSS instead of deleting it | Read `AnnotationToolbar.tsx` — no `authFetch`, no `optimisticStatus`, no `statuses` array should remain; confirm `data-testid="status-group"` is absent from rendered output, not merely hidden |
| 4 | Save indicator semantics (design Decision 4) | Agent invents a dirty-buffer save, batching span writes until the button is clicked, changing persistence behaviour and risking data loss | Confirm span create/delete/promote still POST/DELETE immediately; the counter must be display-only and never gate a span request |
| 5 | Error path on completion | Agent implements the happy path and drops the 422 branch — no toast, or optimistically flips the badge to "completed" and never reverts | Trigger completion on a task with zero spans; badge must stay "in_progress", toast must show the API message, button must re-enable |
| 6 | Test updates | Agent skips or comments out the old status-group tests instead of replacing them, leaving coverage silently reduced | Diff `AnnotationToolbar.test.tsx` and `AnnotationPage.test.tsx` — no `.skip`/`xit`; new tests must cover rows 2, 4, 6, 8–12 |
| 7 | Scope creep into span locking | Agent adds a status guard to the span endpoints, freezing edits on completed tasks — explicitly a non-goal | Grep the span endpoints in `src/annotation_service` for task-status checks; there should be none introduced by this change |

---

## 3. Pattern & ADR Compliance

| ADR | Decision Summary | Constraint on This Change | Verification Step |
|-----|-----------------|--------------------------|-------------------|
| ADR-001 Tenant Data Isolation | Per-tenant Postgres schemas, schema resolved from tenant context | The task status SELECT/UPDATE must stay inside `_schema(tenant_id)` | Read the modified block in `src/annotation_service/api/v1/tasks.py` — every `text(...)` statement must interpolate `{schema}` derived from `get_tenant_id(request)`; no hardcoded schema names |
| ADR-004 OpenSpec Governance | Spec-driven flow: delta specs precede implementation | Behaviour changes must appear in this change's delta specs before code lands | Confirm every behavioural change in the diff traces to a requirement in `specs/portal-annotation/spec.md` or `specs/annotation-workspace/spec.md` |
| ADR-005 OpenCode Agent Boundaries | Agents edit only within declared scope | Edits confined to annotation portal components, `tasks.py`, and their tests | Review `git diff --stat` — files touched should be limited to `src/portal/src/components/annotation/*`, `src/annotation_service/api/v1/tasks.py`, `tests/test_annotation_workspace.py` |

---

## 4. Evidence Requirements

Evidence that **MUST** be collected and logged in Section 5 before this change is archived.
Do not archive while any item below remains unchecked.

### Functional Evidence

- [x] Scenario 1 (Toolbar renders all elements): test output showing the toolbar render test passing with filename, badge, counter, Pre-label, and layout toggle assertions
- [x] Scenario 2 (No status selection control): test output asserting `queryByTestId("status-group")` is null, plus a fetch-spy assertion that the toolbar issues no PATCH
- [x] Scenario 3 (Completed badge, no transition control): test output for a completed task showing badge text "completed" and absence of any status button
- [x] Scenario 4 (Open promotes to in-progress): test output showing one PATCH `{status: "in-progress"}` on task selection
- [x] Scenario 5 (Promotion once per session): test output asserting exactly one PATCH across select → switch → re-select
- [x] Scenario 6 (Completed task opens without PATCH): test output asserting zero status PATCHes and rendered spans for a completed task
- [x] Scenario 7 (Span creation sends no status PATCH): test output asserting the span POST fires and no annotation-tasks PATCH accompanies it
- [x] Scenario 8 (Action bar renders): test output asserting the action bar testid is present
- [x] Scenario 9 (Mark as Completed succeeds): test output showing PATCH `{status: "completed"}`, badge "completed" on 200
- [x] Scenario 10 (422 no-spans path): test output showing badge remains in_progress and button re-enabled
- [x] Scenario 11 (Idempotent re-completion): test output for the completed → completed path returning 200 with no error toast
- [x] Scenario 12 (Disabled with no task): test output asserting the button is disabled and no request is issued on click
- [x] Scenario 13 (Create task): pytest output for the task-creation test in `tests/test_annotation_workspace.py`
- [x] Scenario 14 (409 on already-assigned document): pytest output for the duplicate-assignment test
- [x] Scenario 15 (Status filter list): pytest output for the status-filter list test
- [x] Scenario 16 (unannotated → in-progress): pytest output for the status update test
- [x] Scenario 17 (Complete with spans): pytest output for the completion test
- [x] Scenario 18 (Complete with no spans → 422): pytest output showing 422 and the NO_SPANS message
- [x] Scenario 19 (Idempotent completion): pytest output showing 200 and unchanged completed status
- [x] Scenario 20 (Reopen rejected): pytest output showing 422 with code INVALID_TRANSITION

### Structural Evidence

- [x] Code review completed — implementation matches design.md decisions (no undocumented deviations)
- [x] All ADR compliance steps in Section 3 confirmed ✓
- [x] No undocumented architectural patterns introduced
- [x] No AI-invented requirements present in generated code (cross-checked against spec files)

### Edge Case Evidence

- [x] Risk 1 mitigation confirmed — grep of `AnnotationPage.tsx` shows a single `"in-progress"` PATCH body site (line 160) and `sentInProgressRef` used only in the task-selection guard (lines 53, 155–156)
- [x] Risk 2 mitigation confirmed — `valid_transitions` in `tasks.py` maps `"completed": ["completed"]` only; the `NO_SPANS` check remains unconditional on `new_status == "completed"`, preceding the UPDATE
- [x] Risk 3 mitigation confirmed — grep of `AnnotationToolbar.tsx` for `authFetch`, `optimisticStatus`, `status-btn`, `status-group` returns no matches
- [x] Risk 4 mitigation confirmed — code review: span create/delete/promote fetches are unchanged aside from `incrementPendingWrites`/`decrementPendingWrites` wrapping; no buffering introduced
- [x] Risk 5 mitigation confirmed — `AnnotationPage.test.tsx` "Scenario 10" passes: badge stays `in_progress`, error toast fires, button re-enables after a 422
- [x] Risk 6 mitigation confirmed — grep for `.skip`, `xit(`, `xdescribe` across the three annotation test files returns no matches
- [x] Risk 7 mitigation confirmed — grep of `spans.py` for `annotation_tasks` returns no matches; no task-status guard added

---

## 5. Evidence Log

| # | Evidence Type | Description / Link | Scenario(s) Covered | Collected By | Date |
|---|--------------|-------------------|---------------------|--------------|------|
| 1 | Functional | `vitest run src/components/annotation/AnnotationToolbar.test.tsx` (with `NODE_OPTIONS=--localstorage-file=...`) — "Test Files 1 passed (1), Tests 6 passed (6)" | Scenarios 1, 2, 3 | agent (opsx:apply) | 2026-07-29 |
| 2 | Functional | `vitest run src/components/annotation/AnnotationActionBar.test.tsx` — "Test Files 1 passed (1), Tests 2 passed (2)" | Scenarios 8, 12 | agent (opsx:apply) | 2026-07-29 |
| 3 | Functional | `vitest run src/components/annotation/AnnotationPage.test.tsx` — "Test Files 1 passed (1), Tests 19 passed (19)" | Scenarios 4, 5, 6, 7, 9, 10, 11 | agent (opsx:apply) | 2026-07-29 |
| 4 | Functional | `pytest tests/test_annotation_workspace.py -k task` — "9 passed, 15 deselected" | Scenarios 13–20 | agent (opsx:apply) | 2026-07-29 |
| 5 | Structural | Code review: diff limited to `src/portal/src/components/annotation/*`, `src/annotation_service/api/v1/tasks.py`, `tests/test_annotation_workspace.py` — matches design.md Decisions 1–4 | N/A (structural) | agent (opsx:apply) | 2026-07-29 |
| 6 | Edge Case | grep sweep for Risks 1, 3, 6, 7 (`AnnotationPage.tsx`, `AnnotationToolbar.tsx`, `spans.py`, test files) — all clean, see § Hallucination Risk Register | Risks 1, 3, 6, 7 | agent (opsx:apply) | 2026-07-29 |

---

## 6. Audit Record

> ⚠️ **GATE: This section must be completed and signed by a human reviewer before
> `/opsx:archive` is run.** An unsigned or incomplete Audit Record is a hard block on archive.

**Change slug:** annotation-completion-workflow
**Proposal:** `openspec/changes/annotation-completion-workflow/proposal.md`
**Spec files reviewed:**
  - specs/portal-annotation/spec.md
  - specs/annotation-workspace/spec.md

### Reviewer Sign-Off

| Check | Status |
|-------|--------|
| Design reviewed against proposal | - [x] |
| All ADRs in Section 3 verified compliant | - [x] |
| Spec Alignment table complete (no missing scenarios) | - [x] |
| Evidence Log populated with real evidence | - [x] |
| All functional evidence items in Section 4 checked | - [x] |
| All structural evidence items in Section 4 checked | - [x] |
| All edge case evidence items in Section 4 checked | - [x] |

### AI Output Review

| Check | Status |
|-------|--------|
| All generated artifacts reviewed for spec alignment | - [x] |
| No hallucinated requirements introduced | - [x] |
| No undocumented patterns used | - [x] |
| No AI-invented fields, endpoints, or behaviours present | - [x] |
| Every THEN clause in specs has a corresponding evidence entry | - [x] |
| Hallucination risk register reviewed and all mitigations confirmed | - [x] |

**Archive approved by:** arjoonnjayakumar

**Date:** 2026-07-29

**Notes:** Live bug found post-implementation: annotation_service container was running a stale image, so the completed→completed idempotent transition wasn't in effect and users saw a spurious "Cannot transition" error. Fixed by rebuilding/restarting the container (`docker compose build annotation_service && docker compose up -d annotation_service`) — code was already correct, this was a deploy-freshness gap, not a code defect.
