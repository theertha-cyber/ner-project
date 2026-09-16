# Verification Plan

**Change:** tenant-admin-console-nav-restructure
**Generated:** 2026-09-09
**Status:** 🟢 VERIFIED (commits `3747e25`, `f5febdf`) — frontend + Python suite green (ad-hoc container run against `ner_test`, 2026-09-10); Audit Record completed by the implementing agent at the project owner's direction (see §6 caveats).

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
| 9 | nav-config | Method Landing Routes and Legacy Redirects | legacy schema-proposals route redirects | `/schema-proposals` → `/annotate/automated/schema` | `next.config.js` redirects + `app/(auth)/schema-proposals/page.tsx` redirect shim (code review, §5 row 7) | - [x] |
| 10 | nav-config | Method Landing Routes and Legacy Redirects | automated step routes are tenant-admin only | annotator redirected away from `/annotate/automated/prelabel` | `app/(auth)/annotate/automated/layout.tsx` `RequireAuth roles={["tenant_admin"]}` (code review, §5 row 7) | - [x] |
| 11 | nav-config | Method Landing Routes and Legacy Redirects | the annotation workspace route is unchanged | `/annotation` renders the 3-pane workspace | `app/(auth)/annotation/page.tsx` untouched by this change — `git diff` (code review) | - [x] |
| 12 | notifications | Notification Storage | A notification row is persisted | inserted row retrievable with its fields and null `read_at` | `tests/test_annotation_workspace.py::test_task_completion_marks_training_eligible_and_notifies` | - [x] |
| 13 | notifications | Notification Read API | A tenant admin sees a tenant-admin-addressed notification | appears in `GET /api/v1/notifications`, counts toward `unread` | `tests/test_notifications_api.py::test_tenant_admin_sees_role_notification` | - [x] |
| 14 | notifications | Notification Read API | A business user does not see annotation notifications | excluded from the response | `tests/test_notifications_api.py::test_business_user_excluded` | - [x] |
| 15 | notifications | Notification Read API | Cross-tenant isolation | tenant B does not see tenant A's notification | `tests/test_notifications_api.py::test_cross_tenant_isolation` | - [x] |
| 16 | notifications | Notification Read API | Marking one notification read | `read_at` set, drops from `unread` | `tests/test_notifications_api.py::test_mark_one_read` | - [x] |
| 17 | notifications | Notification Read API | Marking a notification that is not the caller's | 404, unchanged | `tests/test_notifications_api.py::test_mark_foreign_notification_404` | - [x] |
| 18 | notifications | Notification Bell | Unread badge reflects the unread count | badge shows `3` for 3 unread | `NotificationBell.tsx` renders `unread` from `useNotifications()` as a badge chip (code review) — dedicated portal test not added | - [~] |
| 19 | notifications | Notification Bell | The bell is absent for a business user | no bell in the topbar | `Topbar.tsx` renders `<NotificationBell>` only for `tenant_admin`/`annotator` (code review) — dedicated portal assertion not added | - [~] |
| 20 | task-assignment-ui | Annotation Task Endpoint Role Gates | An annotator cannot create a task | `POST /api/v1/annotation-tasks` → 403 | `tests/test_annotation_workspace.py::test_task_create_rejects_annotator` | - [x] |
| 21 | task-assignment-ui | Annotation Task Endpoint Role Gates | A business user cannot create or list tasks | both → 403 | `tests/test_annotation_workspace.py::test_task_create_rejects_business_user`, `::test_task_list_rejects_business_user` | - [x] |
| 22 | task-assignment-ui | Annotation Task Endpoint Role Gates | A tenant admin can create a task | 201 | `tests/test_annotation_workspace.py::test_7_10_task_create_returns_201` (token updated to tenant_admin) | - [x] |
| 23 | task-assignment-ui | Task Completion Is Final Approval | Completing a task marks it training-eligible and notifies the tenant admin | `training_eligible: true`, `training_eligible_at` set, notification row exists | `tests/test_annotation_workspace.py::test_task_completion_marks_training_eligible_and_notifies` | - [x] |
| 24 | task-assignment-ui | Task Completion Is Final Approval | Re-completing an already-completed task does not re-notify | no second notification, timestamp unchanged | `tests/test_annotation_workspace.py::test_task_recomplete_completed_task_is_idempotent` | - [x] |
| 25 | task-assignment-ui | Task Completion Is Final Approval | A completion has no Tenant Admin review step | only onward action is request-training | `/annotate/manual` exposes no "review annotations" control post-completion (code review) — dedicated portal test not added | - [~] |

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
- [x] Rows 9–11 — legacy route pages / `next.config.js` redirects / automated-layout guard confirmed by code review (§5 row 7); `/annotation` untouched by this change's diff.
- [x] Rows 12–17, 20–24 — `pytest tests/test_annotation_workspace.py tests/test_notifications_api.py` → 38 passed against `ner_test` (§5 rows 4, 5).
- [~] Rows 18–19, 25 — bell badge / bell-absence / no-review-action confirmed by code review; dedicated portal assertions not added (tracked in §8).

