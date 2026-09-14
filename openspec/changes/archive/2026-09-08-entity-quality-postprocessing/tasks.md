## 1. Confidence calibration (blocking — lands first)

- [x] 1.1 Record a pre-change pytest baseline (the suite is red on `main`) so newly failing tests are distinguishable from pre-existing failures.
- [x] 1.2 Replace `scores = np.max(logits, axis=-1)[0]` in `src/model_serving/services/inference_service.py:191` with a softmax over the label axis, taking the probability of the argmax label.
- [x] 1.3 Confirm `_infer_with_base_model` (`inference_service.py:326`) emits the same `[0,1]` scale; document the equivalence in a code comment.
- [x] 1.4 Confirm the sliding-window overlap tie-break (`inference_service.py:262-268`) still selects the higher-probability prediction under the new scale.
- [x] 1.5 Verification: `tests/test_inference_confidence_calibration.py` — unit tests for rows 2, 3, 4 (calibrated range on both paths, hand-computed softmax comparison, tie-break).
- [x] 1.6 Verification: re-run existing `tests/` covering `/internal/v1/infer` for rows 1, 5, 6, 7 (custom labels, base fallback, load-failure fallback, 403).

## 2. Migration A — `document_entities` provenance

- [x] 2.1 Add `alembic/versions/035_document_entities_provenance.py` adding `source_entity_value`, `source_entity_type`, `postprocess_status`, `postprocess_model`, `postprocess_prompt_version`, `postprocess_at`, `extraction_schema_version`, `occurrence_count` — all nullable or defaulted — to `tenant_template` and every existing tenant schema, following the per-schema DDL pattern in `alembic/versions/029_document_entities_typed_values.py`.
- [x] 2.2 Ensure the migration skips tenant schemas with no `document_entities` table rather than aborting.
- [x] 2.3 Implement the downgrade to drop only the added columns.
- [x] 2.4 Verification: `tests/test_migration_document_entities_provenance.py` — rows 86, 87, 88, 89 (columns per schema, existing rows unchanged, missing-table tolerance, downgrade).

## 3. Deterministic repairs — normalization and reconstruction

- [x] 3.1 Extend `canonicalize()` in `src/extraction_service/services/entity_normalizer.py` to strip Unicode general-category `Cf` characters and fold typographic punctuation (U+2018/U+2019→`'`, U+201C/U+201D→`"`, U+2013/U+2014→`-`) before casefold and whitespace collapse.
- [x] 3.2 Add `max_entity_word_gap` to `src/shared/config.py` (default 2).
- [x] 3.3 Widen `_is_adjacent` to accept a same-page continuation within `max_entity_word_gap`; keep differing pages and NULL page numbers failing closed (split).
- [x] 3.4 Add span punctuation trimming in `reconstruct_entities._flush`, adjusting `char_start`/`char_end` by the characters removed from each end.
- [x] 3.5 Add a leading-numeral-with-trailing-words branch to `_read_number` in `src/extraction_service/services/semantic_normalizer.py`.
- [x] 3.6 Verification: `tests/test_entity_normalizer_unicode.py` — rows 8, 9, 10, 11 (U+200B equality, curly apostrophe, dashes, purity).
- [x] 3.7 Verification: `tests/test_entity_reconstruction_gap.py` — rows 12, 13, 14, 15, using the real `"Having two and a half years of experience"` prediction sequence, plus differing-page and NULL-page cases.
- [x] 3.8 Verification: `tests/test_entity_span_trimming.py` — rows 16, 17, 18, 19 including the offset/slice property check.
- [x] 3.9 Verification: `tests/test_semantic_normalizer_numeral_prose.py` — rows 24, 25, 26, 27, 28.

## 4. Validity gate and duplicate policy

- [x] 4.1 Add `min_entity_value_length` and a per-entity-type short-value exemption mechanism to configuration; decide the exemption shape (open question 2 in design.md) and record it.
- [x] 4.2 Implement the validity gate rejecting empty, punctuation-only, and under-length canonical values before `insert_document_entities`, returning a rejected count.
- [x] 4.3 Implement intra-document collapse on `(document_id, entity_type, normalized_value)` producing `occurrence_count` and retaining the first mention's `page_number`/`char_start`/`char_end`.
- [x] 4.4 Report the rejected count on the extraction run alongside the existing `unreviewed`/`unparseable` counters in `src/extraction_service/worker.py`.
- [x] 4.5 Verification: `tests/test_entity_validity_gate.py` — rows 20, 21, 22, 23.
- [x] 4.6 Verification: `tests/test_document_entity_dedup.py` — rows 64, 65, 66, 67.
- [x] 4.7 Verification: re-run `tests/test_chat_api_sql*.py` and `tests/test_entity_resolver.py` and confirm no regression from changed row counts and values.

