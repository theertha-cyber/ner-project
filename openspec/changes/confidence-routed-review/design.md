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

- All five questions from proposal.md remain open: review threshold value, human-versus-LLM routing policy, span-level confidence aggregation, whether a correction triggers re-extraction, and audit cadence.
- **Retention bound for below-threshold predictions** — how long, or how many, before unreviewed ones are discarded? Unbounded retention on a large corpus is a real storage cost.
- **Should a rejected prediction ("not an entity") produce a negative training signal?** It is genuine information that the model was wrong, but representing it requires deciding whether the region becomes an explicit `O` or is simply left unlabeled. This interacts directly with the partial-labeling concern from change 1 and should not be decided casually.
- No in-force ADR governs "one model reviewing another model's output". If the LLM review route becomes load-bearing rather than a fallback, that may warrant an ADR — flagged, not resolved.
