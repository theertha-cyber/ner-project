## Why

`harden-chat-pipeline-correctness` repaired the contracts between orchestration, retrieval, SQL, context assembly, and error propagation, and explicitly listed *"NER model quality, `NAME` entity recall, value normalization punctuation"* as **not changing**. Those are now the binding constraint. This change addresses them.

A read-only forensic pass over the live development tenant `d2eb33ab-…` (214 documents, 9 processed, 8 with entities, 364 `document_entities` rows, 20 extraction runs) traced representative entities from source text through BERT output, reconstruction, normalization, persistence, and into the SQL a structured query would issue. **Entity data is a real bottleneck, but the dominant, measurable defects are deterministic pipeline bugs downstream of BERT — not model quality.** Attributing them to the model, and reaching for an LLM to paper over them, would spend token cost on problems a regex fixes.

### Measured defects, attributed

| # | Defect | Evidence (tenant `d2eb33ab`) | Earliest origin |
|---|---|---|---|
| 1 | `confidence` is a **raw logit**, not a probability | `inference_service.py:191` — `scores = np.max(logits, axis=-1)[0]`, no softmax. Persisted range **2.85–7.44**, mean 5.63, **0 of 364 rows ≤ 1.0**. `settings.confidence_threshold = 0.50` filters nothing at `extraction.py:96`. The base-model fallback path (`inference_service.py:326`) returns pipeline `score`, a real probability — **the two inference paths emit incomparable scales into the same column** | model serving |
| 2 | Multi-token entity split by an over-strict adjacency guard | Text: `"Having two and a half years of experience"`. BERT emitted a **correct contiguous BIO sequence**: `B-YEARS_OF_EXP two`, `I-YEARS_OF_EXP half`, `I-YEARS_OF_EXP years`. `_is_adjacent` (`entity_normalizer.py:82-100`) requires `word_index == prev + 1`; `and`/`a` are `O` and were filtered out by model serving, so the gap of 2 splits the entity. Persisted as two rows: `two` → `value_number 2.0`, `half years` → `value_number 0.5`. **The normalizer is innocent**: `normalize_value("two and a half years", "duration", "years")` returns `2.5` correctly when given the whole span | entity reconstruction |
| 3 | Zero-width space (U+200B) survives canonicalization | `canonicalize()` applies NFKC + casefold + `\s+` collapse; Python `\s` does not match U+200B (category `Cf`, not `Zs`), and NFKC does not remove it. 9 rows carry it. `WHERE entity_type='JOB_TITLE' AND normalized_value = 'software engineer'` returns **2**; `ILIKE '%software engineer%'` returns **7**. **71% of matching rows are unreachable by exact equality** | normalization |
| 4 | Trailing punctuation retained on `entity_value` and in `char_end` | `_tokenize_span` (`worker.py:19`) splits on `\S+`, so punctuation binds to the word before the model ever sees it. **181 of 364 rows (49.7%)** have `entity_value` ending in `.,;:)`. `canonicalize` strips *surrounding* punctuation from `normalized_value` only — interior stays (`uniqlo co., ltd`), and openers are orphaned (`o konni, pathanamthitta (dist`) | worker tokenization |
| 5 | Deterministic parser gap on a common surface form | `"2 years of experience,"` → `value_number NULL`; `"2+ years of experience"` → `2.0`. `_read_number` tries `_digits_to_number` (single-token regex, fails on multi-word) then `_words_to_number` (alphabetic tokens only, ignores the digit). Identical semantics, opposite outcomes | semantic normalization |
| 6 | Curly quotes and empty values persisted | 4 rows contain U+2019 (`st.xavier’s college` — never matches an ASCII apostrophe literal); **2 rows have `normalized_value = ''`** (from `entity_value = ','`); 16 rows have `length(normalized_value) <= 2` | normalization + persistence (no validity gate) |
| 7 | Genuine BERT type/boundary errors | `B-COMPANY HANNAH`, `B-COMPANY VISHNU`, `B-COMPANY AJAYDEV` (person names), `B-DEGREE JAVA`, `B-ADDRESS Arjun`, `B-ADDRESS github.com/definitelyarjun`, `PHONE_NUMBER 2079 993` / `695571` / `Z5060835` (passport number). `NAME` exists on only **4 of 8** extracted documents — resumes without a name row cannot be resolved by `entity_resolver._lookup_candidate_rows` | **BERT extraction** |
| 8 | Duplicate rows inflate counting queries | 364 rows, **289 distinct `(document_id, entity_type, normalized_value)`** — 20.6% duplicates. `node.js` ×8, `react` ×6 in one document. Faithful to repeat mentions, but `COUNT(*)` and per-document ranking read them as evidence weight | persistence design (no dedup policy) |

**Attribution:** defect 7 is BERT. Defects 1–6 and 8 are not — they are deterministic bugs in serving, reconstruction, normalization, and persistence. A useful signal for routing: the four confirmed misclassifications in defect 7 carry logits **3.10–4.18**, all below the corpus **p10 of 4.29** (median 5.76). Rank-relative confidence separates bad extractions today; the absolute threshold in settings does not.

