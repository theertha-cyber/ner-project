## Context

`/annotate/manual` (`ManualAnnotationLanding`) currently shows two work cards — "Annotation
workspace" and "Review queue" — plus stats that include a "predictions awaiting review" count
sourced from `useReviewQueue`. The tenant admin does not use the review queue and asked for
it removed. Reviewed and approved via an HTML mockup before this implementation (two
iterations: an initial generic rework, then a second pass built from the real running app's
computed styles and the tenant admin's own screenshot of the current page).

The review queue is backed by a real, separate capability (`confidence-routed-review`,
archived `2026-09-08`) that retains below-threshold extraction predictions, routes them to
human/LLM review, and turns outcomes into confirmed spans for training. That capability owns
a database table, extraction-time retention logic in `src/extraction_service`, and audit
sampling. None of that was part of the mockup the tenant admin reviewed, and removing it is a
materially larger, riskier change than a landing-page rework.

## Goals / Non-Goals

**Goals**
- Remove every frontend entry point to `/review-queue` (nav child, work card, stat).
- Give `/annotate/manual` a reason to exist beyond one link: show what's already annotated,
  and connect that directly to starting a training run.
- Reuse existing data sources and routes rather than inventing new ones.

**Non-Goals**
- Removing or deprecating the `confidence-routed-review` backend capability, its database
  table, or its extraction-time retention behaviour. Out of scope — see proposal.md § Open
  Questions.
- Changing what "Models & Training" (`/training-jobs`) does once the user gets there.
- Changing the annotation workspace's own behaviour when opened via `?task={id}` — it already
  renders a completed task read-only; this change only links to it.

## Decisions

**Reuse `/api/v1/annotation-tasks` instead of a new endpoint.** `AnnotationPage` already
fetches this for the task queue and it already carries `filename`, `status`, and
`span_count`. The landing page filters client-side for `status === "completed"`. Rejected
alternative: a dedicated `/api/v1/annotated-documents` endpoint — more accurate long-term (no
client-side filtering, could be paginated), but not justified for a list that, in the current
seed data, tops out around 100 rows, and it would duplicate data the workspace already fetches
in the same session.

**Reuse `/annotation?task={id}` as the "View" destination instead of a new read-only
viewer.** `AnnotationPage` already reads a `task` query param (line ~222) and auto-selects
that task, rendering its `COMPLETED` status and confirmed spans. Building a second viewer
would duplicate span-rendering logic (`DocumentViewer`, entity color mapping) that already
exists and is already exercised by tests.

**`AnnotatedDocuments` and `TrainModelBanner` are new presentational components, not
additions to `AnnotateLanding`.** `AnnotateLanding` already accepts a `children` slot used by
no page yet; passing the new sections through it keeps the shared component's contract
(heading/intro/primaryAction/stats/workCards) unchanged for `AutomatedAnnotationLanding` and
`ImportAnnotationLanding`, which also use it.

**No new ADR.** This is a product decision about one landing page's content, not a durable
architectural commitment — it doesn't introduce a pattern, a new dependency, or a data-model
change. `docs/adr/` already has entries so the ADR pipeline step is satisfied without one.

**Delete rather than deprecate the review-queue frontend code.** `ReviewQueuePage`,
`useReviewQueue`, `useResolveQueuedPrediction`, `useReviewAccumulation`, and
`types/confidence-review.ts` become fully unused once the route and work card are gone (only
`ReviewQueuePage` imported them). Leaving dead code with a passing test suite around it would
misrepresent it as live. The backend endpoints they called are untouched and can grow a new
frontend later without any backend change.

## Risks / Trade-offs

- **[Risk]** An `annotator`'s "submitted, awaiting review" mental model disappears with no
  replacement metric. → **Mitigation**: replaced with "completed by me", which answers the
  question the annotator actually has ("is my work done") without depending on the removed
  queue.
- **[Risk]** Deleting `useReviewAccumulation` removes the only frontend caller of
  `/api/v1/review-accumulation`, so a backend regression there would go unnoticed by the
  portal test suite. → **Mitigation**: that endpoint belongs to `confidence-routed-review`,
  which has its own backend test coverage independent of the portal; this was true before this
  change too (the portal never asserted on the backend's correctness, only rendered it).
- **[Trade-off]** The Annotated Documents list re-fetches and client-filters the full task
  list rather than a purpose-built, paginated endpoint. Acceptable at current data volumes
  (see Decisions); revisit if a tenant's completed-task count grows large enough to make the
  unpaginated fetch slow.

## Migration Plan

Frontend-only, additive-and-subtractive in the same deploy — no data migration, no feature
flag. Deploy order doesn't matter relative to backend services since nothing backend changes.
Rollback is a plain revert of the portal image; no data was created or destroyed that would
need reconciling.

## Open Questions

None outstanding for this change. The backend `confidence-routed-review` capability's future
is explicitly deferred to the project owner (proposal.md § Open Questions), not a design
question this change needs to resolve.
