## Context

The extraction path today is: `document_text_spans` → `worker._tokenize_span` (whitespace) → `POST /internal/v1/infer` (ONNX, sliding-window) → `_align_predictions_with_offsets` → `merge_wordpieces` → `reconstruct_entities` (BIO) → `apply_semantic_normalization` (typed values) → `insert_document_entities` → `document_entities`. Downstream, `chat_api.sql_generator` writes SQL against that table and `chat_api.entity_resolver` resolves person mentions from it.

The forensic pass recorded in `proposal.md` establishes the constraint that shapes this design: **most of the measured damage happens after BERT, in deterministic code**. One entity that BERT tagged correctly (`B-YEARS_OF_EXP two`, `I- half`, `I- years`) was split by an adjacency guard into `2.0` and `0.5` years — while the normalizer, given the whole span, returns `2.5`. Seventy-one percent of `software engineer` rows are unreachable by SQL equality because of a zero-width space that `canonicalize` does not strip. Half of all rows carry trailing punctuation that arrives from whitespace tokenization, not from the model.

The remaining damage is genuinely BERT's: person names typed `COMPANY`, `JAVA` typed `DEGREE`, a passport number typed `PHONE_NUMBER`, and missing `NAME` rows on half the extracted corpus. That residue is what an LLM post-processor can plausibly address — and only that residue.

A second constraint governs the routing design. `inference_service.py:191` emits `np.max(logits, axis=-1)` with no softmax, so `document_entities.confidence` holds raw logits (2.85–7.44, mean 5.63). The base-model fallback path emits a real probability. Any "send low-confidence entities to the LLM" rule is unimplementable until those two paths agree on a scale.

**Stakeholders:** Business Users trigger extraction and consume chat answers; Tenant Admins own entity-type configuration; the platform owner carries the token cost of any per-entity LLM call.

## Goals / Non-Goals

**Goals:**

- Make `normalized_value` reliably matchable by SQL equality, so structured retrieval stops silently under-returning.
- Make typed values (`value_number`, `value_date`) reflect the entity the document actually states.
- Repair the deterministic defects with deterministic code, at zero token cost.
- Add an optional, off-by-default LLM post-processing stage that addresses BERT's residual type and boundary errors under a strict, validated contract.
- Preserve, for every row, what BERT produced and what post-processing changed.
- Let a Business User choose the processing mode per run, enforced server-side and recorded on the run.
- Prove the value of post-processing with entity-level and downstream-retrieval metrics, including a hallucination rate.

**Non-Goals:**

- Improving BERT recall. Missing `NAME` rows are a training-data problem; nothing in this change re-reads a document to find entities BERT missed.
- Replacing BERT with LLM extraction. The LLM never sees a document without a BERT candidate anchoring it.
- Backfilling or rewriting the existing 364 rows.
- Any change to retrieval orchestration, SQL generation, context assembly, or chunking — those belong to `harden-chat-pipeline-correctness`.
- Implementing the Batch Extraction UI control. This change specifies its backend contract only.
- Document ingestion / OCR fixes, even though the zero-width space originates there.

## Currently-In-Force ADRs

Every ADR in `docs/adr/` was reviewed. Supersession graph: ADR-008 partially supersedes ADR-002 (default-model behaviour); ADR-009 partially supersedes ADR-006 (hyperparameter submission); ADR-010 partially supersedes ADR-006 (dataset thresholds). None of the superseded clauses touch this design. ADR-004, ADR-005, ADR-006, ADR-009, ADR-010 govern governance, agent boundaries, and training, and do not constrain extraction post-processing.