### What an LLM post-processor can and cannot buy

- **Cannot** fix defects 1–6 or 8 more cheaply or more reliably than the deterministic fix. Sending every entity to `gpt-4o-mini` to strip a zero-width space would be absurd.
- **Can** address defect 7 — type misclassification, boundary errors, and invalid artifacts — where the deterministic layer has no rule and the evidence is in the surrounding document text.
- **Cannot** fix missing `NAME` rows without re-reading the document, which is out of scope by the user's own constraint (BERT stays the primary extraction mechanism). Recall gaps stay a training-data problem.

So the change is sequenced: **deterministic repairs first, LLM post-processing second, gated on confidence and disabled by default.**

## What Changes

### A. Confidence calibration (blocking — everything else depends on it)

- `model_serving` SHALL apply softmax over the label axis and emit a calibrated probability in `[0, 1]`, replacing the raw `np.max(logits)` at `inference_service.py:191`. Both the ONNX path and the base-model fallback SHALL emit the same scale. **BREAKING** for any consumer reading the current logit range — currently none reads it meaningfully, because `settings.confidence_threshold = 0.50` never matched.
- Existing `document_entities.confidence` values are logits on an incomparable scale. They SHALL NOT be rewritten in place; rows SHALL carry an extraction-schema marker so calibrated and uncalibrated rows are distinguishable, and confidence-gated routing SHALL only consider calibrated rows.

### B. Deterministic repairs (no LLM, no token cost)

- `canonicalize()` SHALL strip Unicode format characters (`Cf`, incl. U+200B/U+FEFF) and fold typographic punctuation (U+2019→`'`, U+2013/U+2014→`-`) before casefolding.
- `_is_adjacent` SHALL permit an `I-` continuation across a bounded intra-sentence gap on the same page, instead of requiring strict `word_index + 1`. The cross-page stitching it was written to prevent is preserved by keeping the page and gap bounds.
- Entity spans SHALL be trimmed of leading/trailing punctuation **with `char_start`/`char_end` adjusted to match**, so offsets keep pointing at the text the value names.
- `_read_number` SHALL parse a leading numeral followed by trailing words (`"2 years of experience"`), closing the gap that makes `2+` parse and `2` not.
- A **validity gate** SHALL reject entities whose canonical value is empty, punctuation-only, or below a minimum length before persistence, instead of writing them.
- A **duplicate policy** SHALL be defined and applied: identical `(entity_type, normalized_value)` within a document collapses to one row carrying an occurrence count and the first span, so `COUNT(*)` stops reading repetition as weight. **BREAKING** for any query relying on one row per mention.

### C. LLM post-processing (new, optional, off by default)

- A new post-processing stage SHALL run between reconstruction+normalization and persistence, over **candidate entities only** — those below a calibrated-confidence threshold or matching a deterministic suspicion rule — never over the whole document.
- The LLM SHALL be constrained to a strict decision contract (`keep` / `modify` / `merge` / `reject`) with structured fields, validated before persistence. Invalid output SHALL never reach the database.
- The LLM SHALL NOT invent entities: every emitted value must be a substring of, or a normalization of, the document text it was shown. Emissions failing that check SHALL be discarded and the BERT row persisted unchanged.
- Post-processing SHALL be **fail-open**: a timeout, provider error, rate limit, or invalid response SHALL persist the validated BERT result and mark the run degraded. A successful BERT extraction is never lost to a post-processing failure.

### D. Provenance

- `document_entities` SHALL retain what BERT produced alongside what post-processing produced, sufficient to answer "what did BERT extract?" and "what exactly did the LLM change?", without a second table and without breaking existing readers. Schema migration required.

### E. Business-user processing mode

- `POST /api/v1/extract-batch` SHALL accept a server-validated processing mode. **BREAKING**: the endpoint currently takes only a `documentIds` query parameter and no body.
- `extraction_runs` SHALL record the mode actually used and the post-processor model/prompt version. Schema migration required.
- Default SHALL be **BERT-only**. Changing the UI mode SHALL NOT reprocess existing results.
- The Batch Extraction modal control is specified as a backend contract in this change; **the UI is not implemented here.**

### F. Evaluation

- An entity-level evaluation harness SHALL measure precision / recall / F1, exact-value accuracy, and entity-type accuracy for BERT-only vs BERT+post-processing over a labelled fixture drawn from real tenant documents, including a **hallucination rate** metric — an entity emitted with no textual support is a failure regardless of how much F1 improves.
- The existing retrieval golden set (`src/shared/retrieval/eval/`) SHALL be extended with structured-query success rate, so entity changes are scored on downstream retrieval, not on how tidy the values look.

### Explicitly not changing

BERT training data or model architecture; `NAME` recall (a training problem, not a post-processing one); document ingestion / OCR / PDF text extraction; chunking; retrieval orchestration, SQL generation, or context assembly (owned by `harden-chat-pipeline-correctness`); the Batch Extraction UI implementation.

