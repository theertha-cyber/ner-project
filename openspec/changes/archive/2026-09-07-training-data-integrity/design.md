## Context

`GET /api/v1/annotation-export` in `src/annotation_service/api/v1/export.py` converts a tenant's confirmed spans into HuggingFace-format JSONL that `src/training_service/worker.py` consumes to fine-tune a per-tenant model. Three defects in that path corrupt or discard training data:

- The inline offset walk in `export_annotations` (and the equivalent in `_bio_tags`) computes each token's character offsets by adding token length and then skipping exactly one `" "`. `_tokenize` is `text_val.split()`, which splits on any whitespace run. Any newline, tab, or repeated space therefore desynchronises the walk permanently. Verified: for `"John Doe\nworks at Acme Corp"`, token `"Acme"` computes to offsets (15,19), which is the substring `"at A"`. Because documents are OCR'd through Tesseract, multi-line text is the normal case.
- Each document produces exactly one JSONL record (`lines.append(...)` inside `for d_id in doc_ids`), and the existing `annotation-workspace` spec asserts this ("there SHALL be 3 lines (one per document)").
- `worker.py` tokenises with `truncation=True, padding="max_length", max_length=max_seq_length`, where `max_seq_length` defaults to 128. A one-record-per-document dataset is therefore cut to roughly the first 90 source words.

The three compound: a long document becomes one row, that row is truncated, and whatever survives is mislabelled. No model trained on this platform to date has seen correctly aligned, complete training data.

`imported_annotations` rows bypass all of this — they are emitted directly as pre-tokenised `{tokens, tags}` and are already row-sized.

## Goals / Non-Goals

**Goals:**
- BIO tags align to the correct tokens for text containing any whitespace form.
- A long document contributes all of its annotated content to training, not just its opening.
- The dataset has enough rows for a meaningful train/evaluation split.
- No stored data changes and no migration is required.

**Non-Goals:**
- No change to the export API path, query parameters, or the per-record `{tokens, tags}` shape — `worker.py`'s consumption contract is untouched.
- No new dataset-readiness threshold. ADR-010 owns that; see Decision 4.
- No automatic invalidation or retraining of existing model versions (see Decision 5).
- No re-windowing of `imported_annotations` passthrough rows.
- Nothing from changes 1, 2, 4, 5 or 6. This change is independent and can land in parallel with 1 and 2.

## Currently-In-Force ADRs

| ADR | Decision Summary | Constraint on This Design |
|-----|-----------------|--------------------------|
| ADR-010-per-entity-type-dataset-threshold | Dataset readiness is measured per entity type at 200 labeled entities per type, enforced via `NER_MIN_ENTITIES_PER_TYPE` (default 0, inert); `NER_MIN_TRAINING_ENTITIES` retains its total-count meaning | This change MUST NOT introduce a second, competing notion of "enough data". Any guard added here must be mechanically scoped to whether a train/test split can be formed, and must leave readiness judgement to ADR-010's per-type mechanism. |
| ADR-006-training-infrastructure | Async Celery GPU workers; training hyperparameters submitted with the job request (the hyperparameter clause is superseded by ADR-009) | `max_seq_length` remains a caller-supplied hyperparameter. This change may alter its default but MUST NOT remove the ability to set it per job. |
| ADR-009-system-admin-sets-training-hyperparameters | A System Admin sets training hyperparameters at approval time, not at job submission | Any change to the `max_seq_length` default must remain overridable through the existing approval-time hyperparameter path, not hardcoded in the worker. |
| ADR-001-tenant-data-isolation | Tenant isolation via separate PostgreSQL schemas | Unchanged by this design — export already resolves the tenant schema per request and this change does not alter that resolution. |

> ADR-010 explicitly records that its 200-per-type figure "is not empirically derived... It should be revisited once a model has trained against a per-type-balanced dataset." This change is a precondition for that revisit: until export produces correctly aligned, untruncated data, no such training run has been possible.

## Decisions

### Decision 1: Derive token offsets by scanning the source text, not by assuming separators