| ADR | Decision Summary | Constraint on This Design |
|-----|-----------------|--------------------------|
| ADR-001 Tenant Data Isolation (Proposed) | Schema-per-tenant; `search_path` injection via shared `tenant_context`; migrations applied to `public` and every tenant schema; zero cross-tenant leakage | The post-processor receives tenant scope from server-controlled context only, never from an LLM-influenced value. Both migrations must run against `tenant_template` and every existing tenant schema. No prompt may carry content from more than one tenant. |
| ADR-002 Base Model Strategy (Proposed, partly superseded by ADR-008) | Single curated base model, no BYOM | The post-processor is not a model registered for extraction and must not be promotable as one. It is a service dependency, not a model version. |
| ADR-003 Model Serving Topology (Proposed) | Extraction routes all inference through the Serving Layer internal endpoint; serving resolves the active version per request | The softmax fix belongs in `model_serving`, not in the worker. The worker must not post-process confidence to compensate; that would put scoring logic outside the serving layer. |
| ADR-007 Chatbot Architecture (Proposed) | Every response cites sources; generated SQL is validated; all interactions tenant-scoped; P95 latency monitored | Provenance must keep citations resolvable — dedup must not destroy the span a citation points at. Entity changes must not degrade the citation path. |
| ADR-008 Base Model as Default (Proposed) | Tenants without a promoted model fall back to the base model | The base-model path must emit the same calibrated confidence scale as the ONNX path, or a base-model tenant's entities route to the LLM at a different rate for no reason. |

## Decisions

### Decision 1: Calibrate confidence in `model_serving`, before anything else in this change

**Choice:** Replace `scores = np.max(logits, axis=-1)[0]` with a softmax over the label axis, taking the probability of the argmax label. Apply the same treatment so the ONNX path and the `_infer_with_base_model` pipeline path both emit `[0, 1]`. Do not rewrite existing `document_entities.confidence` values; instead stamp new rows with an extraction-schema marker, and let confidence-gated logic consider only marked rows.

**Rationale:** Every other decision here depends on a confidence number that means something. Today `settings.confidence_threshold = 0.50` filters nothing (0 of 364 rows are ≤ 1.0), the `/extract` playground's `confidence >= threshold` filter is dead code, and a "route suspicious entities to the LLM" rule has no scale to act on. ADR-003 puts scoring in the serving layer, so the fix goes there. In-place rewriting is rejected because a logit cannot be converted to a probability after the fact — the full logit vector is gone.

**Alternatives considered:**
- *Min-max normalize the logits in the worker.* Rejected: produces a number that looks like a probability and is not one, varies with corpus composition, and puts scoring outside the serving layer against ADR-003.
- *Rank-relative routing on raw logits (percentile within document).* Tempting — the four confirmed misclassifications all sit below the corpus p10 of 4.29 — but a per-document percentile always routes a fixed fraction of entities regardless of whether any are bad, and it cannot be compared across model versions. Rejected as the primary mechanism; retained as a **secondary** suspicion signal in Decision 4.
- *Defer calibration to a separate change.* Rejected: it would make the post-processor's candidate selection unspecifiable, which is the core of the contract.

### Decision 2: Deterministic repairs land as a distinct, LLM-free group, and land first

**Choice:** Four repairs in `entity_normalizer.py` / `semantic_normalizer.py`, sequenced ahead of any LLM work:

1. `canonicalize()` strips Unicode general-category `Cf` characters (U+200B, U+FEFF, U+200E, …) and folds typographic punctuation (U+2019→`'`, U+2018→`'`, U+201C/U+201D→`"`, U+2013/U+2014→`-`) **before** casefold and whitespace collapse.
2. `_is_adjacent` accepts an `I-` continuation when the gap is on the same page and `current_index - prev_index <= max_entity_word_gap` (default 2), instead of requiring exactly `+1`.
3. Span punctuation is trimmed from both ends of the reconstructed value **with `char_start`/`char_end` moved by the number of characters removed**, so offsets keep naming the text they point at.
4. `_read_number` gains a leading-numeral-with-trailing-words branch, so `"2 years of experience"` parses like `"2+ years of experience"` already does.

**Rationale:** These are the highest-yield fixes in the change and cost nothing per document. Repair 1 alone recovers 5 of 7 `software engineer` rows for equality matching. Repair 2 alone turns `2.0 + 0.5` back into the `2.5` the normalizer already computes correctly for the whole phrase. Repair 4 is a four-line branch. Doing LLM work before these would spend tokens fixing bugs and then measure the LLM's contribution against a broken baseline — the evaluation in Decision 9 would be meaningless.

