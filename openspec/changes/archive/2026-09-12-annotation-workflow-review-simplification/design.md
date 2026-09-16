## Context

The automated pre-labeling flow (`seed-bootstrap`) previously let a Tenant Admin choose,
per batch, between an `initial` kind (≤5 docs, self-reviewed by the Tenant Admin on the same
page) and a `large` kind (no cap, reviewed by an Annotator Admin via a sampled acceptance
gate before its spans became training data). The project owner reviewed this and asked for a
different shape: the small batch gets an independent reviewer (an Annotator Admin, not the
person who uploaded it), and the large batch — which is what actually becomes the training
set — needs no review from anyone. The two batches also stop being a choice and become a fixed
sequence: initial, then large.

## Goals / Non-Goals

**Goals**
- Move the `initial` batch's reviewer from `tenant_admin` to `annotator`.
- Remove all human review of the `large` batch; its suggestions become confirmed spans the
  moment pre-labeling finishes.
- Enforce the sequence (approved initial batch required before a large batch can start) at the
  API layer, not only in the portal's UI.
- Give the portal a "Train model" action once the large batch finishes, reusing the existing
  Retraining step rather than inventing a new destination.

**Non-Goals**
- Changing anything about the Retraining step itself, or about System Admin training approval.
- Adding a document-count cap to the `large` batch (none existed before; none is added now —
  the worker's own docstring already documented "100-200 documents" as the expected shape).
- A full recovery UX for a rejected `initial` batch beyond "start a new one" — kept minimal
  (see Risks below).

## Decisions

**A `large` batch's spans still need `span_batch_provenance`, so auto-promotion writes a
synthetic acceptance record rather than changing the schema.** `span_batch_provenance
.acceptance_id` is `NOT NULL REFERENCES batch_acceptance_records` (migration 039). Rather than
add a migration to make it nullable or add a second provenance path, `_auto_promote_large_batch`
writes an ordinary `batch_acceptance_records` row with `reviewer = NULL`, `sampled = false`,
`sample_size = 0`, `decision = 'accepted'`. This is queryable and auditable exactly like a
human-reviewed batch's record, and `reviewer IS NULL` is precisely the fact that distinguishes
it. Rejected alternative: a new `span_provenance_kind` column or a second table for
auto-promoted spans — more explicit, but a schema change and a second code path for something
`span_batch_provenance` already models correctly (a span promoted as part of a batch, with a
record explaining why).

**The sequencing gate lives in `create_prelabel_batch`, not only in the portal.** The portal
already won't show the large-batch picker before the initial batch is approved, but the
endpoint enforces it independently (422 `INITIAL_BATCH_NOT_APPROVED`) — the same reasoning as
the existing 5-document cap on `initial`: a business rule stated only in the UI is not a rule.

**The worker writes its own notification row via raw SQL instead of calling the existing async
`notify()` helper.** `notify()` takes an `AsyncSession`; `run_prelabel_batch_sync` runs on a
sync SQLAlchemy `Connection` (it's a Celery task body, not a FastAPI request handler). Rather
than thread an async session into the worker or duplicate `notify()`'s logic as a new shared
function, `_auto_promote_large_batch` does the one INSERT directly, matching the file's
existing style (every other worker mutation is a raw `text()` statement against `connection`).

**`accept_batch` keeps a single code path instead of a `batch_kind` branch.**
`_gate_acceptance_reviewer` now refuses `large` before `accept_batch`'s body ever runs, so the
function is only ever reached for `initial` batches. The former `if batch_kind ==
BATCH_KIND_LARGE` branch (training-eligible + notify) is deleted rather than left dead, and
replaced with the unconditional "mark `annotator_review_status = 'approved'`, nothing else"
behavior `initial` always needed.

**The portal tracks one active `batchId`, auto-selected from the tenant's batch list.**
`BatchAcceptancePage` already had a single `batchId` state slot for "the batch just created in
this session." It now also auto-selects the right batch on load (the large batch if one
exists, else the initial one, unless the initial was rejected) via `usePrelabelBatches`, so
returning to the page after a refresh — or as the Annotator Admin's own review target — shows
the correct state without requiring the admin to have just created it. Rejected alternative:
a page-level reducer with an explicit phase enum — more explicit, but this is three
derived booleans (`canCreateInitial`, `canCreateLarge`, `largeDone`) over data already being
fetched, not new state worth its own machinery.

**Rejected-initial-batch recovery is a single "start over" button, not a redo of the batch.**
When an `initial` batch's acceptance is rejected (below agreement threshold), its suggestions
stay available for individual review (unchanged, pre-existing behavior) and the admin can start
a *new* initial batch from scratch. There is no attempt to let them re-review the same rejected
batch's sample or contest the rejection — that was already the case before this change
(`accept_batch`'s docstring: "a rejected one never becomes acceptable").

## Risks / Trade-offs

- **[Risk]** Removing all review from the `large` batch means bad LLM output reaches training
  data unfiltered — the sampled acceptance gate existed specifically to catch this.
  → **Mitigation**: this is the explicit, deliberate product decision requested; the `initial`
  batch's Annotator Admin review (now independent of the uploader) is what the project owner
  is relying on to catch systematic problems before the large batch runs, via the guidance
  mechanism. Not something this change can mitigate further without contradicting the request.
- **[Risk]** `record_initial_batch_guidance`'s permission moved to `annotator` with no existing
  UI caller — a latent inconsistency (spec now says annotator, but nothing exercises it) could
  go unnoticed. → **Mitigation**: stated explicitly in the proposal's Impact section and in a
  Hallucination Risk Register entry (verification.md) so a reviewer knows to check rather than
  assume it was wired up.
- **[Trade-off]** The synthetic acceptance record for an auto-promoted batch has
  `sampled_document_ids = []` and `sample_size = 0`, which reads oddly next to a genuinely
  reviewed record. Accepted: the alternative (a schema change) is disproportionate to what is,
  in effect, a "there was no review" flag.

**Recorded as ADR-013** (`docs/adr/013-large-batch-auto-promotion-no-review.md`): removing all
human review from the `large` batch is a durable policy commitment, not a tactical detail — a
future change that wants to reintroduce any form of large-batch review must explicitly
supersede it rather than add a check quietly beside code this decision intends to be
unreviewed. No prior ADR covered the original sampled-acceptance-gate design, so there is
nothing for ADR-013 to supersede; it is a new, freestanding record.

## Migration Plan

Backend and frontend deploy together; no data migration. Rollback is a plain revert — no data
was created that would need reconciling, since a `large` batch that already auto-promoted under
the new code has ordinary confirmed spans and an ordinary (if `reviewer = NULL`) acceptance
record, both of which the old code already knew how to read.

## Open Questions

None outstanding.
