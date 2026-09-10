## Why

After the manual (Phase 3), automated (`automated-annotation-guided-workflow`), and import
(`import-annotation-training-eligibility`) changes, three kinds of unit can be
"training-eligible":

- an `annotation_tasks` row an annotator marked completed (`training_eligible_at`),
- a `prelabel_batches` row with `batch_kind = 'large'` an annotator approved
  (`annotator_review_status = 'approved'`, `training_eligible_at`),
- an `annotation_imports` file with all types mapped (`training_eligible_at`).

Each already has its own "Request training" affordance wired to
`POST /api/v1/training-retrain-requests`, and completed/accepted work already lands in the
training dataset (confirmed spans for manual/automated; eligible rows for import). What is
missing is a **single place to see what is eligible and waiting** — the Tenant Admin
currently has to visit three screens to know whether there is anything worth training on,
and the retraining decision surface reports one accumulation number with no sense of where
it came from.

## What Changes

- Add a **training-eligibility overview** to the retraining decision surface: counts of
  training-eligible manual tasks, approved automated large batches, and mapped import
  files that have **not yet been consumed by a completed training run**, plus the most
  recent eligibility timestamp per source.
- Break the existing per-entity-type accumulation figure down by **source**
  (`manual` / `automated` / `import`) so the surface shows not just "318 new spans" but
  where they came from.
- The portal's three Automated/Manual/Import landing pages and the
  `/annotate/automated/retrain` step read this one overview so the "Training: Eligible —
  [Request Training]" state is identical everywhere and there is exactly one `Request
  training` call.
- No change to `POST /api/v1/training-retrain-requests`, to training approval, or to model
  promotion.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `human-gated-retraining`: the Retraining Decision Surface additionally reports a
  training-eligibility overview (eligible-and-unconsumed counts per source with the latest
  timestamp) and a per-source breakdown of the accumulation figure. The decision surface
  stays a report — it still enqueues, schedules, and promotes nothing.

## Impact

- **Backend**: `src/annotation_service/api/v1/retraining_decision.py` and
  `src/annotation_service/services/accumulation.py` — add the eligibility counts and the
  per-source accumulation split. Reads `annotation_tasks.training_eligible_at`,
  `prelabel_batches` (kind + review status + eligible ts), `annotation_imports`, and the
  existing consumed-spans / span-provenance tables.
- **Frontend**: `src/portal/src/components/retraining/RetrainingDecisionPage.tsx`,
  `src/portal/src/hooks/use-retraining.ts` (overview fields), and the three
  `/annotate/*` landing pages / `automated/layout.tsx` stepper state derivation.
- **Database**: none. All source fields already exist after the prior changes.
- **No impact**: the retrain request path, training approval, model promotion, model
  serving.

## Open Questions

- **"Unconsumed" for import files.** Manual/automated spans have a consumed-spans record;
  an import file does not. Assume an import file counts as unconsumed until a training run
  completes *after* its `training_eligible_at`, using the run's completion timestamp — a
  coarse but honest signal, matching how accumulation already treats time.
- **Do we surface eligible units that are already consumed?** Assume no — the overview is
  "what is waiting", so consumed units drop off it (they show in run history instead).
- **Ordering of the per-source accumulation split vs the existing per-entity-type split.**
  Assume both are reported (entity-type breakdown unchanged; source breakdown added
  alongside), not nested.