**Alternatives considered:**
- *Have the LLM fix punctuation and whitespace.* Rejected on cost and determinism: a model call to remove a zero-width space is strictly worse than `unicodedata.category(c) == 'Cf'`, and it introduces variance into a value that indexes a B-tree.
- *Fix tokenization instead of trimming spans* — i.e. make `_tokenize_span` split punctuation off words. Rejected for this change: it changes the token stream the model sees, which invalidates the model's training-time tokenization assumptions and would require re-validating extraction quality end to end. Trimming after reconstruction gets the same stored value without touching inference. Flagged in Open Questions as the better long-term fix.
- *Widen `_is_adjacent` without a page bound.* Rejected: the guard exists because model serving filters `O` predictions, so two labelled words pages apart arrive adjacent in the list. An unbounded gap reintroduces exactly that bug.

### Decision 3: A validity gate and an explicit duplicate policy, at the persistence boundary

**Choice:** Before `insert_document_entities`, drop entities whose canonical value is empty, punctuation-only, or shorter than `min_entity_value_length` (default 2 characters, excluding types configured as short-code-bearing). Separately, collapse rows identical on `(document_id, entity_type, normalized_value)` into one row carrying `occurrence_count` and the **first** span's `page_number` / `char_start` / `char_end`.

**Rationale:** Two rows currently hold `normalized_value = ''` (from `entity_value = ','`) and 16 hold values of ≤ 2 characters — these are not facts, and `NOT NULL` does not catch an empty string. On duplication: 364 rows collapse to 289 distinct triples; `node.js` appears 8 times in one document. `COUNT(*)` over `document_entities` currently reads repetition as evidence weight, which ranks a document that says "React" six times above one that says it once. Keeping `occurrence_count` preserves the signal without letting it distort counting. Keeping the first span keeps ADR-007's citation path resolvable.

**Alternatives considered:**
- *Deduplicate at query time in `sql_generator`.* Rejected: it makes every downstream consumer responsible for remembering `DISTINCT`, and the generation model has already been observed omitting it.
- *Keep every mention and add a `UNIQUE` view.* Rejected as more surface for the same result; the row-per-mention data is not used by any current reader.
- *Drop duplicates entirely with no count.* Rejected: mention frequency is genuinely useful for ranking and is cheap to keep.

### Decision 4: Post-process **selected candidates only**, never every entity — Option B

**Choice:** Route an entity to the LLM only if it trips at least one selection rule:

- calibrated `confidence < postprocess_confidence_threshold` (a setting, tuned on the eval fixture — not hard-coded), **or**
- its declared `value_kind` is non-`text` and semantic normalization produced no typed value (the `unparseable_count` path already counted in `worker.py:253`), **or**
- it is a single-token entity of a type that is typically multi-token for this tenant (`NAME`, `COMPANY`, `INSTITUTION`, `ADDRESS`), **or**
- it sits within `max_entity_word_gap` of a same-type neighbour on the same page (a merge candidate).

Candidates are batched per document into one request with a bounded window of surrounding document text as evidence.

**Rationale:** The proposal asked for this to be decided on measured data, not assumed. The data says option B. On the live tenant, 364 rows across 8 documents produced 4 confirmed type errors, 1 split entity, and ~16 junk rows — call it 6% genuinely suspicious once Decision 2 removes the punctuation and Unicode noise. Sending all 364 costs ~16× more than sending the suspicious ones for the same achievable gain, and it puts 94% of correct extractions at risk of being "improved" by a model that has no reason to touch them. The counting matters at scale: `tenant_demo_tenant` holds 1,910 documents.

The confirmed misclassifications (`HANNAH`, `VISHNU`, `AJAYDEV`, `JAVA`, logits 3.10–4.18) all fall below the corpus p10 of 4.29, so confidence-based selection demonstrably catches the errors this stage exists to fix — once Decision 1 makes the number a probability. Until it does, the other three rules are structural and work on any scale.

