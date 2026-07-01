# Verification Plan

**Change:** assign-annotation-tasks
**Generated:** 2026-06-29
**Status:** 🔴 Incomplete — Evidence Log and Audit Record must be filled by a human reviewer before archive.

---

## 1. Spec Alignment

Map every requirement and every scenario in this change to a testable acceptance criterion.

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | task-assignment-ui | Task Assignment Form | Assign Task button visible for tenant admin | Given a tenant_admin user on the annotation workspace, when the Task Queue panel renders, then a "＋ Assign Task" button is visible in the panel | Component test or manual check: button present in DOM for tenant_admin | - [ ] |
| 2 | task-assignment-ui | Task Assignment Form | Assign Task button hidden for annotator | Given an annotator user on the annotation workspace, when the Task Queue panel renders, then no "＋ Assign Task" button is in the DOM | Component test or manual check: button absent in DOM for annotator | - [ ] |
| 3 | task-assignment-ui | Task Assignment Form | Clicking Assign Task button expands the inline form | Given a tenant admin and collapsed form, when the button is clicked, then an inline form expands and both dropdowns begin loading | Component test: form is visible after click; dropdowns show loading state | - [ ] |
| 4 | task-assignment-ui | Task Assignment Form | Document dropdown lists only processed documents | Given the form is open and the tenant has processed/pending/failed documents, when the Document dropdown renders, then only processed documents appear as options | Component test: dropdown options filtered to status === "processed" | - [ ] |
| 5 | task-assignment-ui | Task Assignment Form | Annotator dropdown lists only annotator-role users | Given the form is open and the tenant has mixed-role users, when the Annotator dropdown renders, then only annotator-role users appear | Component test: dropdown options filtered to role === "annotator" | - [ ] |
| 6 | task-assignment-ui | Task Assignment Form | Assign button disabled until both fields are selected | Given the form is open, when only one dropdown has a selection, then the Assign button is disabled | Component test: button disabled attribute present until both fields selected | - [ ] |
| 7 | task-assignment-ui | Task Assignment Form | Successful task creation adds task to queue | Given both fields selected, when admin clicks Assign and backend returns 201, then new task is prepended to queue, form collapses, success toast shown | Component test with mock API: queue updates, form closes, toast fires | - [ ] |
| 8 | task-assignment-ui | Task Assignment Form | Duplicate assignment (409) shows inline error | Given a document with active task, when admin clicks Assign and backend returns 409, then form remains open, inline error message shown, queue unchanged | Component test with mock 409: error visible, form stays open | - [ ] |
| 9 | task-assignment-ui | Task Assignment Form | Cancel collapses form without submitting | Given the form is open with selections, when user clicks Cancel, then form collapses and no POST request is sent | Component test: no network call on cancel, form hidden | - [ ] |
| 10 | task-assignment-ui | Task Assignment Form | Empty annotator list shows descriptive message | Given no annotator-role users exist, when the Annotator dropdown renders, then "No annotators available — invite users first" message appears and Assign button is disabled | Component test with empty users mock: message visible, button disabled | - [ ] |
| 11 | portal-annotation | Annotation Task Queue | Task row shows filename and document metadata | Given a task for "invoice-2026-00417.pdf" with status "processed" and 12 spans, when the task queue renders, then the row shows filename as primary label and "processed · 12 spans" as subtitle | Existing test / manual check | - [ ] |
| 12 | portal-annotation | Annotation Task Queue | Active task row is highlighted | Given the first task is selected, when queue renders, then selected row has left border in primary color and tinted background; others do not | Existing test / manual check | - [ ] |
| 13 | portal-annotation | Annotation Task Queue | Annotator sees only assigned tasks | Given an annotator with 2 assigned tasks and 3 others, when workspace loads, then queue shows exactly 2 rows | Existing test / manual check | - [ ] |
| 14 | portal-annotation | Annotation Task Queue | Selecting a task loads the document | Given queue with 2+ tasks, when user clicks second row, then text, spans, and suggested spans are fetched for that document | Existing test / manual check | - [ ] |
| 15 | portal-annotation | Annotation Task Queue | Empty queue shows contextual message | Given no tasks for current user, when workspace loads, then "No tasks assigned" message with admin contact prompt appears | Existing test / manual check | - [ ] |
| 16 | portal-annotation | Annotation Task Queue | Tenant admin sees Assign Task button | Given a tenant_admin user, when Task Queue panel renders, then "＋ Assign Task" button appears above the task list | Manual check / component test | - [ ] |
| 17 | portal-annotation | Annotation Task Queue | Annotator does not see Assign Task button | Given an annotator user, when Task Queue panel renders, then "＋ Assign Task" button does not appear | Manual check / component test | - [ ] |

---

