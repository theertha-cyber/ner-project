# Verification Plan

**Change:** automated-annotation-pii-masking
**Generated:** 2026-09-17
**Status:** ✅ Implemented and self-verified by the implementing agent. Human review and Audit
Record sign-off still pending (§ 6).

---

## 1. Spec Alignment

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | llm-prelabeling | Extraction Scope | Entity types without QA pairs are still extracted | Given two open-sensitivity types (one with QA pairs, one without), when pre-labeling runs, then both produce spans | pytest: `test_llm_prelabel_extraction_scope.py::TestEntityTypesWithoutQaPairs` | - [x] |
| 2 | llm-prelabeling | Extraction Scope | QA pairs do not limit extraction to their literal topic | Given a QA pair implying one answer, when the document has two distinct mentions, then both are extracted | pytest: `test_llm_prelabel_extraction_scope.py::TestQaPairsDoNotLimitScope` | - [x] |
| 3 | llm-prelabeling | Extraction Scope | A local_only entity type is never named in the external prompt | Given an open type and a local_only type, when pre-labeling runs, then the external payload names only the open type, and a local_only span is still stored | pytest: `test_pii_masking_wiring.py::TestExternalPayloadExcludesSensitiveTypes::test_prompt_names_only_the_open_type` | - [x] |
| 4 | llm-prelabeling | Extraction Scope | A pattern entity type is never named in the external prompt | Given an open type and a pattern type, when pre-labeling runs, then the external payload names only the open type, and a pattern span is still stored | pytest: same test as row 3 — asserts both `- case_number` and `- child_name` absent | - [x] |
| 5 | llm-prelabeling | Grounding and Verification | Quote grounds to exactly one location | Given no sensitive types active, when grounding runs, then the offset matches the original text directly | pytest: `test_llm_prelabel_grounding.py::TestGroundingSucceeds` | - [x] |
| 6 | llm-prelabeling | Grounding and Verification | Quote cannot be found in the document text | Given a quote absent from the text, when grounding runs, then no span is stored and it counts as ungrounded | pytest: `test_llm_prelabel_grounding.py` (unmatched-quote tests) | - [x] |
| 7 | llm-prelabeling | Grounding and Verification | Quote matches multiple locations in the document | Given a quote matching twice, when grounding runs, then the first unclaimed occurrence is stored | pytest: `test_llm_prelabel_grounding.py` (multi-match tests) | - [x] |
| 8 | llm-prelabeling | Grounding and Verification | A grounded offset in the masked copy translates to the real document's offset | Given a document with a masked span earlier in the text, when the LLM's quote grounds in the masked copy after that span, then the stored offset/text point at the original document, not the masked copy | pytest: `test_pii_masking_wiring.py::TestMergedStorageAndOffsetTranslation` (the "Acme Corp" offset, after a masked "Jimmy Smith") + `test_pii_masking.py::TestTranslateOffset` | - [x] |
| 9 | llm-prelabeling | Suggested Span Storage and Source Tracking | LLM pre-labeling replaces existing suggestions for the document | Given 2 keyword-sourced spans exist, when pre-labeling completes, then they are replaced by llm/pattern/local_model-sourced spans | pytest: `test_llm_prelabel_api.py::TestStorage::test_llm_prelabel_replaces_existing_suggestions` (regression; the merged-source case is row 10) | - [x] |
| 10 | llm-prelabeling | Suggested Span Storage and Source Tracking | Locally and externally sourced spans coexist for one document | Given open, pattern, and local_only types all present, when pre-labeling completes, then spans with all three sources exist | pytest: `test_pii_masking_wiring.py::TestMergedStorageAndOffsetTranslation::test_all_three_sources_are_stored_with_real_text_and_correct_offsets` | - [x] |
| 11 | llm-prelabeling | Suggested Span Storage and Source Tracking | An overlapping locally-detected span wins over a later-claimed external one | Given a pattern span claims a range first, when an LLM span overlaps it after translation, then the pattern span is kept and the LLM span is dropped | **Not empirically tested** — see note below the table | - [ ] |
| 12 | llm-prelabeling | Result Caching | Re-triggering on an unchanged document and configuration uses the cache | Given no changes since a successful run, when re-triggered, then it's served from cache with no new LLM call | pytest: `test_llm_prelabel_cache.py::TestCacheHit` | - [x] |
| 13 | llm-prelabeling | Result Caching | Configuration change invalidates the cache | Given a QA pair is added, when re-triggered, then the LLM is called again | pytest: `test_llm_prelabel_cache.py::TestCacheInvalidation::test_entity_config_change_invalidates_cache` | - [x] |
| 14 | llm-prelabeling | Result Caching | Reclassifying an entity type's sensitivity invalidates the cache | Given a type is reclassified from open to local_only, when re-triggered, then the pipeline reruns and the new payload excludes that type | pytest: `test_pii_masking_wiring.py::TestCacheBustsOnMaskingConfigChange::test_reclassifying_sensitivity_invalidates_the_cache` (also covers the reverse direction, local_only → open) | - [x] |
| — | llm-prelabeling | Result Caching | (added scenario) Changing a pattern type's validation_rule invalidates the cache | | pytest: `test_pii_masking_wiring.py::TestCacheBustsOnMaskingConfigChange::test_changing_a_validation_rule_invalidates_the_cache` | - [x] |
| 15 | llm-prelabeling | Safe-Copy Generation | A tenant with no pattern or local_only types sends the original text unchanged | Given all active types are open, when pre-labeling runs, then the masked copy equals the original and the full text is sent externally | pytest: `test_pii_masking.py::TestMaskDocument::test_no_sensitive_types_leaves_the_copy_identical` | - [x] |
| 16 | llm-prelabeling | Safe-Copy Generation | Detected spans are replaced with placeholders before the external call | Given a local_only match in the text, when the external payload is built, then it contains a placeholder, not the real substring | pytest: `test_pii_masking_wiring.py::TestExternalPayloadExcludesSensitiveTypes::test_prompt_never_contains_the_real_sensitive_text` | - [x] |
| 17 | llm-prelabeling | Safe-Copy Generation | A pattern match is replaced with a placeholder before the external call | Given a pattern match (SSN) in the text, when the external payload is built, then it does not contain the real SSN substring | pytest: same test as row 16 (asserts `"123-45-6789" not in payload`) + `test_pii_masking.py::TestMaskDocument::test_a_pattern_match_is_replaced_with_a_placeholder` | - [x] |
| 18 | llm-prelabeling | Local-Only Type Coverage Requirement | Trigger is refused when a local_only type has no base_label_mapping | Given an unmapped local_only type, when the single-document trigger is called, then 422 naming the type, and no job is enqueued | pytest: `test_pii_masking_wiring.py::TestLocalOnlyCoverageRequirement::test_trigger_refused_when_local_only_type_has_no_mapping` | - [x] |
| 19 | llm-prelabeling | Local-Only Type Coverage Requirement | Batch trigger is refused for the same reason | Given an unmapped local_only type, when a batch trigger is called, then 422 and no batch is created | pytest: `test_pii_masking_batch.py::TestBatchLocalOnlyCoverageRequirement::test_batch_trigger_refused_when_local_only_type_has_no_mapping` | - [x] |
| 20 | llm-prelabeling | Local-Only Type Coverage Requirement | A local_only type with a base_label_mapping does not block the trigger | Given a mapped local_only type, when the trigger is called, then 202 | pytest: `test_pii_masking_wiring.py::...test_trigger_allowed_when_local_only_type_is_mapped` (single-doc) + `test_pii_masking_batch.py::...test_batch_trigger_allowed_when_local_only_type_is_mapped` (batch) | - [x] |
| 21 | llm-prelabeling | Fail-Closed on Local Detection Failure | Local model unavailability blocks the external call entirely | Given the local model service is unreachable, when pre-labeling is triggered, then the job fails, no external request is made, and the failure reason names local-detection failure | pytest: `test_pii_masking_wiring.py::TestFailClosed::test_local_model_failure_blocks_the_external_call` | - [x] |
| 22 | llm-prelabeling | Fail-Closed on Local Detection Failure | A batch document's local-detection failure does not abort the batch | Given one of 10 documents hits an intermittent local-model failure, when the batch completes, then that document fails with a local-detection reason and the other 9 succeed, with no external request for the failed one | pytest: `test_pii_masking_batch.py::TestBatchFailClosed::test_one_documents_local_detection_failure_does_not_abort_the_batch` (3 documents, not 10 — same principle, smaller fixture) | - [x] |
| 23 | llm-prelabeling | Placeholder Stability Within a Document | Repeated mentions of the same value share one placeholder | Given the same name appears 3 times, when the masked copy is built, then all 3 occurrences get the identical placeholder | pytest: `test_pii_masking.py::TestMaskDocument::test_repeated_mentions_share_one_placeholder` | - [x] |
| 24 | llm-prelabeling | Placeholder Stability Within a Document | Distinct values of the same type get distinguishable placeholders | Given two different names of the same type, when the masked copy is built, then they get two different placeholders | pytest: `test_pii_masking.py::TestMaskDocument::test_distinct_values_get_distinct_placeholders` | - [x] |

