## Why

The tenant admin reviewed the Manual annotation landing page and asked for the Review Queue
entry point to be removed ("no review is needed") — it's a confidence-based review surface
the tenant does not use. Once it's gone, the landing page also needs its own reason to exist
beyond a single "open the workspace" link: a place to see what's already been annotated, and
a clear next step once there's enough annotated material to train on. Without that, removing
the second work card leaves the page thinner than before rather than more useful.

## What Changes

- Remove the "Review queue" work card, its `awaitingReview` stat, and the annotator's
  "Open my queue" primary action from `/annotate/manual`.
- **BREAKING (spec-level)**: `nav-config`'s Role Navigation Matrix requirement changes —
  `Manual` no longer carries a `Review Queue /review-queue` child. The `/review-queue` route,
  its page component, and the now-unused `useReviewQueue` / `useResolveQueuedPrediction` /
  `useReviewAccumulation` hooks are deleted from the portal.
- Add an "Annotated documents" list to `/annotate/manual` showing every completed annotation
  task (filename, span count), scoped to the caller's own tasks for `annotator` and to every
  task for `tenant_admin`, each linking to the existing read-only view at
  `/annotation?task={id}`.
- Add a "Train model" call-to-action that appears once at least one document is annotated and
  links to `/training-jobs` (Models & Training). Tenant-admin only — training is not an
  annotator capability in the current role matrix.

## Capabilities

### New Capabilities

- `manual-annotation-landing`: the `/annotate/manual` page's stats, work cards, annotated
  documents list, and the training hand-off action. This page previously existed but had no
  capability spec of its own.

### Modified Capabilities

- `nav-config`: the Role Navigation Matrix requirement's `Manual` children list drops
  `Review Queue /review-queue`.

## Impact

- **Frontend only.** `src/portal/src/app/(auth)/annotate/manual/page.tsx`,
  `src/portal/src/lib/nav-config.ts`, two new presentational components
  (`AnnotatedDocuments`, `TrainModelBanner`) under `src/portal/src/components/annotate/`.
  Deleted: `app/(auth)/review-queue/`, `components/review-queue/`, `hooks/use-review-queue.ts`,
  `types/confidence-review.ts`.
- **Backend: none.** The `confidence-routed-review` capability (extraction-time confidence
  routing, the `/api/v1/review-queue` endpoints, the accumulation accounting) is a separate,
  already-archived capability (`2026-09-08-confidence-routed-review`) with its own consumers
  and migrations. Removing its only UI surface does not retire the capability; this change
  does not touch `src/annotation_service` or `src/extraction_service`, and does not migrate
  or drop any table. Reviving a queue UI later would need no backend work.
- **`nav-config`'s "no pre-existing route SHALL be removed" clause is out of scope here**:
  that constraint is scoped, in its own requirement text, to the method landing routes and
  automated step routes (`/annotate/{manual,automated,import}` and the four step routes).
  `/review-queue` is a work-card destination, not one of those routes.
- **Depends on**: nothing new — reuses the existing `/api/v1/annotation-tasks` endpoint
  already used by the annotation workspace, and the existing `/annotation?task={id}` deep
  link already read by `AnnotationPage`.
- **No impact**: the annotation workspace itself, entity types, document upload/import,
  automated annotation, and the `annotator`'s Batch Review screen are all unchanged.

## Open Questions

- Whether the Review Queue's backend capability (`confidence-routed-review`) should be
  deprecated or removed entirely is a separate, materially larger decision (it owns a DB
  table, extraction-time retention logic, and audit sampling) that was not part of what was
  reviewed and approved for this change. Flagged for the project owner to decide separately.
