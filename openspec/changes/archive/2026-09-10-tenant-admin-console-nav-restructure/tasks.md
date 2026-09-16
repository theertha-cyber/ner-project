## 1. Navigation (Phase 2 — done)

- [x] 1.1 `src/portal/src/lib/nav-config.ts`: `NavItem` becomes a `NavSection | NavLeaf` union; `navFor` returns a grouped tree for `tenant_admin`/`annotator` and a flat list for `system_admin`/`business_user`; add `flattenNav`, `crumbsFor`, `resolveScreenTitle`.
- [x] 1.2 `SCREEN_TITLES`: add keys for `/annotate/manual`, `/annotate/automated`, `/annotate/automated/{schema,prelabel,retrain}`, `/annotate/import`; retain legacy-route keys.
- [x] 1.3 `Sidebar.tsx`: render non-navigable section headers; a section with zero permitted links is dropped; sub-screen `children` are not rendered as rows.
- [x] 1.4 `Topbar.tsx`: derive a `section › landing › screen` breadcrumb via `crumbsFor(navFor(user.role), pathname)`.
- [x] 1.5 Landing routes `app/(auth)/annotate/{manual,automated,import}/page.tsx` + `AnnotateLanding` component + `AutomatedStepper` + `annotate/automated/layout.tsx` (`RequireAuth roles={["tenant_admin"]}` + stepper).
- [x] 1.6 Step routes `annotate/automated/{schema,prelabel,retrain}/page.tsx` wrapping the existing `SchemaProposalPage` / `BatchAcceptancePage` / `RetrainingDecisionPage`.
- [x] 1.7 Legacy `/schema-proposals`, `/prelabel-batches`, `/retraining` → `redirect()` shims + `next.config.js` `redirects()`.
- [x] 1.8 `nav-config.test.ts` + `sidebar.test.tsx` updated; 3 obsolete glyph-icon assertions refreshed.
- [ ] 1.9 Add portal tests: legacy-route redirect (scenario 9), automated-route annotator guard (scenario 10), `/annotation` unchanged (scenario 11).

## 2. Notifications infrastructure (Phase 3 — done)

- [x] 2.1 Migration `041`: `public.notifications` (+ `idx_notifications_tenant_role_unread`); `annotation_tasks.training_eligible_at`; `prelabel_batches.annotator_review_status` / `training_eligible_at`; `{schema}.annotation_imports` (staged for later changes).
- [x] 2.2 `src/annotation_service/services/notify.py`: `notify(session, *, tenant_id, kind, title, body, recipient_role, recipient_user_id, resource_type, resource_id)`.
- [x] 2.3 `src/gateway/api/v1/notifications.py`: `GET /api/v1/notifications` (tenant + role/user scoped, `unread` count), `POST /{id}/read`, `POST /read-all`; registered in `gateway/main.py`.
- [x] 2.4 `scripts/setup_test_db.py` (`public.notifications`), `tests/conftest.py` + `tests/test_annotation_workspace.py` fixtures (column + table).
- [x] 2.5 Portal: `hooks/use-notifications.ts`, `components/app-shell/NotificationBell.tsx`, wired into `Topbar` for `tenant_admin`/`annotator`.
- [ ] 2.6 Add `tests/test_notifications_api.py`: `test_tenant_admin_sees_role_notification`, `test_business_user_excluded`, `test_cross_tenant_isolation`, `test_mark_one_read`, `test_mark_foreign_notification_404`. (Scenarios 13–17)
- [ ] 2.7 Add a portal assertion that the bell is absent for `business_user`. (Scenario 19)

## 3. Annotation-task RBAC + completion hook (Phase 3 — done)

- [x] 3.1 `src/annotation_service/api/v1/_rbac.py`: `require_roles`, `require_tenant_admin`, `require_annotator_or_tenant_admin`.
- [x] 3.2 `tasks.py`: `POST` requires `tenant_admin`; `GET` requires `tenant_admin`|`annotator`; `PATCH` requires `annotator`|`tenant_admin`.
- [x] 3.3 `tasks.py`: on `→ completed` from a non-`completed` state, set `training_eligible_at` and call `notify(kind="annotation_task_completed", recipient_role="tenant_admin", resource_type="annotation_task", resource_id=task_id)` in the same transaction; response gains `training_eligible`.
- [x] 3.4 `tests/test_annotation_workspace.py`: `test_task_create_rejects_annotator`, `test_task_create_rejects_business_user`, `test_task_list_rejects_business_user`, `test_task_completion_marks_training_eligible_and_notifies`; existing create-task tests moved to a `tenant_admin` token.
- [ ] 3.5 Extend `test_task_recomplete_completed_task_is_idempotent` to assert exactly one notification row. (Scenario 24)

## 4. Verification

- [x] 4.1 Frontend: `nav-config` + `app-shell` vitest suites pass; targeted regression run 167/168 (1 pre-existing unrelated failure); no new `tsc` errors. Recorded in verification.md §5 / §7.
- [ ] 4.2 Run the Python suite against `ner_test` (apply migration `041` first); fill verification.md rows 12–24, §4, §5.
- [ ] 4.3 Complete the structural + edge-case evidence in verification.md §4.
- [ ] 4.4 Human reviewer signs verification.md §6.