## 5. Migration B — `extraction_runs` processing mode

- [x] 5.1 Add `alembic/versions/036_extraction_runs_processing_mode.py` adding `processing_mode` (default `bert_only`), `postprocess_model`, `postprocess_prompt_version`, and a degraded indicator to `tenant_template` and every tenant schema.
- [x] 5.2 Implement the downgrade.
- [x] 5.3 Verification: `tests/test_migration_extraction_runs_processing_mode.py` — rows 90, 91, 92.

## 6. Batch extraction contract — processing mode

- [x] 6.1 Add a `BatchExtractRequest` model to `src/extraction_service/api/v1/schemas.py` carrying `documentIds` and `processing_mode` with a `bert_only` default and a strict enum.
- [x] 6.2 Change `POST /api/v1/extract-batch` in `src/extraction_service/api/v1/extraction.py` to accept the body, retaining the `documentIds` query parameter for one release.
- [x] 6.3 Reject `bert_llm_postprocess` with 422 when no post-processor is configured; reject unknown modes with 422. Create no run in either case.
- [x] 6.4 Persist `processing_mode` on the run at insert; pass it as a `run_batch_extraction` task argument.
- [x] 6.5 Add the mode, post-processor model, prompt version, and degraded indicator to `BatchRunStatus` / `BatchRunListItem` and the status/list endpoints.
- [x] 6.6 Confirm `get_already_extracted` skip logic is untouched, so mode changes reprocess nothing.
- [x] 6.7 Verification: `tests/test_extract_batch_processing_mode.py` — rows 68, 69, 70, 71, 72, 73, 74, 83.
- [x] 6.8 Verification: re-run the existing batch-extraction suite for rows 76, 77, 78, 79, 80, 81, 82.
- [x] 6.9 Verification: `tests/test_extract_confidence_threshold.py` — rows 84, 85 (threshold meaningful against the calibrated scale).

## 7. Post-processor — client, contract, and validation

- [x] 7.1 Add post-processor settings to `src/shared/config.py`: `postprocess_enabled`, `postprocess_confidence_threshold`, `postprocess_timeout_seconds`, `postprocess_context_chars`, `postprocess_token_budget`, `postprocess_prompt_version`.
- [x] 7.2 Create `src/extraction_service/services/entity_postprocessor.py` building the Azure OpenAI client the way `src/chat_api/services/rag_orchestrator.py:36-44` does, using `settings.azure_openai_chat_deployment`.
- [x] 7.3 Implement candidate selection: calibrated-confidence threshold (calibrated rows only), unparseable typed value, single-token entity of a multi-token type, and same-type same-page neighbour within `max_entity_word_gap`.
- [x] 7.4 Implement per-document request construction with server-assigned `candidate_id` values and a text window bounded by `postprocess_context_chars` containing each candidate's span.
- [x] 7.5 Author the prompt template, versioned by `postprocess_prompt_version`, constraining output to the `keep`/`modify`/`merge`/`reject` schema.
- [x] 7.6 Implement the six validation steps from design.md Decision 6, including the canonical-folded substring check against the server-built window.
- [x] 7.7 Enforce the permitted-transformation table: merge bounds, sentence-bounded boundary repair, `entity_type` restricted to the tenant's `entity_definitions` (tenant-filtered, case-insensitive), rejection allowed, typed-value emission ignored, alias canonicalization ignored.
- [x] 7.8 Route accepted values through the existing `canonicalize` and `apply_semantic_normalization` before persistence; never write to `document_entities` from the post-processor.
- [x] 7.9 Verification: `tests/test_entity_postprocessor_selection.py` — rows 29, 30, 31, 32, 33.
- [x] 7.10 Verification: `tests/test_entity_postprocessor_contract.py` — rows 34, 35, 36, 37, 38.
- [x] 7.11 Verification: `tests/test_entity_postprocessor_no_invention.py` — rows 39, 40, 41.
- [x] 7.12 Verification: `tests/test_entity_postprocessor_transformations.py` — rows 42, 43, 44, 45, 46, 47.
- [x] 7.13 Verification: `tests/test_entity_postprocessor_tenant_scope.py` — rows 53, 54, 55.

