## 1. Establish the Failing Baseline

- [ ] 1.1 Add `tests/test_annotation_export_offsets.py` with `test_tags_align_across_newline` reproducing the verified defect: text `"John Doe\nworks at Acme Corp"` with an `organization` span on `"Acme Corp"` currently tags the wrong tokens. Confirm the test FAILS against current code before any fix.
- [ ] 1.2 Add `test_tags_align_across_tabs_and_double_spaces` to the same file and confirm it also fails, establishing that the defect is whitespace-general and not newline-specific.
- [ ] 1.3 Measure the token-length distribution of real tenant documents and the longest entity span in the corpus. Record both — they are the inputs to the window budget and overlap values chosen in group 3 (design.md Open Questions requires these be measured, not guessed).

## 2. Offset Derivation Fix

- [ ] 2.1 Replace `_tokenize` and the inline offset walk in `src/annotation_service/api/v1/export.py` with a single pass yielding `(token, char_start, char_end)` triples, advancing past arbitrary whitespace runs. Tokenisation and offset derivation MUST NOT remain separate operations (design.md Decision 1).
- [ ] 2.2 Apply the same single-pass derivation to `_bio_tags`, or remove `_bio_tags` if it becomes redundant with the corrected inline path.
- [ ] 2.3 Remove every read of the stored `bio_tags` column from `export.py`; derive tags solely from each span's `char_start`/`char_end` (design.md Decision 2). Do not remove the column and do not change what `spans.py` writes.
- [ ] 2.4 Confirm tests 1.1 and 1.2 now pass, covering Spec Alignment rows 5-6.
- [ ] 2.5 Add `test_stored_bio_tags_ignored` supplying a span whose stored `bio_tags` deliberately disagrees with its offsets, asserting the offsets win. Covers Spec Alignment row 7.
- [ ] 2.6 Run the existing export regression tests in `tests/test_annotation_workspace.py` and `tests/test_bio_tags.py`. Any test that asserted stored-tag behaviour must be reviewed against design.md Decision 2 rather than assumed still valid — a failure here may be a corrected expectation, not a regression.

## 3. Windowing

- [ ] 3.1 Choose the window token budget and overlap from the measurements in task 1.3. Overlap MUST exceed the longest entity observed in the corpus. Document both values and the reasoning in the implementation.
- [ ] 3.2 Emit one record per window instead of one per document, windowing tokens and tags together from the same index range so they cannot desynchronise (verification.md Risk 3).
- [ ] 3.3 Ensure a document within the window budget still produces exactly one record, preserving the existing behaviour for short documents.
- [ ] 3.4 Leave the `imported_annotations` branch untouched — those rows are emitted verbatim, unwindowed and un-retokenised (design.md Non-Goals).
- [ ] 3.5 Add `tests/test_annotation_export_windowing.py` with `test_long_document_produces_multiple_records`, `test_consecutive_windows_overlap`, `test_boundary_entity_complete_in_one_window`, and `test_imported_rows_not_windowed`, covering Spec Alignment rows 2-4 and 10.
- [ ] 3.6 Confirm the existing export regression tests (Spec Alignment rows 1, 8, 9) still pass — short documents, entity-type filtering, and document filtering are unaffected by windowing.

## 4. Training Sequence Length

- [ ] 4.1 Raise the `max_seq_length` default in `src/training_service/worker.py` to a value derived from the window budget chosen in task 3.1, including a stated safety factor for subword expansion. The two values MUST be derived from one another, not chosen independently (verification.md Risk 7).
- [ ] 4.2 Confirm `max_seq_length` is still read from the job's approved hyperparameters with the new value only as a fallback — it MUST NOT be hardcoded (ADR-009).
- [ ] 4.3 Detect and record when a record's subword expansion exceeds `max_seq_length`, including an affected-record count. Truncation must be observable; the job MUST NOT fail solely because it occurred.
- [ ] 4.4 Add `test_window_sized_record_not_truncated`, `test_max_seq_length_override_respected`, and `test_truncation_is_recorded` to `tests/test_training_worker.py`, covering Spec Alignment rows 12-14.

## 5. Split Guard

- [ ] 5.1 Add a guard before `train_test_split` that fails the job with a clear error naming the row count when the split would yield zero evaluation rows. The guard MUST test only evaluation-partition size — no row-count sufficiency constant, no data-quality judgement (design.md Decision 4, ADR-010).
- [ ] 5.2 Confirm the job transitions to "failed" and that no training runs and no evaluation metric is reported when the guard trips.
- [ ] 5.3 Add `test_dataset_too_small_to_split_fails` and `test_sufficient_dataset_proceeds_without_extra_gate` to `tests/test_training_worker.py`, covering Spec Alignment rows 17-18.
- [ ] 5.4 Confirm `NER_MIN_ENTITIES_PER_TYPE` and `NER_MIN_TRAINING_ENTITIES` semantics and defaults are untouched by this change.

## 6. Verification & Evidence

- [ ] 6.1 Run all acceptance-criteria tests for every scenario in verification.md § Spec Alignment and confirm all pass.
- [ ] 6.2 Collect functional evidence (screenshot / test output / log) for each scenario — record one entry per row in verification.md § Evidence Log.
- [ ] 6.3 Confirm every Hallucination Risk mitigation step in verification.md § Hallucination Risk Register.
- [ ] 6.4 Confirm all ADR compliance steps in verification.md § Pattern & ADR Compliance.
- [ ] 6.5 Confirm `alembic/versions/` is unchanged — this change requires no migration.
- [ ] 6.6 Run one real training job end to end against a tenant with genuine annotated documents, and record the resulting row count and metrics. Note explicitly that these metrics are not comparable to any pre-fix run.
- [ ] 6.7 Complete Audit Record sign-off in verification.md § Audit Record (human reviewer required — this task cannot be marked complete by an agent).
- [ ] 6.8 Run `openspec validate training-data-integrity --type change --strict` and confirm it exits clean before archive.