**Alternatives considered:**
- *Option A — post-process every entity.* Rejected on the numbers above, plus latency: batch runs process documents serially in a Celery task with no per-document parallelism, so a per-entity call multiplies wall-clock time by the entity count.
- *Whole-document LLM pass alongside BERT.* Rejected by the user's stated constraint and by the no-invention rule — a whole-document pass has no BERT anchor to validate an emitted entity against.
- *Confidence-only selection.* Rejected: it would have missed the split `two` / `half years` entity entirely, whose tokens scored 4.55 and 4.08–5.92 — around and above the median.

### Decision 5: An explicit permitted-transformation contract, classified per operation

**Choice:** The post-processor may emit exactly four decisions — `keep`, `modify`, `merge`, `reject` — and each permitted transformation is classified:

| Operation | Classification | Why |
|---|---|---|
| Merge adjacent same-type fragments | **Conditionally allowed** | Only for same `entity_type`, same `page_number`, gap ≤ `max_entity_word_gap`, and the merged value must be a contiguous substring of the source text between the two spans. This is the `two … half years` case. Unbounded merging re-creates the cross-page stitching bug. |
| Normalize punctuation / whitespace / casing | **Not allowed** | Decision 2 does this deterministically and identically every time. An LLM doing it adds cost and variance to a B-tree-indexed column. |
| Repair a malformed span (trim/extend boundaries) | **Conditionally allowed** | Only within the enclosing sentence, and the result must be a substring of the source text. Extension beyond the sentence is how a boundary repair becomes an invention. |
| Correct `entity_type` | **Conditionally allowed** | Only to a type present in this tenant's `public.entity_definitions`. This is the `B-COMPANY HANNAH` / `B-DEGREE JAVA` case — the single largest thing only the LLM can fix. Never to a type the tenant has not configured. |
| Reject an invalid artifact | **Allowed** | Complements the deterministic gate for cases with no rule — `PHONE_NUMBER Z5060835` (a passport number), `ADDRESS github.com/definitelyarjun`. A rejection removes a row; it cannot fabricate one. |
| Convert to a typed representation (`value_number`, `value_date`) | **Not allowed** | The LLM may correct the *value text*; `semantic_normalizer` then re-derives typed fields deterministically from the corrected text. Letting the model emit `value_number` directly means an unverifiable number in an indexed numeric column. |
| Canonicalize surface variants (`ReactJS` → `react`) | **Not allowed** in this change | Belongs to `ALIAS_MAP` / a future alias-learning path. An LLM canonicalizing per-document produces inconsistent canonical forms across documents, which is worse for SQL equality than no canonicalization. |
| Emit a new entity not anchored to a BERT candidate | **Not allowed** | The invention boundary. Non-negotiable. |
| Preserve original span text alongside the processed value | **Required** | Decision 7. |

**Rationale:** The proposal's central requirement is a hard line between evidence-supported correction and model invention. The line is drawn structurally: every `modify` and `merge` result is **mechanically verified against the source text** before persistence, not trusted because the model asserted it. Operations the deterministic layer already handles are closed off so the two layers cannot disagree.

**Alternatives considered:**
- *Allow everything and rely on prompt instructions.* Rejected: enforcement would depend on model compliance. `harden-chat-pipeline-correctness` already recorded that lesson — it replaced a natural-language document-scope instruction with a structural filter for exactly this reason.
- *Allow typed-value emission.* Rejected as above; it puts unverifiable numbers behind a partial index used for filtering.

### Decision 6: A strict structured output contract, validated before persistence

**Choice:** The post-processor returns one object per input candidate, keyed by a request-scoped `candidate_id` the server assigns (never a database id). Shape:

```
{ candidate_id, decision: keep|modify|reject|merge,
  value: string|null,            # required for modify/merge
  entity_type: string|null,      # optional; must exist in entity_definitions
  merge_with: [candidate_id],    # required for merge
  evidence_offset: int|null,     # start offset in the supplied text window
  reason: string }               # bounded length, diagnostic only
```

Validation, all server-side, all before any write:

