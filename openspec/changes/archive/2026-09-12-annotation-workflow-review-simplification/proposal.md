## Why

The tenant admin found the automated batch pre-labeling flow had too much review overhead in
the wrong place: the small validation batch was self-reviewed by the Tenant Admin (no
independent check at all), while the main run — 100-200 documents, the batch that actually
becomes training data — required an Annotator Admin to sample-review it before anything was
promoted. The requested shape inverts and simplifies this: the small batch gets a real,
independent review (by an Annotator Admin), and the main run needs no review at all — the
moment the LLM finishes pre-labeling it, that output *is* the training data. This also removes
the "choose a batch kind" decision from the tenant admin entirely; the two batches now happen
in a fixed order instead of being an either/or choice.

## What Changes

- **BREAKING (spec-level)**: the `initial` batch's acceptance review moves from the
  `tenant_admin` role to the `annotator` role. A `tenant_admin` can no longer review or accept
  an `initial` batch (403).
- **BREAKING (spec-level)**: the `large` batch's acceptance review is removed entirely. Every
  suggestion the LLM produces for a `large` batch is promoted to a confirmed span automatically
  the moment pre-labeling finishes — no sampling, no agreement threshold, no human of any role
  reviews it. Calling any acceptance-gate endpoint (`POST .../acceptance`,
  `GET .../acceptance`, `POST .../acceptance/review`, `POST .../acceptance/accept`) for a
  `large` batch now returns 422.
- A `large` batch can no longer be created until the tenant has an `initial` batch an Annotator
  Admin has approved. This replaces the portal's former either/or radio choice between batch
  kinds with a fixed sequence: initial batch → Annotator Admin review → large batch → automatic
  promotion → train.
- An Annotator Admin approving an `initial` batch is recorded (`annotator_review_status =
  'approved'`) so the portal can gate the large-batch step on it, but — unchanged from before —
  it still does **not** mark the batch training-eligible and still does **not** notify anyone;
  an initial batch's only purpose is producing review guidance for the subsequent large batch.
- `POST /api/v1/prelabel-batches/{id}/guidance` (initial-batch review corrections) moves from
  `tenant_admin` to `annotator`, matching the new reviewer of the batch it is guidance for. This
  endpoint has no existing portal caller (dead code, per design.md), so this is a permission
  correction with no observable behaviour change yet.
- The portal's `/annotate/automated/prelabel` page (`BatchAcceptancePage`) drops its batch-kind
  radio and instead renders the fixed sequence: an initial-batch document picker (≤5 docs) when
  none is approved yet, that batch's status while it's with an Annotator Admin, a large-batch
  document picker (no cap) once approved, that batch's status while auto-promoting, and a
  "Train model" action once it finishes, linking to the existing Retraining step
  (`/annotate/automated/retrain`).
- The Annotator Admin's `/annotate/review-batch` landing page and per-batch review route now
  list and open `initial` batches (previously `large`).

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `seed-bootstrap`: the **Sampled Acceptance Gate**, **Batch Kind**, and **Initial-Batch Review
  Guidance** requirements change as described above. One requirement is added: **Automatic
  Large-Batch Promotion**.

## Impact

- **Backend**: `src/annotation_service/api/v1/seed_bootstrap.py` — `_gate_acceptance_reviewer`
  now refuses `large` outright and requires `annotator` for `initial`; `create_prelabel_batch`
  gains the initial-approved-first check; `accept_batch` no longer has a `large`-kind branch
  (unreachable once the gate refuses it) and now marks `annotator_review_status` for the
  `initial` case it always runs for now; `record_initial_batch_guidance` requires `annotator`.
  `src/annotation_service/worker.py` — `run_prelabel_batch_sync` now looks up the batch's kind
  and, for a finished `large` batch with at least one succeeded document, calls new
  `_auto_promote_large_batch`, which promotes every suggestion, writes a synthetic
  `batch_acceptance_records` row (`reviewer = NULL`, `sampled = false`) so
  `span_batch_provenance.acceptance_id`'s `NOT NULL` constraint is satisfied without a schema
  change, marks the batch training-eligible, and writes the `automated_batch_approved`
  notification directly (the worker has no `AsyncSession` to call the existing async `notify()`
  helper with).
- **Database**: none. No migration. The synthetic acceptance record reuses
  `batch_acceptance_records` exactly as designed for a human-reviewed one, distinguished by
  `reviewer IS NULL` and `sampled = false`.
- **Frontend**: `src/portal/src/components/seed-bootstrap/BatchAcceptancePage.tsx` restructured
  as described; `src/portal/src/app/(auth)/annotate/review-batch/page.tsx` and `[id]/page.tsx`
  filter/label for `initial` instead of `large`; `useBatchAcceptance` gained an `enabled` flag so
  it is not polled for a `large` batch, which would only ever 422.
- **No impact**: the annotation workspace, manual annotation, entity types, document
  upload/import, the retraining decision page's own request/approval flow, and System Admin
  training approval are all unchanged. The automated stepper's own gating (`layout.tsx`) needed
  no changes — it already read `annotator_review_status` / `training_eligible_at` /
  `acceptance_decision` generically, and those fields carry the same meaning under the new
  design, just set by different actors (or automatically).

## Open Questions

None. The reviewed-and-approved shape (initial batch reviewed by an Annotator Admin, large
batch auto-promoted, sequential rather than either/or) was specified directly and completely by
the project owner.
