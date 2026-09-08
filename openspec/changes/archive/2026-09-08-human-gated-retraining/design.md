## Context

The pieces this change needs all exist. Training jobs are created, enter `pending_approval`, and are approved or rejected by a System Admin who sets hyperparameters at that point (`training-approval`, ADR-009). A completed model version sits in "completed" status until a Tenant Admin explicitly promotes it, which archives the previously promoted version and triggers serving warmup (`model-registry`, Promote model version). Promotion is therefore **already** a human action — this change must preserve that, not build it.

Change 5 added accumulation reporting: how many confirmed spans have been created by production review since the currently serving model version was trained, excluding base-model-served predictions.

Two gaps remain.

**The accumulation figure never resets.** Change 5 defines accumulation as a delta since the current version was trained and specifies a record of which spans have been included in which training run — but change 5 deliberately does not touch the training path, so nothing writes that record. The figure is correct until the first retrain and wrong afterwards. Closing this is the substantive work in this change; everything else is surfacing.

**The decision has no home.** Accumulation is reported but not connected to the action it informs, and the existing promote step offers no evidence for choosing to promote beyond the fact that a run completed.

## Goals / Non-Goals

**Goals:**
- Make accumulation reset correctly by recording what each training run consumed.
- Give the retrain decision a surface with enough context to be judged.
- Route a retrain request through the existing submission and approval path without modifying it.
- Give the existing manual promote step some evidence.

**Non-Goals:**
- **No automatic retraining of any kind** — no threshold trigger, no schedule, no cron, no completion-chained follow-on run.
- **No automatic promotion** — the existing manual promote flow stands exactly as it is.
- No new approval mechanism. `training-approval` is reused unchanged.
- No change to the training worker, hyperparameter handling, or the promote/demote flow.
- No new dataset readiness measure. ADR-010 owns readiness; accumulation is a different quantity (established in change 5).
- No judgement about whether a retrain is *worthwhile* — the surface presents evidence, a person decides.

## Currently-In-Force ADRs

| ADR | Decision Summary | Constraint on This Design |
|-----|-----------------|--------------------------|
| ADR-009-system-admin-sets-training-hyperparameters | A System Admin sets training hyperparameters at approval time, not at submission | A retrain request must not carry or set hyperparameters. It creates a job in `pending_approval` exactly like any other submission, leaving hyperparameters to the approval step. |
| ADR-006-training-infrastructure | Async Celery GPU workers consuming a training queue; jobs are enqueued on approval | The retrain request must enter the same queue-on-approval path. It must not enqueue directly, bypass approval, or use a different queue. |
| ADR-003-model-serving-topology | Per-tenant model serving topology | Accumulation and the consumed-span record are per tenant and per model version; the reset must be scoped to the version the run produced. |
| ADR-008-base-model-as-default | The base model serves as version 0 when a tenant has no active trained model | The retraining surface must behave sensibly for a tenant with no trained model, where there is no "current version" to measure a delta against. |
| ADR-010-per-entity-type-dataset-threshold | Dataset readiness is per entity type at 200 per type | If the decision surface shows a per-entity-type breakdown, it must read the existing threshold rather than defining one, and must present accumulation distinctly from readiness — they answer different questions. |
| ADR-001-tenant-data-isolation | Tenant isolation via separate PostgreSQL schemas | The consumed-span record and both surfaces resolve the tenant schema as existing endpoints do. |

## Decisions

### Decision 1: The training run records what it consumed, at completion

**Choice:** When a training run completes successfully, record the set of confirmed spans that went into its dataset, associated with the model version produced. Accumulation is then computed as spans created since the currently serving version's recorded set.

**Rationale:** This is the boundary gap between changes 5 and 6, and it is the kind of gap where each change can plausibly assume the other owns it. Change 5 defines the record and reads it; this change writes it. Recording at completion rather than at submission is deliberate: a job that is rejected at approval, or that fails, consumed nothing, and marking spans as consumed before the run succeeds would silently zero the accumulation figure without producing a model.

**Alternatives considered:**
- Record at submission time — rejected: a rejected or failed job would reset accumulation despite producing no model, losing the evidence that the retrain was never actually done.
- Recompute accumulation by timestamp against the model version's training date — simpler, requires no record, but is wrong whenever spans are backdated, imported, or created during a run. An explicit set is unambiguous.
- Store a copy of the consumed spans — rejected for the same reason change 5 rejected a separate pool table: it duplicates the spans and creates two places one can exist.

### Decision 2: A retrain request is an ordinary training job submission

**Choice:** Requesting a retrain from the decision surface creates a training job through the existing submission path. It enters `pending_approval` and is approved or rejected by a System Admin exactly like any other job. The request carries no hyperparameters.

**Rationale:** `training-approval` already exists, is already System Admin gated, and already handles the reject path with a reason. Building a parallel path for retrains would duplicate an approval mechanism and create two ways a training job can come into being, which is precisely the kind of divergence this plan has avoided elsewhere. ADR-009 puts hyperparameters at approval time, so a request that carried them would contradict it.