Scenarios 1, 2, 5, 6, 7, 9, 12, 13 restate the canonical `llm-prelabeling` spec's pre-existing
scenarios in full (MODIFIED requirements replace their entire scenario set per the archive tool's
rule) — regression coverage confirming this change does not disturb existing behavior for a
tenant with no `pattern`/`local_only` types. Scenarios 3, 4, 8, 10, 11, 14-24 are the new behavior
this change introduces. One extra scenario (marked `—`) was added to the canonical spec beyond
what verification.md originally planned, covering the `validation_rule`/`base_label_mapping`
cache-key extension made during implementation (see design.md and tasks.md task 5.1).

**Row 11 is not empirically tested, and cannot be with the current implementation** — not a gap,
but a stronger guarantee than the scenario asks for. `translate_offset` returns `None` for any
range that is not *entirely* contained in one unmasked segment, so a translated LLM span can
never land inside, or straddle, a local span's character range — the two sets are disjoint by
construction (see the comment at the merge point in `extract_and_ground_document`). Forcing an
overlap to test the tiebreak rule would require deliberately breaking that guarantee first. A
human reviewer should confirm this reasoning holds rather than treat the unchecked box as an
outstanding test debt.

---

## 2. Hallucination Risk Register

| # | Risk Area | Potential AI Error | Human Check Required | Status |
|---|-----------|-------------------|----------------------|--------|
| 1 | The core invariant (ADR-015) | Any code path that constructs the external LLM payload from `document_text` instead of `masked_text` — e.g. a refactor that inlines `mask_document`'s result but keeps a reference to the original text in scope and uses the wrong variable | Read `extract_and_ground_document` line by line and confirm `document_text` itself is never passed to `build_user_payload` or `client.complete_json` — only `masked.masked_text` is | Confirmed by code reading (`worker.py::extract_and_ground_document`) and by `test_pii_masking_wiring.py::TestExternalPayloadExcludesSensitiveTypes::test_prompt_never_contains_the_real_sensitive_text`, which would fail if the real text ever reached the stub |
| 2 | Offset translation direction | Translating masked-copy offsets to original-document offsets backwards, or applying the translation to local spans (which are already correct against the original) and double-shifting them | Confirm `mask_document`'s local spans are merged in without going through `translate_offset`, and that only LLM-returned, masked-copy-grounded offsets are translated | Confirmed: `test_pii_masking_wiring.py::TestMergedStorageAndOffsetTranslation` uses a document where the masked span ("Jimmy Smith") precedes the translated one ("Acme Corp") — a backwards or skipped translation would produce a visibly wrong, not accidentally-correct, offset, and the test asserts the exact offset |
| 3 | Fail-open regression | Implementing local-detection failure handling by analogy to `GuardrailService._classify_once`'s deliberate fail-open pattern instead of the fail-closed behavior this change requires | Simulate a local model failure and assert the external LLM provider received zero requests, not just that the job status is "failed" | Confirmed: `test_pii_masking_wiring.py::TestFailClosed` asserts `llm_client.call_count == 0` after a local-model failure, for both the raise-through behavior and the recorded job status |
| 4 | `base_label_mapping` coverage check happens too late | Implementing the Local-Only Type Coverage Requirement's check inside `extract_and_ground_document` (a worker) instead of at the trigger endpoints (a 422 before enqueueing) | Confirm scenarios 18-19 assert 202/422 synchronously from the trigger HTTP call itself | Confirmed: both `test_pii_masking_wiring.py` (single-doc) and `test_pii_masking_batch.py` (batch) assert the HTTP response code directly from `client.post(...)`, never via job-status polling |
| 5 | Placeholder tokens leak into stored data | A stored suggested span's `text` field containing a placeholder token instead of the real document substring | Confirm every stored span's `text` is sliced from `document_text`, never copied from `masked_text` | Confirmed: `test_pii_masking_wiring.py::TestMergedStorageAndOffsetTranslation` asserts the stored `text_content` for the `organization` span equals `"Acme Corp"`, not a placeholder, and for `child_name`/`case_number` equals the real matched substrings |
| 6 | Cache key change is incomplete | Adding `sensitivity` to `CONFIG_FIELDS`'s hash inputs but not to the `_SELECT_ACTIVE` SQL query, so the hash function receives a dict with no `sensitivity` key | Test scenario 14 with a real reclassification, not a mocked config version | Confirmed, and the risk was in fact broader than originally scoped — `validation_rule` and `base_label_mapping` also needed the same treatment, caught during implementation (see design.md) and proven by two dedicated tests, not one |
| 7 | Migration reversibility for the new source values | The `050` migration's `downgrade()` dropping the widened CHECK constraint without first confirming no `pattern`/`local_only`-sourced rows exist | Confirm `050`'s downgrade documents the same caveat `038b` documents | Confirmed by code review only — the caveat is documented in `050`'s own docstring; downgrade itself was not executed against a database holding such rows (no reason to in this session, since nothing was ever downgraded) |

