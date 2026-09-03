## Context

After changes 1 and 2, a tenant can configure entity types with QA pairs and get LLM suggestions for a single document, approving each suggestion individually through the existing promote endpoint. That path does not scale to producing a trained model: it requires the tenant to already know their entity schema, it fires one HTTP request per document, and it requires individually promoting every suggestion across a corpus.

Change 3 fixes the export and training defects underneath, so a correctly annotated corpus now produces correctly aligned, untruncated, windowed training data.

What remains missing is everything between "tenant has documents and some QA pairs" and "tenant has a trained BERT v1". Three gaps: deriving the entity schema, pre-labeling at batch scale, and accepting a large batch of machine annotations at a cost proportional to trust rather than to corpus size.

Two existing mechanisms constrain the design. Dataset readiness is defined per entity type at 200 entities per type (`DATASET_READINESS_ENTITIES_PER_TYPE` in `src/gateway/api/v1/dashboard.py`, described in-code as "a single source of truth for the entity count that unlocks training", per ADR-010). Training submission and approval already exist: a job enters `pending_approval` and a System Admin approves it, setting hyperparameters at that point (ADR-009, `training-approval`).

## Goals / Non-Goals

**Goals:**
- Let a tenant discover their entity schema from their own documents rather than guessing it up front.
- Pre-label a 100-200 document batch as one trackable job.
- Make the human cost of accepting a machine-annotated batch proportional to how much the machine has earned trust, not to the batch size.
- Make every bulk acceptance auditable after the fact.

**Non-Goals:**
- No new entity type creation path — approved proposals go through the existing `entity-config` API so versioning, validation, and tenant scoping are inherited rather than duplicated.
- No new dataset readiness threshold. ADR-010 owns it (see Decision 5).
- No new training submission or approval mechanism — `training-jobs` and `training-approval` are reused as-is.
- No BERT-generated suggestions; the model does not annotate anything in this change. That is change 5.
- No retraining trigger or automation. That is change 6, and it is human-gated.
- No change to the per-document Suggest flow from changes 1 and 2.

## Currently-In-Force ADRs

| ADR | Decision Summary | Constraint on This Design |
|-----|-----------------|--------------------------|
| ADR-010-per-entity-type-dataset-threshold | Dataset readiness is per entity type at 200 entities per type; enforcement via `NER_MIN_ENTITIES_PER_TYPE` (default 0, inert); progress capped per type before averaging so an over-annotated type cannot mask a starved one | The readiness check added here MUST read the existing per-type threshold constant rather than defining its own, MUST evaluate the union of active entity definitions and spanned types (so a configured-but-unannotated type stays visible), and MUST NOT introduce a tenant-wide total as a gate. |
| ADR-009-system-admin-sets-training-hyperparameters | A System Admin sets training hyperparameters at approval time | The readiness check is advisory and pre-submission; it MUST NOT bypass, replace, or pre-empt the System Admin approval step, and MUST NOT set hyperparameters. |
| ADR-006-training-infrastructure | Async Celery workers with RabbitMQ; GPU workers for training specifically | The batch pre-labeling job is I/O-bound LLM work and MUST run on change 1's non-GPU `annotation.llm_jobs`-style queue, never the GPU `training.jobs` queue. |
| ADR-001-tenant-data-isolation | Tenant isolation via separate PostgreSQL schemas | The batch job, the proposal record, and the acceptance record all live in the tenant schema and resolve it the same way existing `annotation_service` endpoints do. A single LLM call must never span tenants, including in batch mode. |

## Decisions

### Decision 1: The LLM proposes entity types; it never creates them

**Choice:** Schema derivation produces a *proposal* — a list of candidate entity types with names, descriptions, and example values drawn verbatim from the seed documents. A human approves, edits, or rejects each candidate. Approved candidates are then created through the existing `entity-config` create API.

**Rationale:** Entity types are tenant configuration with versioning, validation, and downstream consumers (extraction targets, analytics projections). Letting a model write directly into that configuration would bypass every guarantee the entity-config capability provides and would let a single bad LLM run reshape a tenant's schema. Routing approved candidates through the existing API means this change inherits validation and versioning rather than reimplementing them. It also mirrors change 1's existing constraint that the LLM may never invent an entity type during extraction.

**Alternatives considered:**
- LLM writes entity types directly, human reviews after — rejected: the damage is already done and versioned by then, and it contradicts change 1's Entity Type Constraint requirement.
- Skip schema derivation; require the tenant to configure types manually first — this is the status quo and remains a valid path, but it asks a tenant to know their schema before looking at their documents, which is the harder half of the problem.

### Decision 2: Batch pre-labeling is one job over N documents, reusing change 1's per-document machinery

**Choice:** Add a batch trigger that accepts a document set and enqueues a single job. Internally the job iterates documents, reusing change 1's prompt construction, grounding, verification, and storage logic unchanged. The batch job records per-document outcome; failures on one document do not abort the batch.

**Rationale:** This is the endpoint change 2 deliberately deferred and flagged for revisit here. One job gives one thing to track, one failure surface, and server-side control over pacing and retries — none of which a browser loop can offer for 200 documents. Reusing change 1's internals rather than reimplementing means grounding and extractive-only guarantees cannot drift between the single and batch paths.

**Alternatives considered:**
- Keep the browser loop from change 2 — rejected at this scale: no backpressure, no resumability, and progress is lost if the user navigates away mid-batch.
- Fan out one Celery task per document from a parent task — reasonable and may be the implementation, but the requirement is a single trackable unit with per-document outcomes; whether that is one task or a chord is an implementation choice.

### Decision 3: Bulk acceptance is gated on a sampled agreement rate, not on reviewing everything