**Choice:** Replace the additive offset walk with one that locates each token's actual position in the source text — advancing a cursor past arbitrary whitespace rather than exactly one space character. Tokenisation and offset derivation become a single operation returning `(token, char_start, char_end)` triples.

**Rationale:** The defect exists because tokenisation (splits on any whitespace) and offset derivation (assumes one space) disagree about what a separator is. Producing both from one pass makes the disagreement structurally impossible rather than fixing one arithmetic bug and leaving the same assumption elsewhere.

**Alternatives considered:**
- Patch the advance to skip any whitespace run (`while text[i].isspace(): i += 1`) — this fixes the observed case, but keeps two independent notions of tokenisation that can drift apart again. Rejected as a narrower fix to a structural problem.
- Use a regex with `finditer` to yield tokens and spans together — acceptable and effectively equivalent; the requirement is one pass producing both, not a specific implementation.

### Decision 2: Span offsets are the source of truth; stop consuming the stored `bio_tags` column

**Choice:** Compute BIO tags in export purely from each span's `char_start`/`char_end` against corrected token offsets. Do not read the stored `bio_tags` column.

**Rationale:** This resolves the proposal's open question about `_compute_bio_tags` in `spans.py`. That function contains the same single-space assumption, so the stored column is itself derived from drifting offsets — and export currently *prefers* it when present, applying stored tags positionally against independently-computed token overlap. Two separately-drifting sources being reconciled positionally is unfixable by correcting one of them. The span's character offsets are what the annotator actually drew and are unaffected by the bug; deriving from them makes the corrupt cache irrelevant without requiring a data migration.

**Alternatives considered:**
- Fix `_compute_bio_tags` and keep using the stored column — rejected: it requires backfilling every existing `bio_tags` value to be trustworthy, which is a migration this change explicitly avoids. It also leaves a derived cache that must stay in sync with the offsets forever.
- Fix both and prefer stored tags only when freshly written — rejected as unnecessary complexity for a value that can be recomputed deterministically and cheaply.

> Consequence: the stored `bio_tags` column becomes unused by export. Whether `spans.py` should stop writing it, or whether another consumer depends on it, is recorded in Open Questions — this change does not remove the column or the write.

### Decision 3: Window at export time, with overlap, on a source-token budget

**Choice:** Export emits one record per bounded window of a document rather than one per document. Consecutive windows overlap. The window budget is expressed in source tokens and chosen such that a window's subword expansion fits within the training sequence length without truncation.

**Rationale:** Windowing at export keeps the fix in one place and leaves `worker.py`'s consumption contract identical — it still reads `{tokens, tags}` rows and needs no change to how it builds the Dataset. Overlap ensures an entity straddling a boundary appears complete in at least one window, so boundary entities are not systematically shredded into partial spans. Expressing the budget in source tokens (not subwords) keeps the export service independent of the training tokeniser, with the safety margin handled by the sizing rule rather than by export importing a tokeniser.

**Alternatives considered:**
- Window inside `worker.py` at tokenisation time using `return_overflowing_tokens` — keeps export simple and is tokeniser-exact, but leaves the export endpoint emitting documents too large for any consumer and pushes label realignment into the training path. Rejected: the export format is the shared contract, and it should be the thing that is correct.
- Split on sentence boundaries instead of a token budget — more linguistically natural, but requires a sentence segmenter that behaves acceptably on OCR output with broken line endings. Rejected for v1 as adding a dependency and a new failure mode to a bug-fix change; the budget approach is deterministic.
- Window without overlap — rejected: an entity crossing a boundary would be truncated in both windows, manufacturing exactly the kind of partial label this change exists to eliminate.

### Decision 4: The dataset guard is mechanical, not a readiness threshold

**Choice:** The worker fails a job with a clear error only when the dataset cannot form a valid train/evaluation split (an evaluation partition of zero rows). It does not judge whether the data is sufficient to train a *good* model.

**Rationale:** ADR-010 owns dataset readiness, measured per entity type at 200 per type via `NER_MIN_ENTITIES_PER_TYPE`. Adding a row-count sufficiency threshold here would create a second, competing definition of "enough data" — precisely the disagreement ADR-010 was written to resolve. The guard added here addresses a different, mechanical failure: `train_test_split(test_size=0.1)` on a very small row count yields an empty evaluation set and a metric computed over nothing.

