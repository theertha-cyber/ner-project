## Why

Change 5 accumulates reviewed spans and reports how many have built up since the current model version was trained. Nothing consumes that figure. A tenant can see evidence accumulating but has no surface that connects it to the decision it informs, and — more seriously — nothing ever resets it. Change 5 defines accumulation as a delta since the current version was trained, but change 5 does not touch training, so no code records which spans a training run actually consumed. Left as-is, the figure is correct exactly once and drifts thereafter.

This change closes that loop and gives the decision a home. It is change 6 of a 6-change plan and depends on change 5.

The decision itself stays with a person. An earlier version of this plan had retraining fire automatically once accumulation crossed a threshold; that was deliberately replaced with a manual decision. This change therefore adds a **surface**, not a trigger.

## What Changes

- Record which confirmed spans a training run consumed, at the point the run completes, so accumulation resets against the newly trained version. This is the piece neither change 5 nor the existing training pipeline currently owns.
- Add a retraining decision surface showing the accumulation figure against the currently serving model version, with enough context to judge whether a retrain is worth requesting.
- Allow a retrain to be requested from that surface. The request creates an ordinary training job that enters the existing `pending_approval` state and goes through the existing System Admin approve/reject flow unchanged.
- Add a promotion decision surface showing the candidate version's metrics alongside the currently promoted version's, so the existing manual promote step is made on evidence rather than on the fact that a run finished.
- State explicitly, as a testable requirement, that no accumulation figure, threshold crossing, schedule, or completed training run may automatically initiate a training job or promote a model version.

## Capabilities

### New Capabilities

- `human-gated-retraining`: recording consumed spans at training completion, the retraining decision surface, manual retrain requests into the existing approval flow, the promotion decision surface, and the explicit prohibition on automatic initiation or promotion.

### Modified Capabilities

None. Training job creation reuses `training-jobs`, approval reuses `training-approval`, and promotion reuses `model-registry` — all unchanged. This change adds surfaces and one bookkeeping step around them.

## Impact

- **Backend**: a completion hook in the training path that records the span set consumed by the run; read endpoints backing the two decision surfaces; a retrain request endpoint that creates a training job through the existing submission path.
- **Database**: additive. The consumed-span record introduced by change 5 gains a writer; no existing table is altered.
- **Frontend**: two read-mostly surfaces — retraining decision and promotion decision — plus a request-retrain action.
- **Depends on**: change 5 (accumulation reporting and the consumed-span record it defines), and transitively changes 1, 3 and 4.
- **No impact**: the training worker's behaviour, the approval flow, the promote/demote flow, model serving, extraction, or anything in changes 1-5 beyond consuming change 5's accumulation figure.

## Open Questions

- **What context, beyond the raw count, makes the retrain decision judgeable?** A bare "134 spans since v3" does not say whether those 134 are concentrated in one entity type or spread across all of them, and that distinction changes the answer. A per-entity-type breakdown is likely necessary, but should be confirmed against how the decision is actually made.
- **Are metrics from two training runs comparable enough to display side by side?** Change 3 records that pre-fix and post-fix metrics are not comparable. The same caution applies to any two runs over materially different datasets. The surface must not imply a comparison is valid when it is not — how to convey that is unresolved.
- **Should a retrain request be available when accumulation is zero?** Blocking it prevents a pointless run; allowing it preserves the ability to retrain after a hyperparameter change rather than a data change. Leaning toward allowing it with a warning, but unconfirmed.
- **Who may request a retrain — Tenant Admin, System Admin, or both?** The approval step is already System Admin only, so the request itself could reasonably be broader. Needs a decision consistent with the existing role model.
