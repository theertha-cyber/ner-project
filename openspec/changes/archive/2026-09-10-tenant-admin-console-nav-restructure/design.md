## Context

The Tenant Admin sidebar was 13 flat items (`src/portal/src/lib/nav-config.ts`). Manual,
automated, and import annotation each had one or more top-level entries with no shared
home. `NavItem` was a flat record. There was no notification mechanism anywhere in the
codebase (`grep -r notification src/**/*.py` → nothing), and the `annotation_service`
task endpoints (`tasks.py`) had no role enforcement — only `review.py` did.

The design ZIP ("Tenant-admin navigation restructure") specifies a grouped IA with three
method landing pages, a persistent stepper for the automated sequence, and a persistent
completion notification the Tenant Admin sees before proceeding to training.

## Goals / Non-Goals

**Goals**
- Group navigation by annotation method; keep every existing route working.
- Enforce annotation-task RBAC in the backend, not just the UI.
- Give the Tenant Admin a persistent, server-backed record that an annotator finished.
- Establish the `training_eligible_at` marker and the notification infrastructure the
  automated and import changes will reuse.

**Non-Goals**
- No change to `system_admin` or `business_user` navigation.
- No change to the annotation workspace, review queue, or the seed-bootstrap endpoints
  beyond the task RBAC.
- No WebSocket/SSE — the bell polls.
- No second Tenant Admin annotation-review step (explicitly removed from the model).

## Currently-In-Force ADRs

| ADR | Constraint |
|-----|-----------|
| ADR-001 tenant-data-isolation | `notifications` is in `public` with a `tenant_id` column and every read is tenant-scoped, matching `audit_events`. `annotation_tasks` stays per-tenant-schema. |
| ADR-012 annotation-fix-deployment-topology | Notification *writes* live in `annotation_service`; notification *reads* live in `gateway` (the portal's API host). |

## Decisions

### Decision 1: `NavItem` becomes a `section | link` union; sub-screens stay out of the sidebar

A `NavSection` renders a non-navigable header; its `items` are `NavLeaf`s. A `NavLeaf` may
carry `children` used only for breadcrumb derivation and landing-page tab strips — they are
not sidebar rows. `system_admin`/`business_user` keep returning a flat `NavLeaf[]` (the
union permits it). This keeps the sidebar at ~8 rows while making the method the primary
axis.

### Decision 2: Three new landing routes; legacy routes redirect, never deleted

`/annotate/{manual,automated,import}` are added. `/annotate/automated/{schema,prelabel,retrain}`
wrap the existing `SchemaProposalPage` / `BatchAcceptancePage` / `RetrainingDecisionPage`
components under a stepper layout. `/schema-proposals`, `/prelabel-batches`, `/retraining`
redirect (both `next.config.js` redirects and server-component `redirect()` shims) so
bookmarks and deep links survive.

### Decision 3: `notifications` in `public`, addressed to a role

Cross-cutting infrastructure like `audit_events` lives in `public`; the gateway reads it
without a per-tenant-schema switch. A notification is addressed to `recipient_role`
(`"tenant_admin"`) rather than a user, because "the Tenant Admin" is a position — whichever
tenant admin opens the portal should see it. `recipient_user_id` is available for the cases
that are one person's.

### Decision 4: Completion is the single approval; the notification is guarded to fire once

`PATCH .../{id}` to `completed` from a non-`completed` state, in one transaction: set
`status`, set `training_eligible_at`, write the notification. A re-`complete` is a no-op
(the state machine already treats `completed → completed` as idempotent) and writes no
second notification.

## Risks / Trade-offs

- **Stale `nav-config` canonical spec.** The pre-existing `openspec/specs/nav-config/spec.md`
  described an older nav than even the pre-change code. This delta rewrites the Role
  Navigation Matrix to the new structure; reconciling every stale line of the old spec is
  out of scope.
- **Bell polling.** 60s poll, not push. Acceptable for a completion notification whose
  latency budget is minutes.
- **`business_user` 403 on task list.** A previously-permissive endpoint becomes
  restrictive; no known `business_user` caller exists, but flagged for the reviewer.

## Migration Plan

Migration `041` (applied): `public.notifications` + index;
`annotation_tasks.training_eligible_at`; plus `prelabel_batches.annotator_review_status` /
`training_eligible_at` and `{schema}.annotation_imports` staged for the automated/import
changes. `scripts/setup_test_db.py` and `tests/conftest.py` / `tests/test_annotation_workspace.py`
fixtures updated.

## Open Questions

(resolved) — route prefix `/annotate/*`, Models & Training top-level, annotator gets
review-only Import, notifications in `public`.