1. Response parses as JSON matching the schema. Malformed → whole batch discarded, all candidates persist as BERT emitted them.
2. Every `candidate_id` belongs to this request. Unknown ids → that item discarded.
3. `value` for `modify`/`merge` is a substring of the supplied text window after the same `canonicalize` folding — the **no-invention check**.
4. `entity_type` is in this tenant's `entity_definitions`.
5. `merge_with` targets are same-type, same-page, within the gap bound.
6. Per-item failure discards **that item only**; the corresponding BERT row persists unchanged.

The value then flows through the *existing* `canonicalize` and `apply_semantic_normalization` before insert — the post-processor never writes to `document_entities` directly.

**Rationale:** "Invalid LLM output must never be written directly to the database" is a structural property, not a prompt instruction. Routing the accepted value back through the deterministic normalizers means the LLM cannot bypass the tenant's `value_kind` configuration or produce a `normalized_value` inconsistent with every other row. Assigning `candidate_id` server-side means a model that hallucinates an id addresses nothing.

**Alternatives considered:**
- *Free-form JSON with post-hoc repair.* Rejected: repair logic becomes a second, untested parser.
- *Let the model return the full `NormalizedEntity`.* Rejected: it hands the model fields (`document_id`, offsets, typed values) that must stay server-derived.
- *Provider structured-output / function-calling mode.* Adopted as a **transport** where the deployment supports it, but never as a substitute for the six validation steps — schema conformance is not evidence support.

### Decision 7: Provenance as additive nullable columns on `document_entities`

**Choice:** Add the minimum set that answers both required questions:

| Column | Purpose |
|---|---|
| `source_entity_value` | BERT's original surface value. NULL when unchanged. |
| `source_entity_type` | BERT's original type. NULL when unchanged. |
| `postprocess_status` | `not_applied` \| `kept` \| `modified` \| `merged` \| `rejected_logged` \| `failed` |
| `postprocess_model` | Provider deployment identifier actually used |
| `postprocess_prompt_version` | Prompt template version |
| `postprocess_at` | Timestamp |
| `extraction_schema_version` | Marks rows produced by the calibrated/repaired pipeline (Decision 1) |
| `occurrence_count` | Decision 3 |

**Rationale:** The existing schema cannot answer "what did BERT extract?" at all — `insert_document_entities` writes one value per field with no history. A sidecar table was the obvious alternative and is rejected: `sql_generator`'s whitelist and prompt describe one entity table, and adding a second either widens that surface or hides provenance from the tool that most needs it. Nullable additive columns break no existing reader — `SELECT` lists in `entity_resolver` and `sql_generator` are explicit, never `SELECT *`. Storing originals only when changed keeps the table from doubling for the 94% of rows post-processing never touches. `postprocess_prompt_version` is what makes a quality regression traceable to a prompt edit rather than to the model.

**Alternatives considered:**
- *Sidecar `document_entity_revisions` table.* Rejected above; revisit if provenance ever needs to be multi-step.
- *A single JSONB `provenance` column.* Rejected: not indexable for the obvious operational question ("show me everything the LLM changed in this run") without a GIN index that costs more than six scalar columns.
- *No provenance, rely on `extracted_entities` for raw output.* Rejected: `extracted_entities` stores per-token predictions, not reconstructed entities, so it cannot answer what BERT's *entity* was.

### Decision 8: Fail-open, per-batch, with the degradation recorded

**Choice:**

| Failure | Behaviour |
|---|---|
| Timeout (`postprocess_timeout_seconds`) | Persist BERT rows; mark `postprocess_status = 'failed'`; continue the document |
| Provider/API error | One retry with backoff, then as above |
| Rate limit (429) | Respect `Retry-After` within the run's remaining budget, then as above |
| Malformed / unparseable response | Discard the whole batch; persist BERT rows; mark `failed` |
| Individual invalid item | Discard that item only; persist that BERT row unchanged; other items proceed |
| Token budget exhausted mid-run | Remaining documents process BERT-only; run completes with a degraded marker |