---

## 3. Pattern & ADR Compliance

| ADR | Decision Summary | Constraint on This Change | Verification Step | Status |
|-----|-----------------|--------------------------|-------------------|--------|
| ADR-015 (new, this change) | `pattern`/`local_only` entity type values never reach the external LLM provider; local-detection failure fails closed | This change's own implementation must hold the invariant it establishes | Confirmed by Hallucination Risk 1 and 3, plus scenarios 3, 4, 16, 17, 21 | Confirmed by passing tests, not code review alone |
| ADR-001 (tenant data isolation) | Every tenant's data and processing must stay scoped to that tenant | The new call to `model_serving`'s `/internal/v1/infer` must carry and enforce the correct tenant context, the same way the existing external-LLM call already resolves everything within the requesting tenant's schema | `ModelServingClient.infer` builds its Bearer token from `create_access_token(tenant_id=tenant_id, ...)`, the same tenant id `extract_and_ground_document` already resolves the document/entity-config from — code-reviewed, not independently re-tested, since `model_serving`'s own `get_tenant_id` enforcement is out of this change's scope (this change is a new *caller* of an existing, already-tenant-scoped endpoint) | Confirmed by code review; not exercised against a real `model_serving` instance in this session (`StubLocalModelClient` stands in for it in every test) |