## 2. Hallucination Risk Register

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|-------------------|----------------------|
| 1 | Role gate logic | AI may gate on a wrong field (e.g., `user.email` or `user.tenantSlug`) instead of `user.role === "tenant_admin"` | Confirm the conditional rendering reads `user.role` from `useAuth()`, not any other user property |
| 2 | Client-side dropdown filtering | AI may skip the `status: "processed"` filter on documents or the `role: "annotator"` filter on users, showing all records | Inspect filtering logic: documents must be filtered to `status === "processed"` and users to `role === "annotator"` before populating dropdowns |
| 3 | Optimistic update payload shape | AI may construct the optimistic task object with wrong field names (e.g., `userId` vs `annotator_user_id`) causing a render mismatch in the task queue row | Compare the fields in the optimistic task object against `AnnotationTask` interface in `TaskQueue.tsx` (id, document_id, annotator_user_id, status, filename, etc.) |
| 4 | POST payload | AI may send `{ user_id, doc_id }` instead of the spec-required `{ document_id, annotator_user_id }` | Intercept the POST request in a test or network tab and verify field names match `annotation-workspace` spec |
| 5 | 409 error surfacing | AI may close the form or show a toast instead of an inline error, violating the spec requirement that the form remains open | Verify 409 response: form is still mounted, inline error message rendered within the form, task list unchanged |
| 6 | Lazy fetch timing | AI may fetch users/documents on workspace mount for all users rather than only when the form opens | Confirm React Query `enabled` flag is tied to form open state; network tab should show no `/api/v1/users` call until the form is opened by a tenant_admin |

---

## 3. Pattern & ADR Compliance

| ADR | Decision Summary | Constraint on This Change | Verification Step |
|-----|-----------------|--------------------------|-------------------|
| ADR-001-tenant-data-isolation | All data is scoped per tenant via JWT; no cross-tenant reads | Users and documents fetched must be scoped to the admin's tenant — `authFetch` must carry the JWT | Confirm `authFetch` (not raw `fetch`) is used for all new API calls in the assignment form |
| ADR-004-openspec-governance | Spec-driven workflow; specs required before implementation | `task-assignment-ui` spec and `portal-annotation` delta spec must exist before implementation begins | Confirm both spec files exist at their expected paths in this change before `/opsx:apply` is run |
| ADR-005-opencode-agent-boundaries | Frontend only calls defined API contracts; no new backend endpoints invented | The assignment form must call only existing endpoints: `GET /api/v1/documents`, `GET /api/v1/users`, `POST /api/v1/annotation-tasks` | Grep the new components for any endpoint not listed here — any unknown endpoint path is a violation |

---

## 4. Evidence Requirements

### Functional Evidence

- [ ] Scenario 1 (button visible for admin): Screenshot or test output showing "＋ Assign Task" button present in DOM for tenant_admin user
- [ ] Scenario 2 (button hidden for annotator): Test output confirming button is absent from DOM for annotator user
- [ ] Scenario 3 (form expands on click): Screenshot or test showing inline form visible after button click, with dropdowns in loading state
- [ ] Scenario 4 (document filter): Test output showing only `processed` documents appear in dropdown; pending/failed documents excluded
- [ ] Scenario 5 (annotator filter): Test output showing only `annotator`-role users appear in dropdown
- [ ] Scenario 6 (Assign button disabled): Test output showing button disabled attribute when one or both fields unselected
- [ ] Scenario 7 (successful creation): Test output or API trace showing 201 POST, new task prepended to list, form collapsed, success toast fired
- [ ] Scenario 8 (409 inline error): Test output showing form stays open, inline error message rendered, no queue update on 409
- [ ] Scenario 9 (cancel): Test output confirming no POST request on cancel and form collapses
- [ ] Scenario 10 (empty annotator list): Test output showing "No annotators available" message and disabled Assign button
- [ ] Scenarios 11–15 (existing task queue behaviours): Existing tests still pass (no regression)
- [ ] Scenario 16 (admin sees button): Manual check in browser as tenant_admin
- [ ] Scenario 17 (annotator does not see button): Manual check in browser as annotator

### Structural Evidence

- [ ] Code review completed — implementation matches design.md decisions (no undocumented deviations)
- [ ] All ADR compliance steps in Section 3 confirmed ✓
- [ ] No undocumented architectural patterns introduced
- [ ] No AI-invented requirements present in generated code (cross-checked against spec files)

### Edge Case Evidence

- [ ] Risk 1 (role gate): Confirmed `user.role === "tenant_admin"` is the exact condition used, verified by reading the rendered component
- [ ] Risk 2 (dropdown filters): Confirmed client-side filter code for both documents (`status === "processed"`) and users (`role === "annotator"`) is present and correct
- [ ] Risk 3 (optimistic payload shape): Confirmed optimistic task object fields match `AnnotationTask` interface exactly
- [ ] Risk 4 (POST payload): API call intercepted in test/network tab; fields are `document_id` and `annotator_user_id`
- [ ] Risk 5 (409 handling): 409 scenario tested with mock; form stays open, inline error shown
- [ ] Risk 6 (lazy fetch): Network tab confirms no user/document API calls until form is opened

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

**Change slug:** assign-annotation-tasks
**Proposal:** `openspec/changes/assign-annotation-tasks/proposal.md`
**Spec files reviewed:**
- specs/task-assignment-ui/spec.md
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