The **run** completes as `completed` with a degraded indicator, not as `failed`. Nothing about a post-processing failure destroys a successful BERT extraction.

**Rationale:** The proposal offered this policy and asked whether it is right for this architecture. It is, for a specific reason: post-processing is opt-in per run and touches only ~6% of rows, so a failure costs a small quality improvement, not the extraction. Failing the run instead would make an optional enhancement a new single point of failure for a Business User's whole batch — and `run_batch_extraction` is declared `max_retries=0`, so a failed run is not automatically retried. The one thing that must **not** be fail-open is validation: an invalid item is discarded, never persisted on the theory that some data beats none.

**Alternatives considered:**
- *Fail the run so the user knows.* Rejected as above; the degraded marker plus per-row `postprocess_status = 'failed'` carries the same information without discarding good work.
- *Queue failures for later reprocessing.* Rejected as scope: it needs a reprocessing job, an idempotency story, and a UI. The provenance columns leave the door open.

### Decision 9: Evaluate at the entity level and at the retrieval level, with hallucination as a gate

**Choice:** Two harnesses.

*Entity level* — a fixture of labelled `(document, expected entities)` drawn from real tenant documents, deliberately covering every failure class observed: correct extractions that must survive, type errors (`HANNAH`/`JAVA`), fragmented spans (`two` / `half years`), malformed values (trailing punctuation, U+200B), duplicates, durations and numerics, dates, organization and person names, multi-token entities. Metrics: precision, recall, F1, exact-value accuracy, entity-type accuracy, and **hallucination rate** — entities emitted with no substring support in the source, and entities present after post-processing that were absent from BERT's output.

*Retrieval level* — extend `src/shared/retrieval/eval/` with **structured-query success rate**: for a golden query whose answer requires `document_entities`, did the generated SQL return the expected rows? The existing golden set already carries `simple_structured`, `exact_entity_lookup`, and `attribute_filtering` query classes, so the classes exist; the metric does not.

Three configurations are compared on both: **BERT-only (today)**, **BERT + deterministic repairs**, **BERT + repairs + post-processing**. The middle configuration is the one that matters — it is what isolates the LLM's actual contribution from the repairs'.

**Gate:** a post-processing configuration may be offered as a mode only if hallucination rate is **zero** on the fixture and structured-query success rate does not regress. F1 improvement alone is not sufficient.

**Rationale:** The proposal's stated objective is reliability of the structured representation, not prettier values, and it explicitly warns about improving normalization while introducing false positives. A zero-hallucination gate encodes that: the no-invention rule in Decision 6 is a mechanism, and this is its acceptance test. Three configurations rather than two prevents the deterministic repairs' gains from being credited to the LLM — with only two arms, Decision 2's fixes would inflate the post-processor's apparent value substantially.

**Alternatives considered:**
- *Retrieval-level evaluation only.* Rejected: it cannot attribute a change to extraction versus SQL generation, which is the confusion this whole change exists to resolve.
- *Two-arm comparison.* Rejected as above.
- *LLM-as-judge on entity quality.* Rejected: it evaluates the post-processor with the same class of model that produced the output, on a task where substring support is mechanically checkable.

### Decision 10: Processing mode is a server-validated request field, recorded on the run

**Choice:** `POST /api/v1/extract-batch` gains a request body with `processing_mode: "bert_only" | "bert_llm_postprocess"`, defaulting to `bert_only` when absent. **BREAKING** — the endpoint takes only a `documentIds` query parameter today. `documentIds` moves into the body, with the query parameter retained for one release. The mode is validated against the enum and against whether post-processing is configured for the deployment; an unconfigured tenant requesting `bert_llm_postprocess` gets `422`, not a silent downgrade. The worker receives the mode as a task argument and enforces it — it does not re-read a tenant setting.

`extraction_runs` gains `processing_mode`, `postprocess_model`, `postprocess_prompt_version`, and a degraded indicator, surfaced additively on `BatchRunStatus` / `BatchRunListItem`.

The skip logic in `worker.run_batch_extraction` (`get_already_extracted` against `model_version`) is **unchanged**: a document already extracted under the active model version is skipped regardless of mode. Switching the UI toggle reprocesses nothing.

