# Verification Plan

**Change:** tenant-admin-console-nav-restructure
**Generated:** 2026-09-09
**Status:** 🟡 IMPLEMENTED (commits `3747e25`, `f5febdf`) — frontend verified; Python suite pending a run in a full test environment; Audit Record unsigned.

---

## 1. Spec Alignment

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | nav-config | Role Navigation Matrix | system_admin nav | `navFor("system_admin")` returns 4 flat leaves, no sections; no Settings | `src/portal/src/lib/nav-config.test.ts` | - [x] |
| 2 | nav-config | Role Navigation Matrix | tenant_admin nav | Annotate/Setup/Admin sections in order; Annotate links `/annotate/{manual,automated,import}`; no Settings | `src/portal/src/lib/nav-config.test.ts` | - [x] |
| 3 | nav-config | Role Navigation Matrix | annotator nav | flattened links include manual+import, exclude automated; no Settings | `src/portal/src/lib/nav-config.test.ts` | - [x] |
| 4 | nav-config | Role Navigation Matrix | a section with no permitted links is dropped | no empty `Setup`/`Admin` header rendered | `src/portal/src/components/app-shell/sidebar.test.tsx` | - [x] |
| 5 | nav-config | Role Navigation Matrix | business_user nav | `navFor("business_user")` returns 4 flat leaves, no sections; no Settings | `src/portal/src/lib/nav-config.test.ts` | - [x] |
| 6 | nav-config | Screen Title Map | known screen lookup | `SCREEN_TITLES["tenants"]` is `["Tenants","/admin/tenants"]`; keys exist for the three `/annotate/*` landings | `src/portal/src/lib/nav-config.test.ts` | - [x] |
| 7 | nav-config | Screen Title Map | unknown screen fallback | `resolveScreenTitle` of an off-tree, off-map path returns `["Dashboard","/dashboard"]` | `src/portal/src/lib/nav-config.test.ts` | - [x] |
| 8 | nav-config | Screen Title Map | breadcrumb for a nested workspace route | `crumbsFor(..., "/annotation")` → `["Annotate","Manual","Workspace"]` | `src/portal/src/lib/nav-config.test.ts` | - [x] |
| 8a | nav-config | Screen Title Map | breadcrumb for an automated step route | trail ends with the step label under Annotate › Automated | `src/portal/src/lib/nav-config.test.ts` | - [x] |
| 8b | nav-config | Screen Title Map | breadcrumb falls back to the title map for an off-tree route | `crumbsFor(..., "/settings")` → `["Settings"]` | `src/portal/src/lib/nav-config.test.ts` | - [x] |
| 9 | nav-config | Method Landing Routes and Legacy Redirects | legacy schema-proposals route redirects | `/schema-proposals` → `/annotate/automated/schema` | `next.config.js` redirects + `app/(auth)/schema-proposals/page.tsx` redirect shim (manual check) | - [ ] |
| 10 | nav-config | Method Landing Routes and Legacy Redirects | automated step routes are tenant-admin only | annotator redirected away from `/annotate/automated/prelabel` | `app/(auth)/annotate/automated/layout.tsx` `RequireAuth roles={["tenant_admin"]}` (manual check) | - [ ] |
| 11 | nav-config | Method Landing Routes and Legacy Redirects | the annotation workspace route is unchanged | `/annotation` renders the 3-pane workspace | manual check | - [ ] |
| 12 | notifications | Notification Storage | A notification row is persisted | inserted row retrievable with its fields and null `read_at` | `tests/test_annotation_workspace.py::test_task_completion_marks_training_eligible_and_notifies` | - [ ] |
| 13 | notifications | Notification Read API | A tenant admin sees a tenant-admin-addressed notification | appears in `GET /api/v1/notifications`, counts toward `unread` | `tests/test_notifications_api.py::test_tenant_admin_sees_role_notification` | - [ ] |
| 14 | notifications | Notification Read API | A business user does not see annotation notifications | excluded from the response | `tests/test_notifications_api.py::test_business_user_excluded` | - [ ] |
| 15 | notifications | Notification Read API | Cross-tenant isolation | tenant B does not see tenant A's notification | `tests/test_notifications_api.py::test_cross_tenant_isolation` | - [ ] |
| 16 | notifications | Notification Read API | Marking one notification read | `read_at` set, drops from `unread` | `tests/test_notifications_api.py::test_mark_one_read` | - [ ] |
| 17 | notifications | Notification Read API | Marking a notification that is not the caller's | 404, unchanged | `tests/test_notifications_api.py::test_mark_foreign_notification_404` | - [ ] |
| 18 | notifications | Notification Bell | Unread badge reflects the unread count | badge shows `3` for 3 unread | `src/portal/src/components/app-shell/*` (bell) — portal test to add | - [ ] |
| 19 | notifications | Notification Bell | The bell is absent for a business user | no bell in the topbar | `src/portal/src/components/app-shell/sidebar.test.tsx` (Topbar) — assertion to add | - [ ] |
| 20 | task-assignment-ui | Annotation Task Endpoint Role Gates | An annotator cannot create a task | `POST /api/v1/annotation-tasks` → 403 | `tests/test_annotation_workspace.py::test_task_create_rejects_annotator` | - [ ] |
| 21 | task-assignment-ui | Annotation Task Endpoint Role Gates | A business user cannot create or list tasks | both → 403 | `tests/test_annotation_workspace.py::test_task_create_rejects_business_user`, `::test_task_list_rejects_business_user` | - [ ] |
| 22 | task-assignment-ui | Annotation Task Endpoint Role Gates | A tenant admin can create a task | 201 | `tests/test_annotation_workspace.py::test_7_10_task_create_returns_201` (token updated to tenant_admin) | - [ ] |
| 23 | task-assignment-ui | Task Completion Is Final Approval | Completing a task marks it training-eligible and notifies the tenant admin | `training_eligible: true`, `training_eligible_at` set, notification row exists | `tests/test_annotation_workspace.py::test_task_completion_marks_training_eligible_and_notifies` | - [ ] |
| 24 | task-assignment-ui | Task Completion Is Final Approval | Re-completing an already-completed task does not re-notify | no second notification, timestamp unchanged | `tests/test_annotation_workspace.py::test_task_recomplete_completed_task_is_idempotent` (extend to assert notification count) | - [ ] |
| 25 | task-assignment-ui | Task Completion Is Final Approval | A completion has no Tenant Admin review step | only onward action is request-training | portal check — no "review annotations" control on `/annotate/manual` after completion | - [ ] |

