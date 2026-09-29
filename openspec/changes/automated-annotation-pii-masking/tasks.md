## 1. Backend — safe-copy generation (`pii_masking.py`)

- [x] 1.1 New `src/annotation_service/services/pii_masking.py`: pure pattern detector — for each
      active `pattern`-sensitivity entity type, compile and run its `validation_rule` against
      `document_text`, producing `{entity_type, char_start, char_end, text}` spans; a
      non-compiling regex raises rather than silently matching nothing (`detect_pattern_spans`)
- [x] 1.2 `LocalModelClient` Protocol + `StubLocalModelClient` (mirroring `LLMClient` /
      `StubLLMClient` in `llm_client.py`): one method, tenant id + tokens in, per-token
      base-model-class predictions out
- [x] 1.3 `ModelServingClient` (named for what it calls, not the provider — there is only one
      local model, not a per-vendor choice the way the external LLM has Azure/OpenAI) implements
      `LocalModelClient` calling `POST /internal/v1/infer` on `model_serving` with the tenant's
      document tokens, authenticated the same way `extraction_service.worker` already does
      (`create_access_token` + Bearer header)
- [x] 1.4 Local-model predictions are reconstructed into entities via the *existing*
      `entity_normalizer.merge_wordpieces` / `reconstruct_entities` (imported from
      `extraction_service`, not reimplemented) and mapped to tenant `local_only` types via the
      *existing* `entity_views.entity_type_literals` bridge — the same mechanism
      `relational_projection.py` already uses to route PER/ORG/LOC/MISC (or a fine-tuned
      tenant's own label set) to a tenant's entity type name (`detect_local_only_spans`)
- [x] 1.5 `mask_document(document_text, entity_types, local_model_client, tenant_id) ->
      MaskingResult`: orchestrates 1.1 + 1.2-1.4, applies the same first-claimed-lowest-offset
      overlap rule `ground_entities` already uses, builds the masked copy with placeholders
      (stable per unique exact text — task 1.6), and returns the masked text, the local spans
      (already correct against the original document), and the offset-translation segment table
- [x] 1.6 Placeholder assignment: identical exact text within one document maps to the same
      placeholder token (keyed on the matched text itself); distinct values of the same type get
      distinguishable numbered tokens; no cross-document persistence of the assignment
- [x] 1.7 `translate_offset(masked_start, masked_end, segments) -> (start, end) | None`: pure
      function, returns `None` when the location falls inside a masked/placeholder region or
      straddles a segment boundary
- [x] 1.8 `LocalDetectionUnavailable` exception, raised when the local model call fails or a
      `validation_rule` fails to compile — never swallowed into an empty result
- [x] 1.9 (not in the original plan — added deliberately) `find_uncovered_local_only_type`: the
      coverage-gate check, kept in `pii_masking.py` alongside the mechanism it gates

## 2. Backend — wiring into `extract_and_ground_document`

- [x] 2.1 `worker.py::extract_and_ground_document` calls `mask_document` filters the tenant's
      entity types down to `open`-sensitivity before building the external payload — no change
      needed inside `llm_prelabel.py::build_entity_type_block`/`build_user_payload` themselves,
      since they already take whatever entity-type list the caller passes
- [x] 2.2 `extract_and_ground_document`: `mask_document` runs immediately after loading
      `document_text` and `entity_types`; a `LocalDetectionUnavailable` propagates before any
      call to `client.complete_json` (fail-closed)
- [x] 2.3 External payload built from `masked.masked_text` and the `open`-only entity-type
      subset; `ground_entities` grounds the LLM's response against `masked.masked_text`,
      unchanged
- [x] 2.4 Each grounded (masked-copy) offset translated back to the original document via
      `translate_offset`; a translation failure is counted as ungrounded, not discarded silently
- [x] 2.5 Translated LLM spans and `masked.local_spans` are concatenated and sorted — no second
      overlap-resolution pass needed, since a translated LLM span can only ever fall in the gaps
      between local spans by construction (documented in the code and covered by a wiring test)
- [x] 2.6 `replace_suggested_spans` receives the merged set — unchanged

## 3. Backend — fail-closed failure surfacing

- [x] 3.1 `run_llm_prelabel_sync` (gained a `local_model_client` parameter): catches
      `LocalDetectionUnavailable` alongside `LLMUnavailable`, records
      `f"local detection failed: {exc}"` on the job row, and re-raises
- [x] 3.2 `run_prelabel_batch_sync` (gained a `local_model_client` parameter): a
      `LocalDetectionUnavailable` for one document is caught by its own `except` clause (ahead of
      the existing broad `except Exception`) and recorded with the same distinguishing prefix;
      the batch loop continues to the next document exactly as it does for any other per-document
      failure

## 4. Backend — local_only coverage check at trigger time

- [x] 4.1 Single-document trigger endpoint (`llm_prelabel.py::trigger_llm_prelabel`): 422
      `LOCAL_ONLY_TYPE_NOT_COVERED` (naming the uncovered type) before enqueueing, via
      `find_uncovered_local_only_type`
- [x] 4.2 `seed_bootstrap.py` batch trigger (`create_prelabel_batch`): same check, same error
      code, before either batch kind is created

## 5. Backend — cache key and suggestion-source schema

- [x] 5.1 `src/shared/entity_config_version.py`: added `sensitivity`, `validation_rule`, and
      `base_label_mapping` to `CONFIG_FIELDS` and to `_SELECT_ACTIVE`/`normalize_entity_config` —
      broader than the original plan's "add sensitivity" (see design.md: all three fields govern
      local detection, so all three must bust the cache; caught and fixed during implementation,
      spec/design updated to match)