**Alternatives considered:**
- A distinct "retrain" job type with its own flow — rejected: a retrain is a training job; the only difference is what prompted it, which is metadata, not a different mechanism.
- Let the requester set hyperparameters — rejected: directly contradicts ADR-009.

### Decision 3: No automatic initiation, stated as a testable requirement

**Choice:** Specify explicitly that no accumulation value, threshold crossing, schedule, or completed run may create, enqueue, or schedule a training job, or promote a model version — and make that a scenario rather than only a design note.

**Rationale:** This is the decision that was deliberately reversed earlier in the plan, so it is the one most likely to be reintroduced by someone who reads "the pool has 500 spans" and concludes the system should act on it. A prohibition that lives only in prose is not checkable; as a requirement with a scenario it is. Changes 5 and 6 both carry this guard because both are places the temptation appears.

**Alternatives considered:**
- Leave it as a design note and a non-goal — rejected: non-goals are not verified, and this one needs to be.
- Add a configurable auto-retrain that defaults off — rejected: an off-by-default trigger is still a trigger, and the decision here was that the choice belongs to a person, not to a configuration value.

### Decision 4: The promotion surface shows evidence, and shows its limits

**Choice:** Present the candidate version's metrics alongside the currently promoted version's at the promotion decision point, together with the dataset size each was trained on. Where the two runs trained on materially different datasets, present that fact rather than presenting the numbers as directly comparable.

**Rationale:** The promote step is already a human decision, but currently the only evidence is that a run finished. Metrics make it a real decision. The caveat matters because change 3 established that pre-fix and post-fix metrics are not comparable, and the same applies to any two runs over materially different data — a surface that silently invites a comparison across incomparable runs is worse than one that shows nothing, because it produces confident wrong decisions.

**Alternatives considered:**
- Show metrics with no caveat — rejected for the reason above.
- Compute a single "is this better" verdict — rejected: that is the system making the decision, which is what this change exists not to do, and it would require a comparability judgement the data does not support.

### Decision 5: Behave sensibly with no trained model

**Choice:** For a tenant with no trained model (served by the base model per ADR-008), the retraining surface presents the state as "no trained model yet" rather than an accumulation figure of zero against a nonexistent version, and a first training run remains available through the existing path.

**Rationale:** "Zero spans since version 3" and "there is no version 3" are different states that a bare zero conflates. Change 5 already excludes base-model predictions from accumulation, so a base-model tenant would otherwise always show zero, which reads as "nothing to do" when the truth is "nothing has been trained".

**Alternatives considered:**
- Show zero — rejected: it is indistinguishable from a fully-retrained tenant with no new evidence, which is the opposite situation.

## Risks / Trade-offs

- [A person may not know what accumulation figure justifies a retrain, so the surface is informative but not actionable] → Partly inherent: there is no established figure, and ADR-010 records that even its own per-type threshold is not empirically derived. Mitigate by showing a per-entity-type breakdown rather than a single number, so the decision has structure even without a threshold (proposal Open Questions).
- [Recording consumed spans at completion means a long run's accumulation figure is stale while it runs] → Accepted: the alternative (recording at submission) is wrong in a worse way. Surfacing that a run is in flight is enough to explain the figure.
- [Side-by-side metrics invite comparison across runs trained on different data] → Decision 4 requires presenting dataset size and difference alongside; how prominently is an open question, and getting it wrong produces confident wrong promotions.
- [Someone later adds an auto-trigger because the figure is right there] → Decision 3 makes the prohibition a testable requirement in both changes 5 and 6; the guard is a scenario, not a comment.

## Migration Plan

1. Land the consumed-span recording at training completion first. It is the correctness fix and it is independently verifiable — accumulation should reset after a run and not before.
2. Land the retraining decision surface (read-only) and confirm the figure it shows behaves correctly across a retrain.
3. Land the retrain request action into the existing submission path.
4. Land the promotion decision surface.
5. Rollback: each step is independently revertable; the only schema use is the record change 5 already defines, and nothing existing changes shape.

## Open Questions

- All four questions from proposal.md remain open: what context beyond the raw count makes the decision judgeable, how to convey metric comparability limits, whether a retrain may be requested at zero accumulation, and who may request one.
- Should a retrain request record what prompted it (accumulation figure at request time, audit agreement rate from change 5) as job metadata? It would make the decision auditable later and costs little, but adds a field to the submission path this change otherwise leaves untouched.
- Once several retrains have happened, is accumulation-at-retrain-time worth reporting as a series, so a tenant can see whether they are retraining too often or too rarely? Out of scope here, but the consumed-span record makes it possible later.
- ADR-010 records that its per-type threshold should be revisited "once a model has trained against a per-type-balanced dataset". Changes 3, 4 and this one together make that possible. Whether to revisit remains a separate decision requiring its own superseding ADR — flagged across changes 3 and 4 and not resolved here either.