---

## 4. Evidence Requirements

### Functional Evidence

- [x] Scenarios 1-2 (Extraction Scope, regression): pytest, `test_llm_prelabel_extraction_scope.py`, unchanged, 43/43 in the file
- [x] Scenarios 3-4 (Extraction Scope, new): pytest, `test_pii_masking_wiring.py`, asserting the external payload's entity-type list excludes non-open types
- [x] Scenarios 5-7 (Grounding and Verification, regression): pytest, `test_llm_prelabel_grounding.py`, unchanged
- [x] Scenario 8 (offset translation): pytest, `test_pii_masking_wiring.py` + `test_pii_masking.py::TestTranslateOffset`
- [x] Scenario 9 (Suggested Span Storage, regression): pytest, `test_llm_prelabel_api.py::TestStorage`
- [x] Scenario 10 (merged sources): pytest, `test_pii_masking_wiring.py::TestMergedStorageAndOffsetTranslation`
- [ ] Scenario 11 (overlap rule, cross-source): not empirically tested — see the note under § 1's table (prevented by construction, not merely untested)
- [x] Scenarios 12-13 (Result Caching, regression): pytest, `test_llm_prelabel_cache.py`
- [x] Scenario 14 (cache busts on sensitivity/validation_rule/base_label_mapping change): pytest, `test_pii_masking_wiring.py::TestCacheBustsOnMaskingConfigChange` (2 tests)
- [x] Scenarios 15-17 (Safe-Copy Generation): pytest, exact payload string absence/presence checks in `test_pii_masking_wiring.py` and unit coverage in `test_pii_masking.py`
- [x] Scenarios 18-20 (Local-Only Type Coverage Requirement): pytest against both trigger endpoints (`test_pii_masking_wiring.py` single-doc, `test_pii_masking_batch.py` batch)
- [x] Scenarios 21-22 (Fail-Closed on Local Detection Failure): pytest, `test_pii_masking_wiring.py::TestFailClosed` (single-doc) and `test_pii_masking_batch.py::TestBatchFailClosed` (batch), asserting zero calls reached the stubbed external LLM client
- [x] Scenarios 23-24 (Placeholder Stability): pytest, pure unit tests in `test_pii_masking.py`
- [ ] Live integration against a real `model_serving` and real external LLM provider: not performed — every test in this session stubs both providers; this is the one gap a human reviewer should weigh before treating ADR-015 as proven against the *real* providers rather than against their contracts

