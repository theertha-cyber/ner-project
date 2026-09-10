## Why

The Tenant Admin's sidebar had grown to 13 flat items with the three ways a dataset gets
built — manual, automated, import — scattered across the list, and there was no persistent
place for the Tenant Admin to learn that an annotator had finished their work. This change
restructures the navigation around the three annotation methods and adds the persistent
completion notification the workflow depends on. It is the foundation the
`automated-annotation-guided-workflow`, `import-annotation-training-eligibility`, and
`training-eligibility-overview` changes build on.

**This change is already implemented** — in commits `3747e25` (navigation) and `f5febdf`
(RBAC + notifications). It is written up here so the spec record is coherent and the
dependent changes have a landed capability to reference.

## What Changes

- **Grouped navigation.** `navFor(role)` returns a two-level tree: `NavItem` becomes a
  `section | link` union. The `tenant_admin` and `annotator` trees are grouped into
  `Annotate` / `Setup` / `Admin` sections; `system_admin` and `business_user` stay flat.
  Section headers are non-navigable and a section with zero permitted links is dropped.
- **Method landing routes.** Three landing routes are added — `/annotate/manual`,
  `/annotate/automated`, `/annotate/import` — plus the automated step routes
  `/annotate/automated/{schema,prelabel,retrain}` under a persistent stepper. No existing
  route is removed; the legacy `/schema-proposals`, `/prelabel-batches`, `/retraining`
  redirect to their step equivalents.
- **Breadcrumbs.** The topbar derives a `section › landing › screen` breadcrumb by walking
  the active role's nav tree.
- **RBAC on annotation-task endpoints.** `POST /api/v1/annotation-tasks` requires
  `tenant_admin`; `GET` excludes `business_user`; `PATCH` requires `annotator` or
  `tenant_admin`. (These endpoints previously had no role gate.)
- **Persistent notifications.** A `public.notifications` table, a
  `GET/POST /api/v1/notifications` gateway API (tenant + role/user scoped), a writer in
  `annotation_service`, and a topbar bell. When an annotator marks a task completed —
  their final approval, with no second Tenant Admin review — the task is stamped
  `training_eligible_at` and a `tenant_admin`-addressed notification is written.

## Capabilities

### New Capabilities

- `notifications`: persistent, per-tenant notifications addressed to a role or a specific
  user, read via a gateway API and rendered as a topbar bell, written by services when
  work crosses a line the recipient needs to know about.

### Modified Capabilities

- `nav-config`: `navFor` returns a `section | link` tree; `tenant_admin`/`annotator` are
  grouped; the three method landing routes and the automated step routes are added to the
  screen-title map; breadcrumbs are derived from the tree.
- `task-assignment-ui`: the annotation-task backend endpoints gain role gates, and an
  annotator completing a task marks it training-eligible and notifies the Tenant Admin.

## Impact

- **Backend**: `src/annotation_service/api/v1/_rbac.py` (new), `.../tasks.py` (gates +
  completion hook), `src/annotation_service/services/notify.py` (new),
  `src/gateway/api/v1/notifications.py` (new) + `gateway/main.py`.
- **Database**: migration `041` — `public.notifications`,
  `annotation_tasks.training_eligible_at`, and (forward-looking, for the automated change)
  `prelabel_batches.annotator_review_status` / `training_eligible_at` and an
  `annotation_imports` header table.
- **Frontend**: `src/portal/src/lib/nav-config.ts` (tree + helpers), `app-shell/Sidebar.tsx`
  (section headers), `app-shell/Topbar.tsx` (breadcrumb + bell),
  `app-shell/NotificationBell.tsx` (new), `hooks/use-notifications.ts` (new),
  `app/(auth)/annotate/**` (landing + step routes), `app/(auth)/{schema-proposals,
  prelabel-batches,retraining}/page.tsx` (redirect shims), `next.config.js` (redirects).
- **No impact**: model serving, extraction, chat/analytics; System Admin and business_user
  navigation; System Admin training approval and model promotion.

## Open Questions

(resolved during implementation)

- Route prefix `/annotate/*` chosen over `/annotation/*` to avoid colliding with the
  existing `/annotation` workspace route.
- "Models & Training" kept top-level rather than under `Setup`.
- Annotators get `Import` (review-only, no upload).
- `notifications` placed in `public` with a `tenant_id` filter, matching `audit_events`.
