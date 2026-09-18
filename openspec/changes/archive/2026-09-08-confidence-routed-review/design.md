## Context

`src/extraction_service/api/v1/extraction.py` already does most of what this change needs. It runs the tenant's model over a document, derives each predicted entity's character offsets by searching the source text (`body.text.find(token_text, char_offset)`), and returns `ExtractedEntity` objects carrying `entity_type`, `value`, `confidence`, `start_offset`, and `end_offset`. It then filters out everything below `settings.confidence_threshold` (default 0.50) and sorts the remainder by confidence.

The `extraction-service` capability also already has a **Review and correct entities** requirement: a user can PATCH an extracted entity to set `review_status` and `corrected_value`, logged with the correcting user and timestamp.

Two gaps prevent this adding up to a training loop:

- The existing correction flow is **value-level**, not span-level. It records that the extracted value "AcmeCorp" should read "Acme Corp". Training needs a character span over document text with an entity type. The offsets exist on the extracted entity, so the translation is possible — but nothing currently performs it, and a corrected *value* that differs in length from the original does not straightforwardly correspond to the original offsets.
- Below-threshold predictions are **discarded** before anything can see them. Those are exactly the cases the model is least certain about and therefore the ones most worth learning from.

## Goals / Non-Goals

**Goals:**
- Route extraction output by confidence rather than discarding the uncertain part.
- Resolve low-confidence predictions through either a human or the LLM, producing one consistent outcome shape.
- Convert review outcomes into confirmed spans so they become training data.
- Report how much reviewed material has accumulated since the current model version was trained.
- Give the auto-accept path some check, rather than none.

**Non-Goals:**
- **No automatic retraining, and no trigger of any kind.** This change reports accumulation and stops. Change 6 owns the decision, and it is human-gated.
- No second inference path. BERT already runs in extraction; this change routes its output rather than re-running the model.
- No change to what business consumers see from extraction.
- No replacement of the existing value-correction flow — it keeps working for its own purpose.
- No LLM pre-labeling of new documents (that is changes 1, 2 and 4); the LLM appears here only as a reviewer of uncertain model predictions.

## Currently-In-Force ADRs

| ADR | Decision Summary | Constraint on This Design |
|-----|-----------------|--------------------------|
| ADR-008-base-model-as-default | The base model serves as the default inference model (version 0) when a tenant has no active trained model | Routing must behave sanely when predictions come from the base model rather than a tenant-trained one. Base-model output should not silently accumulate into a tenant's training pool as if it were tenant-specific evidence — see Decision 5. |
| ADR-003-model-serving-topology | Per-tenant model serving topology | Routing consumes whatever version served the prediction and must record it, so accumulation is attributable to a specific model version rather than to "the model". |
| ADR-006-training-infrastructure | Async Celery + RabbitMQ; GPU workers for training specifically | The LLM review route is I/O-bound and must run on change 1's non-GPU queue, never the GPU `training.jobs` queue. |
| ADR-001-tenant-data-isolation | Tenant isolation via separate PostgreSQL schemas | The review queue, its outcomes, and the accumulation record all live in the tenant schema and resolve it as existing endpoints do. |
| ADR-010-per-entity-type-dataset-threshold | Dataset readiness is per entity type at 200 per type | Accumulation reporting here is a *delta since last training*, which is a different quantity from readiness. It must not be presented as a readiness measure or compared against ADR-010's threshold, or the two will be confused. |

## Decisions

### Decision 1: Two thresholds, not one

**Choice:** Keep the existing business-facing `confidence_threshold` exactly as it is, and add a separate, independently configurable **review threshold** that governs routing. Below-threshold predictions are persisted for routing but remain excluded from business-facing results.

**Rationale:** "Is this good enough to act on?" and "is this uncertain enough to be worth a person's time?" are different questions with different right answers. Collapsing them into one number means tuning review volume silently changes what analytics and chat see, which is a bad coupling. Persisting rather than discarding is the minimal change that makes routing possible at all.

**Alternatives considered:**
- Reuse the single existing threshold for both — rejected: it makes the business surface and the annotation workflow share a knob neither of them owns.
- Lower the existing threshold so low-confidence entities survive — rejected: that changes what every business consumer sees in order to serve an annotation workflow.

### Decision 2: Route extraction output; do not re-run the model

**Choice:** Routing consumes the predictions extraction already produced, in the same run. No separate inference pass over the document.

