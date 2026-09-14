# ADR-013. Large automated batches are promoted without any human review

- **Status:** accepted
- **Date:** 2026-09-12

## Context

`seed-bootstrap`'s original design (change 5 of the seed-bootstrap plan) gated both batch kinds
behind a sampled human acceptance review: an `initial` batch (≤5 docs) self-reviewed by the
Tenant Admin, and a `large` batch (the main, 100-200 document run) reviewed by an Annotator
Admin before any of its suggestions became confirmed spans. That review was the only check
between an LLM's output and the tenant's training data.

The project owner asked for this inverted and simplified: the small batch gets an independent
reviewer (an Annotator Admin, not the uploader), and the large batch — the one that actually
becomes the training set — needs no review from anyone. This is a deliberate trade of
review-as-a-safety-gate for throughput, made explicitly and knowingly by the project owner, not
inferred from ambiguous requirements.

## Decision

A `large` batch's suggested spans are promoted to confirmed spans automatically, with no
sampling, no agreement threshold, and no acceptance step of any role, the moment its
pre-labeling job reaches a terminal state with at least one succeeded document. Every
acceptance-gate endpoint refuses a call made against a `large` batch (422). The only review
remaining anywhere in the automated flow is the `initial` batch's — capped at 5 documents,
performed by an Annotator Admin — whose approval is now also the gate that unlocks the large
batch (`annotation-workflow-review-simplification`).

## Consequences

- The `large` batch's training data quality now depends entirely on the model and on whatever
  the `initial` batch's Annotator Admin review caught (and recorded as guidance) beforehand —
  there is no second check. A future change that wants to reintroduce large-batch review, add
  a post-hoc audit sample, or gate promotion on a confidence threshold must explicitly supersede
  this ADR rather than add such a check quietly next to a code path this ADR intends to be
  unreviewed.
- `span_batch_provenance` continues to be the single provenance mechanism for a batch-promoted
  span, human-reviewed or not; a synthetic `batch_acceptance_records` row with `reviewer IS
  NULL` is what distinguishes the auto-promoted case on inspection, not a schema change.
- The Annotator Admin's per-batch review workload drops for the large batch entirely and
  concentrates on the small initial one instead — a smaller, but now independently reviewed,
  surface.