- [x] 5.2 Migration `054_masking_suggestion_sources.py`: widened `ck_suggested_spans_source`
      (from `038b`) to `('keyword', 'llm', 'pattern', 'local_model')` via
      `apply_to_all_tenant_schemas` — verified against a real `ner_dev` database (see § 6)

## 6. Verification & Evidence

- [x] 6.1 Ran every scenario this environment could exercise — see verification.md § Evidence Log
      for the full breakdown: `test_pii_masking.py` (19, pure unit), `test_pii_masking_wiring.py`
      (8, real DB + stubbed providers, including the two cache-bust tests added after the
      CONFIG_FIELDS correction), `test_pii_masking_batch.py` (3, batch-level coverage-check and
      fail-closed), plus regression suites (`test_llm_prelabel_*`, `test_seed_bootstrap_*`,
      `test_entity_config_*`/migration guards — 118 tests total) and the migration verification
      against real `ner_dev`. A full, untargeted `pytest tests/` run was attempted and did not
      complete in this session (same symptom the `annotation-workflow-review-simplification`
      change's own verification.md records) — every file plausibly affected was run individually
      instead.
- [x] 6.2 Functional evidence collected — verification.md § Evidence Log
- [ ] 6.3 Hallucination Risk Register mitigations: confirmed for risks 1-6 by direct test/code
      evidence; risk 7 (migration reversibility) confirmed by code review only, not exercised
      (no downgrade was run) — left unchecked pending a human reviewer's own look
- [ ] 6.4 ADR compliance (ADR-015, ADR-001): confirmed by the wiring tests and code reading (see
      verification.md § 3) — left unchecked pending human sign-off, per the schema's own
      instruction that this is a reviewer action
- [ ] 6.5 Audit Record sign-off — requires a human reviewer, not the implementing agent
- [x] 6.6 Ran `openspec validate automated-annotation-pii-masking --type change --strict` —
      passes (re-run after the CONFIG_FIELDS/spec amendment in task 5.1)

### Known, deliberately out-of-scope gap found during testing

Two pre-existing test-infrastructure files (`tests/test_llm_prelabel_api.py`,
`tests/seed_bootstrap_support.py`) maintain their own hand-rolled copies of
`public.entity_definitions`'s DDL for test isolation, predating several real columns. Both were
missing `sensitivity` (needed for this change's own tests to run at all) and have been patched
with an `ADD COLUMN IF NOT EXISTS` self-heal, mirroring how `db-init`'s migrations self-heal the
real schema. A third, unrelated gap was found and left alone: `tests/conftest.py`'s
`training_jobs` fixture table is missing `source_scope` (added by migration `046`, unconnected to
this change), which fails `test_seed_bootstrap_readiness.py::test_readiness_does_not_block_
submission` regardless of anything in this change. Flagged, not fixed — fixing unrelated test
infrastructure is out of scope here.