**Rationale:** "Must not rely solely on client-side state" means the mode travels with the request and is enforced by the worker. Passing it as a task argument rather than having the worker read a setting means the run's behaviour is fixed at enqueue time — a setting changed mid-run cannot alter what a queued run does, and the recorded `processing_mode` is then truthful. Default `bert_only` is chosen because post-processing costs tokens, adds an external dependency, and has not yet passed the Decision 9 gate; a default that silently spends money is the wrong default. Leaving skip logic alone satisfies "existing extraction results must not be silently reprocessed" without any new code.

**Alternatives considered:**
- *Default to `bert_llm_postprocess`.* Rejected: unmeasured quality, unbudgeted cost, and it makes an external provider a dependency of the default path.
- *Tenant-level setting instead of per-run.* Rejected: the proposal asks for a per-run choice, and per-run makes A/B comparison possible without a settings change.
- *Add mode as a second query parameter.* Rejected: the parameter list is already carrying a comma-joined id list, which is at its limit; a body is the right shape and the migration cost is one release.

### Decision 11: The post-processor is a tenant-scoped, server-controlled client in the extraction worker

**Choice:** A new `src/extraction_service/services/entity_postprocessor.py` builds the Azure OpenAI client the same way `chat_api` does (`settings.azure_openai_endpoint` + `settings.azure_openai_chat_deployment`, default `gpt-4o-mini`). Tenant scope, schema, and document identity are derived from the worker's own context and are never present in, or influenced by, the model's output. A prompt carries text from exactly one document of one tenant. The document text window is bounded by `postprocess_context_chars`.

**Rationale:** ADR-001 requires tenant isolation with no leakage, and the post-processor is a new place where content could cross a boundary. Building the prompt from one document at a time makes cross-tenant contamination structurally impossible rather than policy-dependent. `gpt-4o-mini` is the deployment the platform already provisions, already pays for, and already uses for SQL generation — introducing a second model would add a dependency for no measured benefit. Model and prompt version are recorded per row (Decision 7), so switching later is traceable.

**Alternatives considered:**
- *A separate post-processing microservice.* Rejected as premature: the work is a single stage in an existing Celery task, and a new service adds deployment, auth, and network surface for no functional gain.
- *A larger model.* Rejected until the eval fixture shows `gpt-4o-mini` is the limiting factor. The metrics in Decision 9 make that a measurable question rather than a guess.
- *Reuse `chat_api`'s client via an HTTP call.* Rejected: it makes extraction depend on the chat service's availability and rate limits.

## Risks / Trade-offs

- **The LLM "corrects" an entity BERT got right.** → Selection routes only suspicious candidates (Decision 4), `keep` is a first-class decision, every `modify` is substring-verified (Decision 6), and the eval fixture deliberately includes correct extractions that must survive unchanged (Decision 9).
- **Hallucinated entities enter structured data.** → No emission without a BERT anchor; mechanical substring verification; zero-hallucination release gate. This is the risk the change is most explicitly defended against.
- **Deterministic repairs change values downstream consumers already match against.** → `entity_resolver` matches on `normalized_value` word overlap and `sql_generator` prompts describe `normalized_value` as lowercased and punctuation-stripped. Trimming makes stored values *more* consistent with that description, not less; the SQL prompt description must be re-read against the new behaviour and the `chat_api` SQL tests re-run.
- **Dedup breaks a citation.** → Retain the first span's page and offsets; verify citation resolution in the eval run (ADR-007 requires at least one citation per response).
- **Widening `_is_adjacent` re-introduces cross-page stitching.** → Gap bound plus same-page requirement; a regression test asserting that two same-type words on different pages never merge.
- **Latency on large batches.** → Per-document batching rather than per-entity calls, a bounded timeout, and a run-level token budget that degrades to BERT-only rather than stalling. Post-processing is off by default, so the baseline path is unaffected.
- **Cost is unbounded across tenants.** → Per-run token budget with recorded degradation; `tenant_demo_tenant`'s 1,910 documents are the scale case to budget against.
- **Calibration invalidates existing confidence data.** → No backfill; `extraction_schema_version` marks calibrated rows; confidence-gated logic ignores unmarked rows.
- **Fixture labelling is the critical-path cost.** → Scope the first fixture to the 8 documents already extracted plus a targeted sample, sized to cover each failure class rather than to be statistically large.
- **`gpt-4o-mini` may be too weak for type correction.** → Measurable via entity-type accuracy in Decision 9; the model is a setting, and provenance records which one ran.