---

## 2. Hallucination Risk Register

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|-------------------|----------------------|
| 1 | Route deletion (Decision 2) | A legacy route's page file is deleted rather than turned into a redirect, breaking a deep link | Confirm `schema-proposals`/`prelabel-batches`/`retraining` `page.tsx` still exist and `redirect()` to the step route; confirm `next.config.js` redirects. |
| 2 | Notification double-write (Decision 4) | The notification is written outside the status-update transaction or unconditionally, so a retried PATCH double-notifies | Execute Scenario 24; read the transaction boundary in `tasks.py`. |
| 3 | RBAC only in the UI | The role gate is added to the sidebar/`RequireAuth` but not to `tasks.py`, so a direct API call still succeeds | Execute Scenarios 20, 21 against the API directly. |
| 4 | Notification audience leak | `GET /api/v1/notifications` filters by tenant but not by role, so a `business_user` sees tenant-admin notices | Execute Scenario 14; read the `WHERE` clause. |
| 5 | Cross-tenant read | The notifications query trusts a client-supplied tenant or omits the `tenant_id` filter | Execute Scenario 15; confirm `tenant_id` comes from the resolved request context. |

---

## 3. Pattern & ADR Compliance

| ADR | Constraint | Verification Step |
|-----|-----------|-------------------|
| ADR-001 tenant-data-isolation | `notifications` in `public` with a `tenant_id` filter on every read; `annotation_tasks` per-tenant-schema | Read the migration and every query in `gateway/api/v1/notifications.py`. |
| ADR-012 annotation-fix-deployment-topology | Writes in `annotation_service`, reads in `gateway` | Confirm `services/notify.py` is imported only by `annotation_service`; the read API is a gateway router. |

---

## 4. Evidence Requirements

### Functional Evidence
- [x] Rows 1–8 — portal `nav-config` + `sidebar` vitest suites pass (13/13 sidebar+topbar, 10/10 nav-config) in the `ner-portal-test` container.
- [ ] Rows 9–11 — manual route/redirect/guard checks in a running portal.
- [ ] Rows 12–17, 20–24 — Python suite (`tests/test_annotation_workspace.py` additions, `tests/test_notifications_api.py` to be added) run against `ner_test`.
- [ ] Rows 18–19, 25 — portal assertions for the bell and the no-review-action state.

### Structural Evidence
- [x] `navFor` returns a `section | link` union; `system_admin`/`business_user` stay flat — code review
- [x] Legacy route pages are `redirect()` shims, not deletions — code review
- [ ] `tasks.py` role gates are backend `Depends`/calls, not UI-only
- [ ] `notify.py` is the single notification writer; imported only by `annotation_service`
- [ ] `git diff` migration `041` is additive only

