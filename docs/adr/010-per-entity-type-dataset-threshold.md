# ADR-010: Dataset Readiness Measured Per Entity Type

**Status**: Accepted
**Supersedes**: ADR-006 (partially — replaces the two dataset-threshold clauses in its Compliance section; every other clause of ADR-006 remains in force)
**Date**: 2026-08-06

## Context

ADR-006's Compliance section states the dataset threshold twice, and the two statements disagree:

- "Training Orchestrator MUST enforce 500-entity minimum dataset threshold before accepting a job."
- "Minimum dataset threshold: 500 labeled entities per entity type before training permitted."

One is a tenant-wide total, the other is per entity type. The implementation followed the first reading: the annotator dashboard divided a tenant-wide `COUNT(*)` of `spans` by 500, and the training-service gate counted total spans across all types.

A tenant-wide total is a poor proxy for whether a dataset can train a usable model. NER quality is bounded by the weakest label: 500 spans made almost entirely of one entity type produces one usable recogniser and leaves every other configured type untrainable, while the dashboard reports the dataset as fully ready. This was observable in the live data — one tenant showed 5% readiness against a 500 total while holding 18, 4, and 2 spans across its three annotated types, with five further configured types at zero and invisible entirely, because the breakdown enumerated only entity types that already had spans.

Separately, the total-count gate was never actually enforced: `NER_MIN_TRAINING_ENTITIES` defaults to `0` and is unset in the deployed configuration, so the dashboard asserted a rule nothing applied.

## Decision

Dataset readiness is measured **per entity type**, at **200 labeled entities per type**.

- The set of entity types evaluated is the union of the tenant's active `entity_definitions` and the distinct `entity_type` values already present in `spans`. Enumerating definitions is what makes a configured-but-never-annotated type visible; including spanned types is what stops a tenant that never configured its label list from losing readiness reporting entirely.
- Per-type progress is capped at 100% before aggregation, so an over-annotated type cannot compensate for a starved one.
- Overall readiness is the mean of per-type progress, reported alongside a count of how many types have met the threshold.
- Enforcement is available through `NER_MIN_ENTITIES_PER_TYPE`, which defaults to `0` (inert) and, when set, rejects submission naming the entity types that fall short. `NER_MIN_TRAINING_ENTITIES` retains its existing total-count meaning and default.

200 was chosen as a practical per-type target: it is a materially lower bar per label than the previous nominal 500 total while demanding coverage across every type, which is the property that actually predicts model quality.

## Consequences

**Positive**
- The displayed readiness figure predicts what it claims to predict.
- The panel becomes directive: an annotator can see which specific label needs work, including labels with no annotations at all.
- Dashboard and gate can share one definition of "training-ready" rather than the dashboard asserting an unenforced rule.

**Negative**
- Reported readiness drops for tenants whose configured label list exceeds what they have annotated — one tenant moves from roughly 5% to roughly 1.5% purely from being measured against 8 types instead of 3. This is a correction, not a regression, but it will read as a setback.
- A tenant that configures entity types its documents never contain cannot reach 100%. Deactivating the unused type (`is_active = false`) is the supported escape hatch.
- 200 is not empirically derived from measured F1-versus-example-count on this corpus. It should be revisited once a model has trained against a per-type-balanced dataset.

**Neutral**
- Turning on `NER_MIN_ENTITIES_PER_TYPE` remains an operational decision; nothing changes in deployment behaviour on merge.

## References

- ADR-006 (Training Infrastructure) — the superseded threshold clauses
- ADR-001 (Tenant Data Isolation) — the `entity_definitions` read is filtered by `tenant_id`, the isolation boundary for this cross-schema query
- `openspec/changes/annotator-dashboard-cards-and-per-entity-readiness/` — proposal, design, and specs for this change
