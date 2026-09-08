## Why

Three defects in the annotation-export → training path silently corrupt or discard training data today. They affect every tenant that has ever trained a model, independent of the LLM work in changes 1 and 2, and they must be fixed before change 4 attempts to train a usable model from a small seed corpus.

**1. BIO tag offsets desynchronise on any whitespace that is not a single space.** `_tokenize` in `export.py` uses `text_val.split()`, which splits on any whitespace run, but the offset walk that assigns tags only advances past a single `" "` character. After the first newline, tab, or double space, every subsequent token's computed character offsets drift and tags attach to the wrong tokens. Verified against `"John Doe\nworks at Acme Corp"`: the token `"Acme"` is computed at offsets (15,19), which is the substring `"at A"`. Because documents are OCR'd via Tesseract, multi-line text is the normal case, so this silently mislabels the majority of real annotations. This is the most severe of the three — it produces confidently wrong labels rather than missing ones.

**2. Export emits one JSONL record per document.** A tenant with 20 annotated documents produces a 20-row dataset. `worker.py` then applies `train_test_split(test_size=0.1)`, yielding an 18/2 split whose evaluation metric is statistical noise.

**3. Training truncates each record to 128 subword tokens and discards the remainder.** `max_seq_length` defaults to 128 with `truncation=True`. Combined with defect 2, a 600-word résumé becomes one record truncated to roughly the first 90 words — around 85% of the document, and every annotation within it, never reaches the model.

## What Changes

- Fix the offset walk in `export.py` so token character offsets are derived from the actual positions of tokens in the source text rather than by assuming single-space separators. Tags SHALL align correctly for text containing newlines, tabs, and repeated whitespace.
- **BREAKING (spec-level)**: change the Annotation Export requirement from one JSONL record per document to one record per bounded window of a document. A document longer than the window length SHALL produce multiple records; the existing "one line per document" scenario is replaced. The API path, query parameters, and per-record `{tokens, tags}` shape are unchanged, so `worker.py` needs no contract change to consume it.
- Window documents on a token budget with overlap between consecutive windows, so an entity spanning a window boundary is fully present in at least one window.
- Raise the default `max_seq_length` so a window fits within it without truncation, and make the export window length and the training sequence length consistent with one another rather than independently chosen.
- Add an explicit guard: the worker SHALL fail a training job with a clear error when the dataset is too small to produce a meaningful train/test split, rather than silently training on a handful of rows.
- Preserve `imported_annotations` passthrough behaviour unchanged — those rows are already row-sized and must not be re-windowed.

## Capabilities

### New Capabilities

None. This corrects the behaviour of existing capabilities.

### Modified Capabilities

- `annotation-workspace`: the **Annotation Export** requirement changes from one record per document to one record per window, and gains a correctness requirement that BIO tags align to the correct tokens regardless of whitespace form.
- `training-worker`: the **Tokenize dataset** requirement gains an explicit no-silent-truncation constraint and a minimum-dataset-size guard.

## Impact

- **Code**: `src/annotation_service/api/v1/export.py` (`_tokenize`, `_bio_tags`, and the inline offset walk in `export_annotations`); `src/training_service/worker.py` (`max_seq_length` default, dataset size guard before `train_test_split`).
- **Data**: no migration. Nothing stored changes — `spans`, `suggested_spans`, and `document_text_spans` are untouched. Only the derived export output changes.
- **Downstream**: any tenant model trained before this change was trained on misaligned and truncated data. Existing model versions are not invalidated automatically, but their metrics are not comparable to post-fix runs; retraining is advisable and is a human decision, consistent with change 6's human-gated retraining.
- **Related but out of scope**: `_compute_bio_tags` in `spans.py` contains the same single-space assumption for the per-span `bio_tags` column. See Open Questions.
- **No impact**: changes 1 and 2 (this is independent of them and can land in parallel), the annotation UI, model serving, or extraction.

## Open Questions

- **Window size and overlap values**: the specific token budget and overlap are left to design.md. They must satisfy "a window fits in the model's sequence length without truncation" and "overlap ≥ the longest plausible entity", but the concrete numbers should be chosen against real tenant documents rather than guessed.
- **Does `_compute_bio_tags` in `spans.py` need the same offset fix?** It shares the single-space assumption and writes the stored `bio_tags` column that export prefers when present. If stored tags are themselves misaligned, fixing export alone is insufficient. This needs investigation during design — it may expand this change or warrant a follow-up.
- **Should existing model versions be flagged as trained on corrupt data?** Proposed: no automatic action, but surface it so a tenant admin can decide. Confirm this is the right call rather than silently leaving misleading metrics in the model registry.
- **Minimum dataset size threshold**: what row count is too small to train on? ADR-010 establishes per-entity-type dataset readiness thresholds; the guard added here should align with that rather than invent a second, competing threshold.