**Choice:** Before a batch's suggestions can be bulk-promoted to confirmed spans, a reviewer reviews a randomly drawn sample of the batch. The system computes an agreement rate from that review, records it, and permits bulk acceptance only if it clears a configured threshold. A batch below threshold is rejected as a whole.

**Rationale:** This is the central trade-off of the change. Reviewing 200 documents by hand removes the reason to automate; accepting 200 blind puts unverified labels into training, which is the failure mode changes 1 and 3 exist to prevent. Sampling makes the human cost proportional to trust rather than to corpus size, and the recorded rate is what converts "we think the LLM is good" into evidence. Rejecting as a whole rather than partially accepting avoids a dataset that is a silent mixture of verified and unverified labels with no way to tell them apart later.

**Alternatives considered:**
- Accept per-document as reviewed, no batch concept — this is changes 1 and 2's flow and stays available; it just does not scale to a bootstrap corpus.
- Accept the whole batch with no sampling — rejected: it is precisely the unverified-labels-into-training failure this plan has been avoiding since the first design discussion.
- Auto-accept suggestions above an LLM confidence score — rejected: LLM self-reported confidence is poorly calibrated, and change 1 deliberately left `source: "llm"` confidence semantics unspecified for that reason. A measured human agreement rate is evidence; a model's self-assessment is not.

### Decision 4: The sample is drawn randomly and the drawn set is recorded

**Choice:** The sample is randomly drawn from the batch, and the identity of the sampled documents is stored with the acceptance record.

**Rationale:** A reviewer choosing which documents to check, or the system taking the first N, produces an agreement rate that does not generalise to the batch — the first N documents of an upload are frequently the most similar to each other. Recording which documents were drawn is what makes the rate auditable afterwards; without it the number is unfalsifiable.

**Alternatives considered:**
- Let the reviewer pick — rejected: selection bias makes the measurement meaningless.
- Stratify the sample by entity type — better statistically, and worth revisiting, but it requires knowing per-document type distribution before review; deferred as a refinement rather than built on an unvalidated assumption.

### Decision 5: The readiness check reads ADR-010's threshold and is advisory

**Choice:** Before training submission, report per-entity-type counts against the existing `DATASET_READINESS_ENTITIES_PER_TYPE` value, naming types that fall short. The check informs; it does not block submission and does not replace the System Admin approval step.

**Rationale:** ADR-010 already defines readiness and its enforcement knob (`NER_MIN_ENTITIES_PER_TYPE`, inert by default). Adding a second gate here would recreate exactly the duplicate-threshold conflict ADR-010 was written to resolve — the same trap change 3 avoided with its split guard. Making it advisory keeps the actual gate where ADR-009 puts it: with the System Admin at approval time. The value is telling a tenant *before* a GPU run which labels are starved, which the current flow only reveals afterwards.

**Alternatives considered:**
- Block submission below threshold — rejected: it duplicates `NER_MIN_ENTITIES_PER_TYPE`'s job and takes a decision away from the System Admin approval step ADR-009 established.
- Skip the check entirely — rejected: the information exists and withholding it wastes a GPU run and a tenant's time.

## Risks / Trade-offs

- [A sampled agreement rate can clear the threshold while the unsampled remainder contains systematic errors the sample happened to miss] → This is inherent to sampling and cannot be eliminated, only bounded. Mitigate by recording the sample and rate so a later quality problem is traceable to the batch and rate that admitted it, and by keeping the threshold conservative until real data exists (proposal Open Questions).
- [Bulk-accepted spans are indistinguishable from individually reviewed ones once promoted] → Record the acceptance route on promoted spans so a dataset can be filtered or audited by provenance later; change 1 already established a `source` field precedent for exactly this reason.
- [Sending 100-200 documents to an external LLM multiplies the exposure of the unresolved data-residency question] → Hard-gated: this change must not be implemented before change 1 task 1.1 is answered. The risk is larger here than in changes 1 and 2, not different in kind.
- [A schema proposal may suggest plausible-sounding entity types that the tenant's downstream systems have no use for] → Human approval per candidate is the mitigation; the proposal is a starting point for a conversation, not an authority.
- [Batch pre-labeling cost is incurred before the acceptance gate, so a rejected batch is money already spent] → Accepted deliberately: the alternative is reviewing before pre-labeling, which is not possible. Mitigate by encouraging a small batch first, and by change 1's caching, which makes re-running an unchanged corpus after a configuration fix free.

## Migration Plan

1. Land schema proposal first. It is independently useful — a tenant gets a suggested entity schema without any batch or training work — and it produces the configuration the rest of the change consumes.
2. Land batch pre-labeling. At this point a tenant can pre-label a corpus, and the existing per-document review flow still works for accepting it, just slowly.
3. Land the sampled acceptance gate. This is what makes step 2 practical at scale.
4. Land the pre-submission readiness check. Purely additive reporting.
5. Rollback: each step is independently revertable. The new table is additive; suggestions and spans it touched remain valid because bulk promotion produces ordinary confirmed spans through the existing model.

## Open Questions

- All four measurement questions from proposal.md — agreement threshold, sample size, definition of agreement, and seed set size — remain open and must be answered with data from real reviewed batches, not chosen here.
- Should a rejected batch's suggestions be discarded or left in place for individual review? Leaving them costs nothing and preserves the option; discarding them prevents a reviewer from quietly accepting a batch the gate rejected. Needs a decision before implementation.
- Should stratified sampling by entity type replace uniform random sampling (Decision 4)? Better statistically; requires per-document type distribution up front. Revisit once real agreement data exists.
- ADR-010 records that its 200-per-type figure "should be revisited once a model has trained against a per-type-balanced dataset". This change plus change 3 is the first realistic path to such a dataset. Whether the revisit is warranted is a separate decision requiring its own superseding ADR — flagged, not resolved.