## 8. Worker integration, fail-open, and provenance persistence

- [x] 8.1 Accept `processing_mode` in `run_batch_extraction` and gate the post-processing stage on it.
- [x] 8.2 Insert the post-processing stage between `apply_semantic_normalization` and `insert_document_entities` in `src/extraction_service/worker.py`.
- [x] 8.3 Implement the fail-open matrix: timeout, provider error with one backoff retry, 429 within and beyond budget, malformed response discarding the batch, per-item invalidity, and budget exhaustion degrading the remainder of the run.
- [x] 8.4 Ensure a post-processing failure never increments `failed_count` and never fails the run; record the degraded indicator on the run.
- [x] 8.5 Extend `insert_document_entities` to write the provenance columns, populating `source_entity_value`/`source_entity_type` only when the value or type actually changed.
- [x] 8.6 Stamp `extraction_schema_version` on every persisted row.
- [x] 8.7 Verification: `tests/test_extraction_worker_postprocess_failopen.py` — rows 48, 49, 50, 51, 52.
- [x] 8.8 Verification: `tests/test_document_entity_provenance.py` — rows 56, 57, 58, 59, 60, 61, 62, 63.

## 9. Evaluation harness

- [x] 9.1 Build the labelled entity fixture from real tenant documents, covering every required failure class; source the seed cases from the defects in `proposal.md` (U+200B `software engineer`, `two`/`half years`, `COMPANY HANNAH`, `DEGREE JAVA`, `PHONE_NUMBER Z5060835`, `2 years of experience,`, repeated `node.js`).
- [x] 9.2 Implement the fixture loader with required-class coverage enforcement.
- [x] 9.3 Implement entity-level metrics: precision, recall, F1, exact-value accuracy, entity-type accuracy, and hallucination rate (unsupported value, and entity with no BERT candidate).
- [x] 9.4 Implement the three-configuration runner (BERT-only, BERT+repairs, BERT+repairs+post-processing) reporting adjacent-pair deltas.
- [x] 9.5 Add structured-query success rate to `src/shared/retrieval/eval/metrics.py` and surface it in `report.py`.
- [x] 9.6 Implement the release gate: zero hallucination rate and no structured-query success regression against BERT+repairs.
- [x] 9.7 Verification: `tests/test_entity_quality_eval.py` — rows 93, 94, 95, 96, 97, 98, 99, 102, 103, 104.
- [x] 9.8 Verification: `tests/test_retrieval_eval_structured_success.py` — rows 100, 101.
- [x] 9.9 Run the full evaluation against the development tenant and record all three configurations' results in verification.md § Evidence Log.

## 10. Portal contract (no UI implementation)

- [x] 10.1 Update `src/portal/src/types/extraction.ts` and the batch trigger call to send `processing_mode` in the request body, defaulting to `bert_only`.
- [x] 10.2 Surface the server's 422 rejection when a mode is unavailable, without creating a local run entry.
- [x] 10.3 Expose the run's processing mode and degraded indicator in the batch run list data model.
- [x] 10.4 Verification: `src/portal/src/components/extractions/BatchRunsTab.test.tsx` — rows 105, 106, 107, 108 (request payload, rejection surfacing, run-list reporting). The visible modal control is out of scope for this change.

## 11. Verification & Evidence

- [x] 11.1 Run all acceptance-criteria tests for every scenario in verification.md § Spec Alignment and confirm all pass.
- [x] 11.2 Collect functional evidence (screenshot / test output / log) for each scenario — record one entry per row in verification.md § Evidence Log.
- [x] 11.3 Confirm every Hallucination Risk mitigation step in verification.md § Hallucination Risk Register.
- [x] 11.4 Confirm all ADR compliance steps in verification.md § Pattern & ADR Compliance.
- [ ] 11.5 Complete Audit Record sign-off in verification.md § Audit Record (human reviewer required — this task cannot be marked complete by an agent).
- [x] 11.6 Run `openspec validate entity-quality-postprocessing --type change --strict` and confirm it exits clean before archive.