**Rationale:** The model has already scored every token; running it again to get the same numbers costs GPU time and introduces the possibility of the two paths disagreeing about what the model said. Extraction already derives offsets by searching the source text, which is the correct approach and the one change 3 moves export toward.

**Alternatives considered:**
- A dedicated annotation-inference endpoint separate from extraction — rejected: two inference paths over the same document that can drift apart, for no benefit.

### Decision 3: A review outcome produces a span from offsets, not from the corrected value

**Choice:** When a review outcome is converted into a confirmed span, the span is defined by character offsets over the document text. A reviewer adjusting an entity adjusts its offsets. The existing value-level `corrected_value` flow is not the input to span creation.

**Rationale:** Training needs "characters 45-53 of this document are an organisation". A corrected *value* ("AcmeCorp" → "Acme Corp") is a normalisation of what the text says, not a statement about where the entity is — and when the corrected value differs in length from the source text, it no longer corresponds to any span at all. Treating a value correction as a span would reintroduce exactly the "the answer is not in the text" problem change 1 exists to prevent. Value normalisation remains a separate, legitimate concern handled by the existing flow.

**Alternatives considered:**
- Derive the span by searching the document for the corrected value — rejected: fails whenever the correction normalises rather than re-quotes, which is the common case for the existing flow.
- Accept both and prefer whichever is present — rejected: silently mixes two different meanings into one training signal.

### Decision 4: Human and LLM review routes produce the same outcome shape

**Choice:** Both routes resolve a queued prediction to the same outcome structure — confirmed as-is, corrected to different offsets or type, or rejected as not an entity — and both record which route produced it.

**Rationale:** Downstream span creation and accumulation accounting should not care which reviewer type acted, or they will need branching logic that can diverge. Recording the route is what makes it possible to later compare LLM reviewer agreement against human reviewer agreement, which is the evidence needed to decide how much to lean on the LLM route.

**Alternatives considered:**
- LLM route writes spans directly, human route goes through review — rejected: gives the LLM a privileged, unaudited path into training data, which is the failure mode this entire plan has been avoiding.

### Decision 5: Accumulation is a delta against a specific model version, and base-model output does not count