### Structural Evidence

- [x] Code review completed — implementation matches design.md decisions (detection against real text only, masking before the external call, fail-closed error handling, placeholder stability, cache key extension)
- [x] ADR-015 and ADR-001 compliance confirmed (§ 3) — ADR-015 by passing tests, ADR-001 by code review only
- [x] No undocumented architectural patterns introduced
- [x] No AI-invented requirements present in generated code (cross-checked against this change's spec delta)
- [x] Migration `050` reviewed and verified against a real `ner_dev` database (widened CHECK constraint confirmed via `pg_get_constraintdef`); downgrade path reviewed but not executed

### Edge Case Evidence

- [x] Risk 1 (core invariant) confirmed by direct code reading and by test
- [x] Risk 2 (translation direction) confirmed by scenario 8's targeted test
- [x] Risk 3 (fail-open regression) confirmed by scenario 21's zero-external-calls assertion
- [x] Risk 4 (coverage check timing) confirmed by scenarios 18-19 asserting synchronous 422
- [x] Risk 5 (placeholder leaking into storage) confirmed by asserting stored `text_content` equals the real substring
- [x] Risk 6 (incomplete cache key change) confirmed by scenario 14's two tests using real reclassification/rule changes
- [ ] Risk 7 (migration reversibility) confirmed by code review only — downgrade not executed

---

## 5. Evidence Log

| # | Evidence Type | Description / Link | Scenario(s) Covered | Collected By | Date |
|---|--------------|-------------------|---------------------|--------------|------|
| 1 | Functional | `pytest tests/test_pii_masking.py -v`: 19/19 passed (pure unit tests, no DB/network) | 15, 17 (partial), 23, 24, plus internal unit coverage of `detect_pattern_spans`/`detect_local_only_spans`/`find_uncovered_local_only_type`/`translate_offset` | Claude (implementing agent) | 2026-09-17 |
| 2 | Functional | `pytest tests/test_pii_masking_wiring.py -v`: 8/8 passed (real Postgres, stubbed external LLM and local model) | 3, 4, 8, 10, 14, 16, 17, 18, 20, 21 | Claude (implementing agent) | 2026-09-17 |
| 3 | Functional | `pytest tests/test_pii_masking_batch.py -v`: 3/3 passed (real Postgres, real HTTP layer via `httpx.ASGITransport`) | 19, 20 (batch), 22 | Claude (implementing agent) | 2026-09-17 |
| 4 | Functional | `pytest tests/test_llm_prelabel_grounding.py tests/test_llm_prelabel_extraction_scope.py -v`: 43/43 passed, unchanged | 1, 2, 5, 6, 7 (regression) | Claude (implementing agent) | 2026-09-17 |
| 5 | Functional | `pytest tests/test_llm_prelabel_cache.py tests/test_llm_prelabel_api.py -v`: 17/17 passed, after fixing a pre-existing gap in a shared test fixture (see § 6 caveats) | 9, 12, 13 (regression) | Claude (implementing agent) | 2026-09-17 |
| 6 | Functional | `pytest tests/test_seed_bootstrap_batch.py tests/test_seed_bootstrap_acceptance.py tests/test_seed_bootstrap_proposal.py -v`: 32/32 passed, after fixing the same class of pre-existing fixture gap in `seed_bootstrap_support.py` | Regression: `seed-bootstrap`'s Batch Pre-labeling requirement, which defers to `llm-prelabeling`'s behavior — confirmed the deferral still holds | Claude (implementing agent) | 2026-09-17 |
| 7 | Functional | `pytest tests/test_entity_config_value_kind.py tests/test_migration_037_entity_view_metadata.py tests/test_migration_042_045_guards.py tests/test_migration_entity_definition_value_kind.py -v`: 26/26 passed | Regression, `entity-sensitivity-classification` (dependency) unaffected | Claude (implementing agent) | 2026-09-17 |
| 8 | Structural | `docker compose build db-init && docker compose up db-init` against real `ner_dev`: migration `050` applied cleanly on top of `049`; `verify_schema` reported "no drift detected" | Migration correctness | Claude (implementing agent) | 2026-09-17 |
| 9 | Functional | Direct psql against `ner_dev`: `pg_get_constraintdef` on `tenant_template.suggested_spans`'s `ck_suggested_spans_source` shows `('keyword', 'llm', 'pattern', 'local_model')` | Migration `050` | Claude (implementing agent) | 2026-09-17 |
| 10 | Structural | One confirmed pre-existing, unrelated failure isolated and left alone: `test_seed_bootstrap_readiness.py::test_readiness_does_not_block_submission` fails on a `training_jobs.source_scope` column missing from `tests/conftest.py`'s hand-rolled fixture table (migration `046`, unconnected to this change) | N/A — documented, not fixed (out of scope) | Claude (implementing agent) | 2026-09-17 |

**Not collected**: a live end-to-end run against real `model_serving` and a real external LLM provider (every test here stubs both). A full, untargeted `pytest tests/` run was also attempted and did not complete in this session (see § 6 caveats) — every file plausibly affected by this change was identified and run individually instead (rows 1-7 above), the same mitigation the `annotation-workflow-review-simplification` change's own verification.md used for the same symptom.

---

## 6. Audit Record

**Change slug:** automated-annotation-pii-masking
**Proposal:** `openspec/changes/automated-annotation-pii-masking/proposal.md`
**Spec files reviewed:**
  - specs/llm-prelabeling/spec.md

### Reviewer Sign-Off

| Check | Status |
|-------|--------|
| Design reviewed against proposal | - [ ] |
| All ADRs in Section 3 verified compliant | - [ ] |
| Spec Alignment table complete (no missing scenarios) | - [ ] |
| Evidence Log populated with real evidence | - [ ] |
| All functional evidence items in Section 4 checked | - [ ] |
| All structural evidence items in Section 4 checked | - [ ] |
| All edge case evidence items in Section 4 checked | - [ ] |

### AI Output Review

| Check | Status |
|-------|--------|
| All generated artifacts reviewed for spec alignment | - [ ] |
| No hallucinated requirements introduced | - [ ] |
| No undocumented patterns used | - [ ] |
| No AI-invented fields, endpoints, or behaviours present | - [ ] |
| Every THEN clause in specs has a corresponding evidence entry | - [ ] |
| Hallucination risk register reviewed and all mitigations confirmed | - [ ] |

**Archive approved by:** _(pending — not yet implemented)_

**Date:** _(pending)_

**Caveats carried into the archive:** _(none yet — this is a pre-implementation verification plan)_

**Prerequisite:** this change depends on `entity-sensitivity-classification`, which has been
implemented and self-verified in this same session (see its own verification.md) but not yet
archived — both remain pending the same human review and Audit Record sign-off.
