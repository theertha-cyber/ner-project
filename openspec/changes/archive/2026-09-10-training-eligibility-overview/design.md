## Context

`GET /api/v1/retraining-decision` (`src/annotation_service/api/v1/retraining_decision.py`)
reports the accumulation figure since the serving model version, per entity type, plus
`training_run_in_flight`. `accumulation_report` in
`src/annotation_service/services/accumulation.py` computes it from the confirmed-span set
minus the spans a completed run recorded as consumed (per the `human-gated-retraining`
"Training Runs Record Consumed Spans" requirement).

After the manual / automated / import changes, three tables carry a `training_eligible_at`:
`annotation_tasks`, `prelabel_batches` (for `batch_kind = 'large'` with
`annotator_review_status = 'approved'`), and `annotation_imports`. Nothing aggregates them.

## Goals / Non-Goals

**Goals**
- One read that answers "is there training-eligible work waiting, and where from?"
- Attribute the accumulation figure to `manual` / `automated` / `import`.
- Let the portal render an identical "Training: Eligible — [Request training]" state on the
  three landing pages and the retrain step from this one read.

**Non-Goals**
- No change to `POST /api/v1/training-retrain-requests`, training approval, or promotion.
- No new "consumed" bookkeeping for import files beyond a timestamp comparison (see
  Decision 2).
- No per-unit "request training for just this task" — the retrain request trains on the
  whole eligible dataset, unchanged.

## Currently-In-Force ADRs

| ADR | Constraint |
|-----|-----------|
| ADR-001 tenant-data-isolation | All reads are within one tenant schema, resolved as the existing endpoint does. |
| ADR-009 system-admin-sets-hyperparameters | The overview is a report; it never enqueues or approves. |
| ADR-010 per-entity-type-dataset-threshold | The overview MUST NOT compare its counts against the readiness threshold — it is "what is waiting", not "is there enough". |

## Decisions

### Decision 1: Per-source attribution comes from span provenance, not a new column

Confirmed spans already carry provenance: manual spans from the workspace, batch-acceptance
provenance for automated (`span_batch_provenance` / the batch-acceptance route marker), and
— after `import-annotation-training-eligibility` — imported rows are emitted by the export
with a `source: "import"` marker. `accumulation_report` is extended to group the
unconsumed accumulated set by these markers. No schema change.

### Decision 2: "Unconsumed" for an import file = no completed run after its `training_eligible_at`

Manual/automated spans have a consumed-spans record keyed by model version. An import file
has no span rows of its own. The overview treats an import file as unconsumed until a
training job **completes** with a `completed_at` later than the file's
`training_eligible_at`. Coarse, but it matches how accumulation already reasons about time,
and it never *under*-reports waiting work (the failure mode is showing a file as waiting one
run longer than strictly necessary, which is safe).

### Decision 3: The overview is additive to the response, old fields unchanged

The response keeps `spans_accumulated`, `by_entity_type`, `serving_model_version`,
`has_trained_model`, `training_run_in_flight` exactly as today. It adds
`by_source: {manual, automated, import}` and
`eligible_overview: {manual: {count, latest_at}, automated: {...}, import: {...}}`.
Existing callers are unaffected.

## Risks / Trade-offs

- **Provenance completeness.** If some historical confirmed spans have no provenance
  marker, they fall into a `manual`/`unknown` bucket. Acceptable — the per-entity-type
  total is still correct; the source split is best-effort for pre-existing data and exact
  going forward.
- **Import "unconsumed" coarseness (Decision 2).** Documented; safe failure direction.
- **Double-count risk.** A document that was both manually annotated and imported could
  contribute spans under `manual` and a row under `import`. The per-entity-type total is
  computed from spans only (imports are not spans), so the headline figure is not
  double-counted; the `eligible_overview` counts units, not spans, so it is not either.

## Migration Plan

None. All source fields exist. `scripts/setup_test_db.py` / fixtures already gain the
columns via the prior changes; this change only adds test coverage.

## Open Questions

- Should `eligible_overview` also carry a per-source list of unit ids (for the portal to
  deep-link)? Assume counts + latest timestamp only for v1; add ids if the UI needs them.