**Choice:** Track reviewed spans as an accumulation *since the model version currently serving the tenant was trained*, recording the serving model version on each routed prediction. Predictions served by the base model (ADR-008's version 0 fallback) are routed and reviewed normally, but are recorded distinctly and do not count toward a tenant-specific accumulation figure.

**Rationale:** "How much new evidence exists since the model was trained" is the question change 6 needs answered, and it is only meaningful relative to a specific version. Base-model predictions are not evidence about a tenant-trained model's weaknesses — counting them would inflate the figure with material that says nothing about whether retraining the tenant's model would help.

**Alternatives considered:**
- A single global counter of reviewed spans — rejected: it never resets against a version and so cannot answer change 6's question.
- A separate "training pool" table holding copies of spans — rejected: duplicates the spans table and creates two places a span can exist. A marker of what has been trained on is sufficient.

### Decision 6: Audit-sample the auto-accept path

**Choice:** Periodically draw a random sample of auto-accepted high-confidence predictions and route them through the same review flow, recording the agreement rate.

**Rationale:** Without this, high-confidence predictions are never checked by anyone, so a model that is confidently wrong about a particular entity type produces no signal at all — it just quietly degrades the extracted data. Change 4 already built random sampling and agreement-rate measurement for batch acceptance; reusing it here is cheap. This is an addition to the originally sketched flow, where the accept branch was terminal.

**Alternatives considered:**
- Leave the accept path unchecked — rejected: it is the only path with no feedback whatsoever, and confident errors are the hardest kind to notice.
- Audit everything above the threshold — rejected: that is just full review with extra steps.

### Decision 7: The review threshold is 0.90, configured independently

**Choice:** `review_confidence_threshold`, default **0.90**, added as its own setting alongside the existing `confidence_threshold` (0.50). A prediction at or above 0.90 is auto-accepted; below 0.90 it enters the review queue. Changing one never changes the other.

**Rationale:** 0.90 matches the worked scenarios in the spec and starts conservative — it generates enough queue volume to *measure* the real review rate rather than guessing it, which is what the proposal asks for. It can be tuned down once that measurement exists.

**Alternatives considered:**
- 0.80 — rejected for now: lower burden, but captures fewer uncertain cases as training signal in exactly the period where the measurement matters most.
- Per-tenant storage — deferred: same default, more schema and admin surface than this change needs. Revisit if tenant corpora diverge.

### Decision 8: Span confidence is the minimum across constituent tokens

**Choice:** Span-level confidence is `min()` over the constituent tokens' probabilities. This is not a new rule — `aggregate_confidence` in `src/extraction_service/services/entity_normalizer.py` already implements it, and this change adopts it rather than introducing a competing aggregation.

**Rationale:** An entity is only as trustworthy as its weakest token; the minimum keeps the score conservative and stops confident neighbours masking a weak boundary token. Introducing a second aggregation rule for routing would mean the queue and the extraction store disagreed about the same span's confidence.

**Alternatives considered:**
- Mean or first-token — rejected: both mask weak boundaries, which is precisely the failure the queue exists to catch, and both would diverge from the in-force behaviour.

### Decision 9: Routing operates on reconstructed entities, not word-level predictions

**Choice:** Routing consumes the output of `reconstruct_entities`, so a queued item is a whole BIO span with min-aggregated confidence and character offsets — not a single word.

**Rationale:** `src/extraction_service/api/v1/extraction.py` currently emits one `ExtractedEntity` per word and thresholds those, without calling `reconstruct_entities`. Routing that output directly would fill the queue with fragments of multi-token entities, and any span created from a fragment would be wrong. Training needs whole spans, and Decision 8 is only meaningful over a reconstructed span. This is a larger change to the extraction path than the task list implies, and is recorded here so it is not mistaken for scope creep.

**Alternatives considered:**
- Route word-level output as-is — rejected: reviewers would judge fragments, and every multi-token entity would produce an incorrect span.

### Decision 10: Human review only at first; the LLM route is a per-tenant switch, default off

**Choice:** A per-tenant review policy setting selects the route. It ships defaulting to human-only. The LLM route is implemented and tested but is not enabled for any tenant until human-route agreement data exists to compare it against.

**Rationale:** This is Migration Plan steps 2-3 stated as a decision. It gives the safe, observable rollout the plan already calls for, and it produces exactly the baseline needed to judge whether the LLM reviewer's agreement diverges from a human's — the evidence Decision 4 exists to make available.

**Alternatives considered:**
- Always-LLM-first with human escalation — rejected for now: gives the LLM the first word on all training signal before any agreement baseline exists.
- Confidence band split — rejected: adds a third threshold to tune before the first two have been measured.

### Decision 11: Below-threshold predictions are discarded on resolution, with an age cap

**Choice:** A retained below-threshold prediction is deleted once it has been reviewed and converted (to a span, or to a recorded rejection). Anything still unresolved is purged after a configurable age, default **90 days**.

**Rationale:** Bounds storage on both paths. Discarding on resolution stops the queue accumulating dead rows once its information has been extracted into a span or an outcome; the age cap bounds the abandoned path, where a queue that outpaces its reviewers would otherwise grow without limit. The recorded review outcome survives the deletion, so accumulation accounting and route-agreement comparison are unaffected.

**Alternatives considered:**
- Age cap alone — rejected: resolved rows linger until they age out, for no benefit.
- Queue size cap — rejected: couples storage to review throughput, so a slow week silently discards unreviewed evidence.

### Decision 12: A rejection records an outcome and produces no training signal

**Choice:** Rejecting a prediction as "not an entity" records a rejected review outcome. It creates no span, and it does not write an explicit `O` over the region.

**Rationale:** The spec already requires no span from a rejection. Writing an explicit `O` would assert more than the reviewer actually checked — they rejected *this type at these offsets*, not every type over that region — and it would reintroduce change 1's partial-labeling problem, where an unlabeled region becomes indistinguishable from a confirmed non-entity. The rejection is still retained as an outcome, so the information is not lost and a later change can represent it if an ADR justifies doing so.

**Alternatives considered:**
- Explicit `O` over the rejected region — rejected: asserts an unchecked negative, and collides directly with the partial-labeling concern.

### Decision 13: Audit sampling runs weekly at max(20, 5%), capped at 100

**Choice:** Per tenant, weekly, draw `min(100, max(20, ceil(0.05 * N)))` from the auto-accepted predictions since the last audit, where `N` is that population. If `N` is below the floor, the whole population is audited.

**Rationale:** Cheap enough that it actually gets done, which the proposal names as a requirement. The floor of 20 keeps the agreement rate meaningful on a small tenant, where 5% would otherwise sample almost nothing; the cap of 100 stops a large tenant drawing an unreviewable sample. Weekly gives a rate that moves fast enough to notice a confidently-wrong model without a daily operational cost.

**Alternatives considered:**
- Daily fixed 20 — rejected: noisier per run, constant cost, no better signal.
- Monthly 5% uncapped — rejected: unbounded at the top end and near-zero at the bottom, which is the worst of both.

### Decision 14: Routing lives in the batch extraction worker, not the ad-hoc `/extract` endpoint

**Choice:** Confidence routing, retention of below-threshold predictions, and review-queue population all happen in `run_batch_extraction` in `src/extraction_service/worker.py`, immediately after `reconstruct_entities`. The ad-hoc `POST /api/v1/extract` endpoint keeps its existing behaviour unchanged: it filters on `settings.confidence_threshold` and returns entities, persisting nothing.

**Rationale:** proposal.md and tasks.md both name `src/extraction_service/api/v1/extraction.py` as the filtering step to change. That file cannot serve this change's purpose, for two reasons found during implementation:

- `POST /api/v1/extract` is stateless and document-less — `ExtractRequest` is `{text: str}`, and the endpoint writes nothing. `{schema}.spans.document_id` is `NOT NULL REFERENCES documents(id)`, so a prediction retained on that path could never become a confirmed span. Converting review outcomes into training data — the entire point of the change — would be unreachable.
- `settings.confidence_threshold` is applied in exactly one place in the codebase, and it is that endpoint. `run_batch_extraction`, the path that actually persists entities against a document, never applies it. So the premise "below-threshold predictions are discarded" is true only of the ad-hoc endpoint; on the document-backed path nothing is being discarded today, and the retention requirement is really a *routing* requirement.

The worker is also where the prerequisites already sit: `doc_id`, the `model_version` read from the serving response, and the `reconstruct_entities` call that Decision 9 requires routing to sit downstream of. Putting routing anywhere else would mean re-deriving all three.

**Consequence for the extraction-service spec:** the modified **Post-processing confidence filtering** requirement is satisfied on the document-backed path. The ad-hoc endpoint's filtering behaviour is unchanged and its existing regression tests continue to hold, which is what keeps "business consumers see exactly what they see today" literally true.

**Alternatives considered:**
- Route in both paths — rejected: ad-hoc rows have no document, so they would be queue entries that dead-end at span creation, adding surface for no reachable outcome.
- Follow the task list literally — rejected: leaves the change structurally unable to create a single span.

### Decision 15: The visibility guarantee is about the routing store, not about filtering `document_entities`

**Choice:** `document_entities` is left exactly as it is. The guarantee this change makes is that the *routing store* (`routed_predictions`) is read by no business-facing surface, and that routing a prediction changes nothing a consumer receives. The extraction-service spec's visibility requirement and its third scenario were narrowed to say that, rather than to require a filter.

**Rationale:** the original wording — "exactly 3 entities SHALL be returned" for a run with 3 above and 2 below the threshold — assumed the document-backed path already filtered on `settings.confidence_threshold`. It does not, and never has. `run_batch_extraction` passes its full `normalized_entities` list to `insert_document_entities`, which writes every row it is given; `filter_valid_entities` gates on value shape and never reads confidence. A 0.30-confidence entity is therefore in `document_entities` today and is visible to `chat_api`'s entity resolver, its SQL generator, and `document_service`.

That leaves two mutually exclusive readings, and the change's own text picks one of them: proposal.md and task 2.2 both say business consumers must see *exactly what they see today*. Adding the filter to satisfy the scenario literally would delete entities those consumers currently receive — a silent regression in chat and analytics, introduced by an annotation feature, which is precisely the coupling Decision 1 exists to prevent. It would also make task 9.6's byte-identical check unsatisfiable by construction.

The narrowed guarantee is the one that is both true and worth having: retention is invisible because it happens somewhere nothing business-facing reads, not because a filter removes it afterwards.

**Consequence:** whether `document_entities` *should* be confidence-filtered is a real question, but it is a pre-existing question about extraction, not something this change introduced or should settle. It is left untouched and flagged here.

**Alternatives considered:**
- Filter `document_entities` on `confidence_threshold` — rejected: changes what every business consumer sees, in order to serve an annotation workflow, and contradicts this change's own stated non-impact.
- Filter behind a default-off setting — rejected: adds a third threshold-shaped knob and settles nothing; the question belongs to extraction, not here.

### Decision 16: An audit measures the accept path; it neither consumes it nor feeds training data

**Choice:** An audit-origin review outcome is recorded like any other, and stops there. Two behaviours distinguish it from queue review:

- The audited prediction is **not discarded**. `resolve_prediction` takes a `discard` flag, false for audit origin, so the row keeps its `accepted` disposition. Predictions already audited are excluded from later draws by joining `review_outcomes` on `origin = 'audit'`, so no prediction is audited twice and no schema column is needed to say so.
- A confirmed audit outcome **creates no span**. Span creation is reached only from queue-origin outcomes.

**Rationale:** the audit exists because the accept path otherwise has no feedback at all (Decision 6). It is a measurement instrument, and both behaviours follow from that.

Discarding an audited prediction would mean each audit shrank the population the next audit samples from, so a rate measured over 500 and one measured over 480 would be silently non-comparable — and `audit_samples.population_size` is stored precisely so those figures *can* be compared. An instrument that consumes what it measures is the wrong instrument.

Creating spans from audit confirmations would grow accumulation by auditing rather than by reviewing uncertain cases. That inverts what the figure means: accumulation is meant to say "here is new evidence about what the model gets wrong", and filling it with high-confidence predictions a reviewer agreed with would bias the training set toward examples the model already handles. It would also let a tenant inflate its own accumulation figure by auditing more often, which is not a lever anyone should have.

The shared resolution path is preserved in both cases — the audit route calls the same `resolve_prediction`, and the two behaviours are parameters of it rather than a second implementation, so Decision 4's "no privileged path into training data" still holds by construction.

**Consequence:** a sampled prediction the audit judged wrong keeps its `accepted` disposition. That is deliberate: the audit records the disagreement as an outcome and reports a rate; it does not retroactively re-decide individual predictions. Acting on a poor agreement rate is a human decision about the model, not a per-row correction.

**Alternatives considered:**
- Discard audited predictions like queue-resolved ones — rejected: makes successive `population_size` figures non-comparable, for no benefit.
- Let audit confirmations create spans — rejected: grows accumulation from the cases the model already gets right, and makes the figure sensitive to audit frequency.

## Risks / Trade-offs





- [Retaining below-threshold predictions increases stored volume, potentially substantially on large corpora] → Retention should be bounded (by age, by queue size, or by discarding once reviewed and converted), and that bound should be explicit rather than emergent. Flagged in Open Questions.
- [Low-confidence review could flood a queue faster than any human can work it] → The review threshold is configurable precisely so volume can be tuned, and the LLM route exists to absorb volume a human cannot. If the queue still outpaces both, that is information about the model, not a queue problem.
- [The LLM reviewing BERT's output means one model grading another, with correlated blind spots] → Mitigated only partially by recording the route so LLM-reviewed and human-reviewed outcomes can be compared. If their agreement diverges materially, the LLM route's weight should be reconsidered — which is why Decision 4 requires the route be recorded.
- [Span-level confidence derived from token probabilities behaves differently at entity boundaries depending on the aggregation chosen] → Called out as an open question requiring an explicit decision; whichever is chosen must be stated, because it silently determines what lands in the queue.
- [Accumulation figures could be misread as readiness] → Decision 5 keeps them version-scoped and ADR-010's threshold governs readiness; the two must be presented distinctly.

## Migration Plan

1. Change the extraction filtering step to persist below-threshold predictions while continuing to exclude them from business-facing results. Verify business consumers see no change.
2. Land routing and the review queue, with the LLM route disabled — human review only. This is safe and observable.
3. Enable the LLM review route once human-route agreement data exists to compare against.
4. Land accumulation accounting. Purely additive reporting; nothing consumes it until change 6.
5. Land audit sampling of the accept path.
6. Rollback: each step is independently revertable; all schema changes are additive, and spans already created remain ordinary confirmed spans.

## Open Questions

Resolved during implementation and recorded as Decisions 7-13: review threshold value (D7), span-level confidence aggregation (D8), human-versus-LLM routing policy (D10), retention bound for below-threshold predictions (D11), whether a rejection produces a negative training signal (D12), and audit cadence and volume (D13). Decision 9 records a routing-granularity gap found in the existing extraction path.

Still open:

- **Should a corrected extraction re-run extraction for that document?** A correction implies the model was wrong somewhere nearby; whether to re-extract is a product decision with cost implications. Not required by this change.
- No in-force ADR governs "one model reviewing another model's output". Decision 10 keeps the LLM route off by default precisely so this stays non-load-bearing. If it becomes load-bearing, that warrants an ADR — flagged, not resolved.
