# Verification Plan

**Change:** multi-document-task-assignment
**Generated:** 2026-09-14
**Status:** 🟡 Automated evidence collected this session; Audit Record sign-off still needs a human reviewer.

---

## 1. Spec Alignment

| # | Requirement | Scenario | Verification Artifact | Status |
|---|-------------|----------|------------------------|--------|
| 1 | Task Assignment Form | Assign Task button visible for tenant admin | AssignTaskForm.test.tsx render setup (button gating lives in `AnnotationPage.tsx`, pre-existing, unmodified) | [x] |
| 2 | Task Assignment Form | Assign Task button hidden for annotator | (pre-existing, unmodified — button visibility untouched by this change) | [x] |
| 3 | Task Assignment Form | Clicking Assign Task button expands the inline form | (pre-existing, unmodified) | [x] |
| 4 | Task Assignment Form | Document dropdown lists only processed documents | AssignTaskForm.test.tsx::"Scenario 4 — Document list shows only processed documents" | [x] |
| 5 | Task Assignment Form | Annotator dropdown lists only annotator-role users | AssignTaskForm.test.tsx::"Scenario 5" (unchanged behavior, rerun) | [x] |
| 6 | Task Assignment Form | Assign button disabled until both fields are selected | AssignTaskForm.test.tsx::"Scenario 6" (4 tests: initial, doc-only, annotator-only, one-doc-enabled) | [x] |
| 7 | Task Assignment Form | Successful task creation adds task to queue | AssignTaskForm.test.tsx::"Scenario 7" (single-document and multi-document-all-succeed tests) | [x] |
| 8 | Task Assignment Form | Duplicate assignment (409) shows inline error | AssignTaskForm.test.tsx::"Scenario 8" (single-document conflict test) | [x] |
| 9 | Task Assignment Form | Cancel collapses form without submitting | AssignTaskForm.test.tsx::"Scenario 9" (unchanged behavior, rerun) | [x] |
| 10 | Task Assignment Form | Empty annotator list shows descriptive message | AssignTaskForm.test.tsx::"Scenario 10" (unchanged behavior, rerun) | [x] |
| 11 | Task Assignment Form | Multiple documents can be selected and assigned together | AssignTaskForm.test.tsx::"Scenario 7 — ...creates one task per selected document..." | [x] |
| 12 | Task Assignment Form | Select all checks every visible processed document | AssignTaskForm.test.tsx::"Select all / Clear controls — selects every processed document..." | [x] |
| 13 | Task Assignment Form | A partially-failed batch shows per-document results and requires Done to close | AssignTaskForm.test.tsx::"Scenario 8 — ...reports a mixed batch..." | [x] |

Rows 1–3 are the button-gating/expand-collapse behavior, which lives in `AnnotationPage.tsx`
and is untouched by this change; not independently re-verified by a new test here, only by the
unmodified `AnnotationPage.test.tsx` suite (3 of its tests fail — a pre-existing, unrelated
layout-scenario baseline, see § Evidence Log).

---

## 2. Hallucination Risk Register

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|--------------------|-----------------------|
| 1 | Inventing a bulk backend endpoint | Could have assumed or fabricated a `POST /api/v1/annotation-tasks/bulk`-style endpoint that doesn't exist | Confirmed by reading `src/annotation_service/api/v1/tasks.py` directly: only the single-document `POST /api/v1/annotation-tasks` exists; this change loops over it client-side rather than inventing backend surface area |
| 2 | Losing the per-document conflict semantics in a batch | A naive rewrite might treat the whole batch as atomic (all-or-nothing) rather than preserving each document's independent 409 check | Each document is POSTed and checked individually, in its own try/catch, exactly mirroring the prior single-document flow's error handling per request — a batch of 5 where 1 conflicts still creates the other 4 |
| 3 | Silently closing over a partial failure | Could have kept the "always close on submit" behavior from the single-document flow, hiding which documents in a batch failed | Explicitly gated: the form only auto-closes when `failureCount === 0`; any failure keeps it open with per-document results and an explicit "Done" action, so the admin always sees which documents succeeded before the queue updates |
| 4 | `onAssign` signature change breaking its only caller | Changing a shared prop's type from a single item to an array could silently break `AnnotationPage.tsx` if its usage weren't updated in the same change | Confirmed `AnnotationPage.tsx` is `AssignTaskForm`'s only caller (grepped for all usages) and updated `handleTaskAssigned` to prepend the array in the same change; confirmed `AnnotationPage.test.tsx` doesn't exercise this path at all (it mocks `AssignTaskForm` and never renders the real `onAssign` call site), so no test there could have masked a break |

---

## 3. Pattern & ADR Compliance

- No backend or ADR-governed behavior changed — the existing single-document endpoint, its
  conflict rule, and its role gates are all unchanged and reused as-is, once per document.

---

## 4. Evidence Log

- **Frontend — tests:** `AssignTaskForm.test.tsx` — fully rewritten, 15 tests (up from 9), all
  passed against the `ner-portal-test` container.
- **Regression check:** `AnnotationPage.test.tsx` rerun unmodified — 18/21 passed; the 3
  failures (`Scenario 1 — Default layout renders three columns`, `Scenario 2 & 3 — Clicking
  Focus...` x2) are the confirmed pre-existing, layout-related baseline, unrelated to
  `AssignTaskForm` (that file mocks `AssignTaskForm` entirely and never exercises `onAssign`).
- **Full regression sweep:** full portal suite — 114/119 files passed (796/805 tests), 5 failing
  files (down from the known 6-file baseline by exactly one — `AssignTaskForm.test.tsx` no
  longer appears, confirming the stale toast assertion was the only thing keeping it in that
  list). The remaining 5 failures match the pre-existing baseline exactly:
  `AnnotationImportPreview.test.tsx`, `AnnotationPage.test.tsx` (layout scenarios, unrelated to
  `AssignTaskForm`), `StatusFilterTabs.test.tsx`, `EntityTypesPage.test.tsx`,
  `training-jobs/page.test.tsx`.
- **Docker:** rebuilt and restarted the `portal` container.
- **Live browser verification:** logged in as `tenant_admin` (demo-corp), opened the Manual
  workspace, clicked "＋ Assign Task", clicked "Select all (3)" (all 3 processed-document
  checkboxes checked, "Assign 3 documents" button text confirmed), chose an annotator, and
  submitted — all 3 tasks were created in one action, a toast read "3 tasks assigned
  successfully", and the form closed automatically (screenshots captured at each step).

---

## 5. Audit Record

- [ ] Human reviewer has re-run the test suites above independently.
- [ ] Human reviewer has live-verified multi-document assignment in the browser.
- [ ] Human reviewer sign-off: ______________________ Date: ______________