### Structural Evidence
- [x] `navFor` returns a `section | link` union; `system_admin`/`business_user` stay flat — code review
- [x] Legacy route pages are `redirect()` shims, not deletions — code review
- [x] `tasks.py` role gates are backend `Depends` calls (`require_tenant_admin`, `require_roles`, `require_annotator_or_tenant_admin`) — code review + rows 20–22
- [x] `notify.py` is the single notification writer; imported only by `annotation_service` — grep confirms no `gateway` import
- [x] `git diff` migration `041` is additive only (new table + `ADD COLUMN`) — code review

### Edge Case Evidence
- [x] Risk 1 — legacy routes redirect, no deletion (code review, §5 row 7)
- [x] Risk 2 — notification fires exactly once per completion (`test_task_recomplete_completed_task_is_idempotent`)
- [x] Risk 3 — RBAC enforced at the API (`test_task_create_rejects_annotator` / `_business_user`)
- [x] Risk 4 — notification audience filtered by role (`test_business_user_excluded`)
- [x] Risk 5 — tenant_id from request context, never the body (`test_cross_tenant_isolation` + code review of `get_request_tenant_id`)

---

## 5. Evidence Log

| # | Evidence Type | Description / Link | Scenario(s) Covered | Collected By | Date |
|---|--------------|-------------------|---------------------|--------------|------|
| 1 | test output | `ner-portal-test`: `vitest run src/lib/nav-config.test.ts` → 10 passed | 1–3, 5–8 | agent | 2026-09-09 |
| 2 | test output | `ner-portal-test`: `vitest run src/components/app-shell/sidebar.test.tsx` → 13 passed | 4 | agent | 2026-09-09 |
| 3 | test output | `ner-portal-test`: targeted `vitest run src/lib src/components src/app` → 167 passed, 1 pre-existing unrelated failure (`training-jobs/page.test.tsx`) | regression check | agent | 2026-09-09 |
| 4 | test output | `annotation_service` container / `ner_test`: `pytest tests/test_notifications_api.py` → 5 passed (role-addressed read, business-user exclusion, cross-tenant isolation, mark-one-read, foreign-notification 404) | 13–17 | agent | 2026-09-10 |
| 5 | test output | `annotation_service` container / `ner_test`: `pytest tests/test_annotation_workspace.py` → 33 passed (incl. `test_task_create_rejects_annotator`, `::_rejects_business_user`, `test_task_list_rejects_business_user`, `test_7_10_task_create_returns_201` w/ tenant_admin token, `test_task_completion_marks_training_eligible_and_notifies`, `test_task_recomplete_completed_task_is_idempotent`) | 12, 20–24 | agent | 2026-09-10 |
| 6 | code review | `gateway/api/v1/notifications.py` — every read/update `WHERE` clause carries `tenant_id = :tenant_id AND (recipient_role = :role OR recipient_user_id = :uid)`; `tenant_id` from `get_request_tenant_id` (request context), `role` from `require_tenant_role`, never the body | Risks 4, 5; rows 14, 15 | agent | 2026-09-10 |
| 7 | code review | Legacy `schema-proposals` / `prelabel-batches` / `retraining` `page.tsx` are `redirect()` shims (not deleted); `next.config.js` `redirects()` maps the old paths; `annotate/automated/layout.tsx` wraps steps in `RequireAuth roles={["tenant_admin"]}` | Risk 1; rows 9, 10 | agent | 2026-09-10 |

