## Why

After change 4 a tenant has a trained BERT v1 and it extracts entities from incoming documents. But nothing that happens at extraction time ever improves the model. Extraction already produces a per-entity confidence score and character offsets, and a human can already correct an extracted entity's value — yet those corrections stay in the extraction store and never become training data. Meanwhile, predictions below the configured confidence threshold are discarded outright at extraction time, so the very cases the model is least sure about, which are the most informative ones to learn from, are the ones thrown away.

This change closes that loop: route extraction results by confidence, surface the uncertain ones for review by a human or the LLM, and turn the resulting corrections into confirmed spans that accumulate for a future training run. It is change 5 of a 6-change plan and depends on change 4.

## What Changes

- Retain predictions that fall below the business-facing confidence threshold instead of discarding them, so they can be routed to review. **BREAKING (spec-level)**: the existing Post-processing confidence filtering requirement changes from "entities below the threshold SHALL be excluded from results" to "excluded from business-facing results but retained for review routing". Business consumers see exactly what they see today.
- Add a routing step that splits extraction output at a configurable review threshold: high-confidence predictions are accepted without review, low-confidence predictions enter a review queue.
- Add a review queue where a low-confidence prediction is resolved either by a human or by the LLM, according to a configurable per-tenant policy. Both routes produce the same outcome shape.
- Turn a confirmed or corrected review outcome into a confirmed span in the annotation store, so it becomes training data. Record that the span originated from production review rather than from manual annotation or batch acceptance.
- Track how much reviewed material has accumulated since the tenant's current model version was trained, and expose that figure. This change **stops there** — nothing is triggered automatically by the figure growing.
- Add a periodic audit sample over auto-accepted high-confidence predictions, so the accept path is not entirely unchecked. Reuses change 4's sampling and agreement-rate machinery.

## Capabilities

### New Capabilities

- `confidence-routed-review`: confidence-based routing of extraction output, the low-confidence review queue and its human/LLM resolution routes, conversion of review outcomes into confirmed spans, accumulation accounting against the current model version, and audit sampling of the auto-accept path.

### Modified Capabilities

- `extraction-service`: the **Post-processing confidence filtering** requirement changes so below-threshold predictions are retained for review routing rather than discarded, while remaining excluded from business-facing extraction results.

## Impact

- **Backend**: new routing, queue, and review-resolution endpoints plus their storage in `src/annotation_service` (or a sibling module), reusing change 1's LLM client for the LLM review route and change 4's sampling and agreement-rate logic for auditing; routing and retention of below-threshold predictions in `run_batch_extraction` in `src/extraction_service/worker.py`. This is not the file originally named here: `src/extraction_service/api/v1/extraction.py` is the ad-hoc, document-less extract endpoint, and a prediction retained there could never become a span. See design.md Decision 14.
- **Database**: additive. A review queue table and a record of which spans have been included in which training run, both in the tenant schema.
- **Frontend**: a review queue surface. The existing extraction review UI is not replaced — this queue is annotation-oriented and feeds training, which the existing value-correction flow does not.
- **Depends on**: change 4 (a trained model must exist and the acceptance/sampling machinery is reused), and transitively changes 1 and 3.
- **No impact**: business-facing extraction results are unchanged; analytics, chat, and the entity projection consume exactly what they consume today. Training submission and approval are untouched.

## Open Questions

- **Review threshold value, and its relationship to the existing business threshold.** These are two different decisions — "is this good enough to use" versus "is this uncertain enough to be worth a human's time" — and conflating them into one number would be a mistake. Both should be configurable independently, with values measured rather than guessed.
- **What decides human versus LLM review?** Options include always-LLM-first with human escalation on disagreement, a confidence band split, or a per-tenant policy switch. This needs a decision before implementation; the spec requires only that both routes exist and produce the same outcome shape.
- **Span-level confidence derivation.** BERT produces per-token probabilities; a multi-token entity needs one number. Minimum across tokens, mean, or first-token probability all behave differently at the boundaries, and the choice changes which entities land in the queue. Must be decided and stated, not left implicit.
- **Should a corrected extraction re-run extraction for that document?** A correction implies the model was wrong somewhere nearby; whether to re-extract is a product decision with cost implications.
- **Audit sample cadence and volume for the accept path** — currently unspecified beyond "periodic". Needs a basis, and it should be cheap enough that it actually gets done.