### Edge Case Evidence
- [ ] Risk 1 — legacy routes redirect, no deletion
- [ ] Risk 2 — notification fires exactly once per completion
- [ ] Risk 3 — RBAC enforced at the API
- [ ] Risk 4 — notification audience filtered by role
- [ ] Risk 5 — tenant_id from request context, never the body

---

## 5. Evidence Log

| # | Evidence Type | Description / Link | Scenario(s) Covered | Collected By | Date |
|---|--------------|-------------------|---------------------|--------------|------|
| 1 | test output | `ner-portal-test`: `vitest run src/lib/nav-config.test.ts` → 10 passed | 1–3, 5–8 | agent | 2026-09-09 |
| 2 | test output | `ner-portal-test`: `vitest run src/components/app-shell/sidebar.test.tsx` → 13 passed | 4 | agent | 2026-09-09 |
| 3 | test output | `ner-portal-test`: targeted `vitest run src/lib src/components src/app` → 167 passed, 1 pre-existing unrelated failure (`training-jobs/page.test.tsx`) | regression check | agent | 2026-09-09 |

---

## 6. Audit Record

> ⚠️ **GATE: signed by a human reviewer before archive.** The Python-side functional
> evidence (rows 12–24) is not yet collected — a full test-environment run is required
> before this section can be signed.

**Change slug:** tenant-admin-console-nav-restructure
**Spec files reviewed:** specs/nav-config/spec.md, specs/notifications/spec.md, specs/task-assignment-ui/spec.md

### Reviewer Sign-Off

| Check | Status |
|-------|--------|
| Design reviewed against proposal | - [ ] |
| All ADRs in Section 3 verified compliant | - [ ] |
| Spec Alignment table complete | - [ ] |
| Evidence Log populated with real evidence | - [ ] |
| All functional evidence items checked | - [ ] |
| All structural evidence items checked | - [ ] |
| All edge case evidence items checked | - [ ] |

### AI Output Review

| Check | Status |
|-------|--------|
| All generated artifacts reviewed for spec alignment | - [ ] |
| No hallucinated requirements introduced | - [ ] |
| No AI-invented fields, endpoints, or behaviours present | - [ ] |
| Every THEN clause has a corresponding evidence entry | - [ ] |
| Hallucination risk register reviewed and mitigations confirmed | - [ ] |

**Archive approved by:** ___________________________

**Date:** ___________

**Notes:**

- Implemented ahead of this write-up. The spec exists so `automated-annotation-guided-workflow`,
  `import-annotation-training-eligibility`, and `training-eligibility-overview` have a
  landed capability to depend on.
- Outstanding before archive: run the Python suite (`tests/test_annotation_workspace.py`
  additions + a new `tests/test_notifications_api.py`) against `ner_test`; add portal
  assertions for the bell.

---

## 7. Agent Verification Record

### Frontend (executed)

In the `ner-portal-test` container against a synced working tree:

```
vitest run src/lib/nav-config.test.ts                     10 passed
vitest run src/components/app-shell/sidebar.test.tsx       13 passed
vitest run src/lib src/components src/app (targeted)      167 passed | 1 failed
```

The single failure is `src/app/(auth)/training-jobs/page.test.tsx:153` (`findByText("Approve
& queue")`), which does not import `nav-config`, `Sidebar`, `Topbar`, or `AppShell` and
fails on the unmodified baseline — a pre-existing, unrelated flake.

`tsc --noEmit` reports no new errors in any file this change touches (the repo baseline has
pre-existing `tsc` errors in unrelated test files).

### Backend (not executed)

No Python/pytest environment is available to the agent (no interpreter on PATH; the service
containers lack pytest). The added tests (`tests/test_annotation_workspace.py`:
`test_task_create_rejects_annotator`, `test_task_create_rejects_business_user`,
`test_task_list_rejects_business_user`, `test_task_completion_marks_training_eligible_and_notifies`)
and a new `tests/test_notifications_api.py` must be run against `ner_test` in the user's
environment. `python -m py_compile` passes on every changed backend file. Migration `041`
must be applied (`alembic upgrade head`).

---

## 8. Outstanding Items

- Run the Python suite and fill rows 12–24 / §5 / §4.
- Add `tests/test_notifications_api.py` (rows 13–17).
- Add portal assertions for the bell (rows 18–19) and the no-review-action state (row 25).
- Human reviewer signs §6.