---

## 6. Audit Record

> Completed by the implementing agent at the project owner's direction — see the sign-off
> note below. This is NOT an independent human review. The Python-side functional evidence
> (rows 12–24) was collected in an ad-hoc container run against `ner_test`.

**Change slug:** tenant-admin-console-nav-restructure
**Spec files reviewed:** specs/nav-config/spec.md, specs/notifications/spec.md, specs/task-assignment-ui/spec.md

### Reviewer Sign-Off

| Check | Status |
|-------|--------|
| Design reviewed against proposal | - [x] |
| All ADRs in Section 3 verified compliant | - [x] |
| Spec Alignment table complete | - [x] |
| Evidence Log populated with real evidence | - [x] |
| All functional evidence items checked | - [x] (rows 18–19, 25 by code review, not a dedicated portal test) |
| All structural evidence items checked | - [x] |
| All edge case evidence items checked | - [x] |

### AI Output Review

| Check | Status |
|-------|--------|
| All generated artifacts reviewed for spec alignment | - [x] |
| No hallucinated requirements introduced | - [x] |
| No AI-invented fields, endpoints, or behaviours present | - [x] |
| Every THEN clause has a corresponding evidence entry | - [x] |
| Hallucination risk register reviewed and mitigations confirmed | - [x] |

**Archive approved by:** Claude (implementing agent), at the direction of the project owner (theertha@inapp.com), 2026-09-10.

> This is **not** an independent human review — the same agent implemented the change. The checks above reflect the agent's own re-inspection of the diff against the spec and the test runs in Section 7.

**Date:** 2026-09-10

**Caveats carried into the archive:**
- The Python suite ran in an ad-hoc `ner-project-annotation_service-1` container (pytest pip-installed, repo `docker cp`-ed) against `postgres-test` / `ner_test`, not the project's normal CI runner. Re-run `pytest` + `npm test` in the standard environment to confirm.
- Migration `041` has **not** been applied to a long-lived database (`alembic upgrade head`).
- Rows 18–19 and 25 (NotificationBell badge, bell absence for business_user, no post-completion review control) are backed by code review only; dedicated portal assertions were not added.

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

### Backend (executed 2026-09-10)

Run in the `ner-project-annotation_service-1` container (pytest pip-installed, repo
`docker cp`-ed) against `postgres-test` / `ner_test`, `NER_DATABASE_URL` +
`NER_DATABASE_URL_SYNC` pointed at it:

```
tests/test_annotation_workspace.py                33 passed
tests/test_notifications_api.py                    5 passed
```

Covers rows 12–17 and 20–24: annotation-task RBAC (annotator/business_user 403, tenant_admin
201), completion → `training_eligible_at` + single tenant-admin notification, re-completion
idempotent; notifications read API role/tenant/audience scoping and mark-read 404.
Migration `041` still needs `alembic upgrade head` on the deployment DB.

---

## 8. Outstanding Items

- Re-run `pytest` + `npm test` in the standard CI environment (this run was an ad-hoc container).
- `alembic upgrade head` on the deployment DB (migration `041`).
- Add dedicated portal assertions for the NotificationBell badge / bell-absence (rows 18–19)
  and the no-review-action state (row 25) — currently code-review only.
- Optional: an independent human review of the diff (this Audit Record was completed by the
  implementing agent).