**Alternatives considered:**
- Add a minimum row count (e.g. 50 rows) — rejected: that is a readiness judgement wearing a mechanical disguise, and it would conflict with ADR-010.
- Leave the split unguarded — rejected: an empty evaluation partition produces a meaningless metric that is reported as if it were real, which is the same class of silent-wrongness this change exists to remove.

### Decision 5: Do not auto-invalidate models trained before this fix

**Choice:** Existing model versions are left in place and are not automatically flagged, retired, or retrained.

**Rationale:** Retraining is a human decision — that is the explicit position change 6 takes for the retraining loop, and it should hold here too. Automatically invalidating a tenant's deployed model because a training-data defect was found would be a destructive action taken on the tenant's behalf.

**Alternatives considered:**
- Automatically mark affected model versions as stale in the registry — rejected as taking a consequential action without the tenant asking; deferred to Open Questions as a visibility question rather than an automatic behaviour.
- Silently do nothing and say nothing — rejected: metrics from pre-fix runs are not comparable to post-fix runs, and leaving that unsaid is misleading.

## Risks / Trade-offs

- [Windowing changes the row count of every tenant's dataset, so post-fix training metrics are not comparable to pre-fix ones] → Expected and correct — pre-fix metrics were computed on truncated, mislabelled data. Call it out explicitly at rollout so a metric shift is not misread as a regression.
- [An entity longer than the overlap could still be split across windows] → Size the overlap against the longest entity observed in real tenant data rather than a guessed constant, and treat "entity longer than overlap" as a condition worth logging rather than silently accepting.
- [Deriving tags from offsets instead of the stored column changes output for spans whose stored tags happened to be correct] → This is the intended correction; the deterministic recomputation is the authority. Existing export tests asserting stored-tag behaviour must be reviewed rather than assumed still valid.
- [Raising `max_seq_length` increases GPU memory per batch and may affect training throughput] → It remains a caller-supplied hyperparameter per ADR-006/ADR-009, so it stays tunable at approval time; only the default moves.
- [`_compute_bio_tags` in `spans.py` retains the same defect even after this change] → Made harmless for training by Decision 2, but the column keeps accumulating incorrect values. Flagged in Open Questions rather than silently left.

## Migration Plan

1. Land the offset-derivation fix (Decision 1) and the switch to offset-derived tags (Decision 2) together — these are correctness fixes with no format change, and can be verified against existing export tests plus new whitespace cases.
2. Land windowing (Decision 3) and the `max_seq_length` default change together, since the window budget and the sequence length must be sized consistently with one another.
3. Land the split guard (Decision 4).
4. No data migration. No stored table changes. Rollback is a code revert; because nothing persisted changes shape, a revert restores prior behaviour exactly (including its defects).
5. At rollout, notify tenants with existing trained models that pre-fix metrics are not comparable and that retraining is advisable — a human decision, not an automatic one (Decision 5).

## Open Questions

- **Concrete window size and overlap values.** Must satisfy: a window's subword expansion fits the sequence length without truncation, and overlap ≥ the longest plausible entity. Both should be measured against real tenant documents during implementation rather than fixed here.
- **Should `spans.py` stop writing the `bio_tags` column?** After Decision 2 nothing in export reads it. Before removing the write, confirm no other consumer (extraction, analytics, the annotation UI) depends on it. If nothing does, removing the write — and eventually the column — is a follow-up change, not this one.
- **Should model versions trained before this fix be surfaced as such in the model registry?** Decision 5 rules out automatic action; whether to add a visible marker so a tenant admin can make an informed retraining decision is a product question for change 6's human-gated retraining surface.
- **Does this change satisfy ADR-010's stated revisit condition?** ADR-010 notes its 200-per-type figure should be revisited "once a model has trained against a per-type-balanced dataset". This change makes that training possible for the first time. Whether the revisit is warranted is a separate decision and would need its own superseding ADR — flagged here, not resolved.