## Capabilities

### New Capabilities

- `entity-postprocessing`: the optional LLM post-processing stage — candidate selection, the permitted-transformation contract, the structured output schema and its validation, the no-invention rule, fail-open behaviour, tenant isolation, and prompt/model versioning.
- `entity-extraction-provenance`: what `document_entities` retains about the origin of each value — BERT output, post-processed output, processing status, and the model/prompt version that produced the change.
- `entity-quality-eval`: the entity-level evaluation harness, its fixture, its metrics (including hallucination rate), and the gate that a post-processing configuration must pass before it may be offered as a mode.

### Modified Capabilities

- `model-serving`: inference confidence SHALL be a calibrated probability in `[0, 1]` on both the ONNX and base-model paths, replacing the raw max-logit score.
- `entity-normalization`: `canonicalize()` SHALL remove Unicode format characters and fold typographic punctuation; BIO reconstruction SHALL permit a bounded same-page gap in an `I-` continuation; spans SHALL be punctuation-trimmed with offsets adjusted; invalid entities SHALL be rejected before persistence; intra-document duplicates SHALL collapse under a defined policy.
- `structured-entity-values`: numeric parsing SHALL handle a leading numeral followed by trailing words.
- `extraction-service`: batch extraction SHALL accept and enforce a server-validated processing mode, and the run SHALL record the mode used and the post-processor version.
- `tenant-schema-migrations`: `document_entities` gains provenance columns; `extraction_runs` gains processing-mode columns.
- `portal-extraction-page`: the Batch Extraction request SHALL carry a processing mode (backend contract only; UI deferred).

## Impact

**Code**
- `src/model_serving/services/inference_service.py` — softmax calibration, both paths
- `src/extraction_service/services/entity_normalizer.py` — `canonicalize`, `_is_adjacent`, span trimming, validity gate
- `src/extraction_service/services/semantic_normalizer.py` — `_read_number`
- `src/extraction_service/services/document_entity_store.py` — provenance columns, dedup policy
- `src/extraction_service/services/entity_postprocessor.py` — **new**
- `src/extraction_service/worker.py` — post-processing stage, mode enforcement, degraded status
- `src/extraction_service/api/v1/extraction.py`, `schemas.py` — mode in the batch request
- `src/shared/config.py` — post-processor settings (model, thresholds, timeout, budget)
- `alembic/versions/` — two migrations (`document_entities` provenance, `extraction_runs` mode)
- `src/shared/retrieval/eval/` — structured-query success metric
- `tests/` — normalization, reconstruction, post-processor contract, fail-open, migration, eval harness

**APIs**
- `POST /api/v1/extract-batch` — **BREAKING**, gains a request body
- `GET /api/v1/extract-batch/{run_id}` and the list endpoint — additive mode/status fields

**Dependencies**
- Azure OpenAI via the existing `openai` client and `settings.azure_openai_chat_deployment` (`gpt-4o-mini`). The extraction worker gains an outbound LLM dependency it does not have today.

**Data**
- Existing 364 rows keep uncalibrated logit confidences and no provenance. Backfill is out of scope; re-extraction under the new pipeline is the path forward. No silent reprocessing.

**Downstream**
- `chat_api.entity_resolver` and `sql_generator` read `document_entities` directly. Dedup and punctuation trimming change row counts and values; the SQL prompt's description of `normalized_value` must stay accurate.

## Open Questions

1. **Dedup semantics.** Collapsing to one row per `(document_id, entity_type, normalized_value)` improves counting but discards per-mention spans and page numbers. Assumed resolution: collapse with an occurrence count and retain the first span; revisit if citation quality regresses.
2. **Provenance shape.** Additive nullable columns on `document_entities` versus a sidecar table. Assumed: additive columns, since no existing reader breaks and the query surface stays one table. Design must confirm the column set is minimal.
3. **Candidate threshold.** Calibrated-probability cutoff for routing an entity to the LLM is unknown until softmax lands — today's logit p10 (4.29) is not transferable. Assumed: threshold is a setting, tuned against the eval fixture, not hard-coded.
4. **Cost ceiling.** Per-run token budget and its behaviour on exhaustion (degrade to BERT-only mid-run vs fail the run) is unresolved. Assumed: degrade, and record it.
5. **Entity-type correction scope.** Whether the LLM may change `entity_type` at all, and if so whether only within the tenant's configured `entity_definitions`. Assumed: conditionally allowed, constrained to the configured set, never inventing a type.
6. **Merge across candidates.** Merging requires the post-processor to see neighbouring entities, widening its input and its blast radius. Assumed: allowed only for same-type, same-page, gap-bounded neighbours.
7. **Fixture labelling effort.** The eval fixture needs human-labelled ground truth over real tenant documents. Owner and volume unconfirmed; this is the largest non-code cost in the change.
8. **Interaction with in-flight changes.** `normalized-entity-store` and `structured-entity-value-normalization` are not archived, so their capabilities are still change-local. Ordering assumed: this change lands after both.