## Migration Plan

1. **Calibration** — softmax in `model_serving`, both paths. Deploy independently; no schema change. Verify `/extract` returns `[0,1]` and that `settings.confidence_threshold` now filters as documented.
2. **Migration A** — `document_entities`: provenance columns, `occurrence_count`, `extraction_schema_version`. All nullable/defaulted, applied to `tenant_template` and every tenant schema per ADR-001. Rollback: drop columns; no reader depends on them yet.
3. **Deterministic repairs** — `canonicalize`, `_is_adjacent`, span trimming, `_read_number`, validity gate, dedup. Ship with tests reproducing each proposal defect from real values. Rollback: revert; existing rows untouched.
4. **Migration B** — `extraction_runs`: `processing_mode` (default `bert_only`), `postprocess_model`, `postprocess_prompt_version`, degraded indicator. Rollback: drop columns.
5. **Batch API contract** — request body with `processing_mode`; `documentIds` accepted in both places for one release; run records the mode. Rollback: revert; the default keeps old clients working.
6. **Post-processor** — `entity_postprocessor.py`, worker integration, config, fail-open paths. Reachable only via `bert_llm_postprocess`, so it is inert until requested. Rollback: reject the mode with `422`.
7. **Evaluation** — fixture, entity-level harness, structured-query success metric. Run all three configurations; record results in `verification.md`.
8. **Gate** — offer `bert_llm_postprocess` in the UI only after the Decision 9 gate passes. UI work is a separate change.

Steps 1–5 are independently valuable and independently revertible. If post-processing never passes its gate, steps 1–5 still deliver the measured majority of the quality gain.

## Open Questions

1. **Calibrated threshold value.** Unknown until softmax ships. Must be tuned against the fixture, not guessed. Blocks final tuning of Decision 4, not its structure.
2. ~~**`min_entity_value_length` and short-code types.**~~ **Resolved during implementation:** a per-type exemption, not a character-class rule. `settings.min_entity_value_length` defaults to 2 and `settings.entity_short_value_types` names the types whose values may be shorter (default `PROGRAMMING_LANGUAGE`, covering `C`, `R`, `Go`). A character rule was rejected because every candidate rule — all-uppercase, contains a digit, matches a known-acronym list — either admits the junk it is meant to exclude (`—`, a bare `,`) or excludes real values; "short and meaningful" is a property of the entity type, and the tenant already declares its types.
3. **Dedup and citation fidelity.** Whether collapsing loses a citation a user would have wanted. Measurable in the eval run; revisit if it regresses.
4. **Tokenization.** Splitting punctuation in `_tokenize_span` is the better long-term fix than trimming afterwards, but it changes the token stream the model sees and needs end-to-end quality re-validation. Deliberately deferred; worth its own change.
5. **Per-run token budget default.** Needs a measured cost-per-document from step 7 before a number can be set.
6. **Merge across page boundaries.** Currently forbidden. Whether a genuine entity ever spans a page break in this corpus is unmeasured.
7. **Backfill.** Existing 364 rows keep uncalibrated confidence and no provenance. Whether to offer an explicit re-extraction path (not a silent one) is unresolved.
8. **ADR revisitation.** None of the in-force ADRs need superseding. ADR-003 is *extended* in spirit — the serving layer now owns calibration explicitly rather than by implication — which the `adr` step may wish to record. ADR-001's isolation requirements gain a new surface (outbound LLM calls carrying tenant document text); if the platform later adopts a data-processing policy for external providers, that would warrant its own ADR.
