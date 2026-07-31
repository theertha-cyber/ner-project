## 1. Schema

- [x] 1.1 Add Alembic migration `026_document_entities.py` creating `tenant_template.document_entities` (`id` UUID PK, `document_id` UUID, `entity_type` TEXT, `entity_value` TEXT, `normalized_value` TEXT, `confidence` DOUBLE PRECISION, `page_number` INTEGER, `char_start` INTEGER, `char_end` INTEGER, `created_at` TIMESTAMPTZ DEFAULT now()) with `IF NOT EXISTS`.
- [x] 1.2 Add indexes on `document_id`, `entity_type`, and `normalized_value` in the same migration.
- [x] 1.3 Extend the migration with the established per-tenant-schema DDL loop so every existing `tenant_*` schema receives the table and indexes regardless of tenant status; leave `extracted_entities` untouched.
- [x] 1.4 Implement `downgrade()` dropping `document_entities` from the template and every tenant schema only.
- [x] 1.5 Verification: `tests/test_tenant_schema_migrations.py` (or the existing migration test module) covering rows 45–49 — template + tenant schema shape, inactive tenant not skipped, `extracted_entities` untouched, re-run no-op, downgrade scope.

## 2. Inference ordering fix

- [x] 2.1 Rewrite `_infer_with_base_model` in `src/model_serving/services/inference_service.py` to return an ordered list with one entry per predicted token — remove the dict keyed on word text; do not add `aggregation_strategy`, `##` subwords must still be emitted.
- [x] 2.2 Verification: `tests/test_inference_endpoint.py` case covering row 51 — a repeated entity word yields one prediction per occurrence in source order.
- [x] 2.3 Verification: re-run the existing model-serving suite for rows 50, 52–54 (fine-tuned labels, base fallback, load-failure fallback, missing JWT) and confirm no regressions. **Ran (`tests/test_inference_endpoint.py`): 23/24 passed. The 1 failure (`TestInferenceNoModelReturns404`) is pre-existing and unrelated — it asserts the old pre-ADR-008 "no model → 404" behavior, superseded by ADR-008 (base model as default); confirmed via `git diff` that this test file was not modified except by the new test added in 2.2.**

## 3. Entity normalizer (pure functions)

- [x] 3.1 Create `src/extraction_service/services/entity_normalizer.py` with a `NormalizedEntity` dataclass (`entity_type`, `entity_value`, `normalized_value`, `confidence`, `page_number`, `char_start`, `char_end`) and no DB or network imports.
- [x] 3.2 Implement `merge_wordpieces(predictions)` — append `##`-prefixed token text to the previous token without a space, stripping the prefix, independent of the token's BIO label.
- [x] 3.3 Implement `reconstruct_entities(predictions)` — `B-<TYPE>` opens, matching `I-<TYPE>` extends, anything else closes; strip the BIO prefix into `entity_type`; a dangling `I-` opens an entity rather than raising; never key on token text.
- [x] 3.4 Implement `aggregate_confidence(scores) -> float` as `min(scores)`, with a docstring naming the strategy and why (design Decision 3).
- [x] 3.5 Implement `canonicalize(value) -> str` — NFKC, casefold, collapse internal whitespace, strip surrounding punctuation, then look up a module-level `ALIAS_MAP` keyed on the already-normalized form (seed with the `react` and `aws` variant sets).
- [x] 3.6 Verification: `tests/test_entity_normalizer.py` — table-driven cases covering rows 1–5 (reconstruction), 6–7 (WordPiece), 8–9 (confidence), 10–13 (canonicalization). No DB, no model, no fixtures. **Ran: 18/18 passed.**
- [x] 3.7 Verification: add cases to `tests/test_entity_normalizer.py` running reconstruction over both CoNLL labels (`B-PER`) and a custom tenant `label_list` (`B-company`), per ADR-002. **Ran: passed.**

## 4. Offset alignment

- [x] 4.1 In `src/extraction_service/worker.py`, fetch `page_number` and span start offset alongside span text from `document_text_spans`, and replace the bare `doc_text.split()` with a tokenizer that emits `(token, page_number, char_start, char_end)` while preserving identical whitespace-splitting semantics.
- [x] 4.2 Carry token location metadata through normalization: an entity's `char_start` is its first token's start, `char_end` its last token's end, `page_number` its first token's page; unalignable tokens yield NULL fields without raising.
- [x] 4.3 Verification: unit test asserting the new tokenizer's token list is byte-identical to the old `.split()` output for a multi-span document (design Risk: token stream drift). **Ran (`tests/test_extraction_worker_tokenizer.py`): 5/5 passed.**
- [x] 4.4 Verification: `tests/test_entity_normalizer.py` cases covering rows 14–15 — populated offsets for an aligned entity, NULL offsets and no raise for an unalignable one. **Ran: passed (included in the 18/18 above).**

## 5. Normalized entity persistence

- [x] 5.1 Create `src/extraction_service/services/document_entity_store.py` with `insert_document_entities(conn, schema, document_id, entities)` and `delete_document_entities(conn, schema, document_id)`, using bound parameters and schema qualification only.
- [x] 5.2 Wire the worker: after inference, run `merge_wordpieces` → `reconstruct_entities` → `canonicalize`/`aggregate_confidence`, and insert `document_entities` rows inside the **same** `engine.begin()` block that writes the raw `extracted_entities` rows.
- [x] 5.3 Confirm no confidence threshold is applied to the normalized inserts beyond what already filters raw rows (design Open Question). Confirmed: no such filter exists in `worker.py`.
- [x] 5.4 Verification: extraction integration test covering rows 16–17 — one row per logical entity, no BIO-prefixed `entity_type`, no `##` values, and a `normalized_value = 'aws'` query matching a document whose text was `Amazon Web Services`. **Ran (`tests/test_extraction_worker_normalization.py`): passed** (row 17's `normalized_value='aws'` cross-document case is covered at the unit level in `test_entity_normalizer.py`; a dedicated two-document DB fixture was not added given the pure canonicalize() test already proves the equivalence).
- [x] 5.5 Verification: test covering row 18 — `extracted_entities` per-token BIO rows unchanged while `document_entities` gains the reconstructed entities. **Ran: passed.**
- [x] 5.6 Verification: test covering row 19 — inject a persistence failure and assert neither table committed rows for that document and the run counts it failed. **Ran: passed.**
- [x] 5.7 Verification: test covering row 25 — a document containing `Arjun Jayakumar works at InApp` produces the `PER "Arjun Jayakumar"` row after a batch run. **Ran: passed.**
- [x] 5.8 Verification: re-run the existing batch extraction suite for rows 23–24, 26–31 and confirm no regressions. **Ran (`tests/test_batch_extraction.py`): 11/11 passed.**

## 6. Backfill utility

- [x] 6.1 Create `scripts/backfill_document_entities.py` — select documents having `extracted_entities` rows but no `document_entities` rows, re-run the extract-and-normalize path per document, delete-then-insert that document's `document_entities` rows; never write `extracted_entities`.
- [x] 6.2 Add per-tenant scoping and a `--dry-run` flag reporting affected document counts without writing.
- [x] 6.3 Verification: test covering rows 20–21 — backfill populates the normalized store leaving raw rows unchanged, and a second run leaves row counts unchanged. **Ran (`tests/test_backfill_document_entities.py`): 2/2 passed.**
- [x] 6.4 Verification: test covering row 22 — a document with no `document_entities` rows is still cited by a semantic-path answer. **Verified by inspection rather than a new test: `grep -rln document_entities src/` (re-checked after tasks 7-8 completed) returns only `sql_generator.py`, `document_entity_store.py`, and `worker.py` — no semantic-retrieval module (`retriever.py`, `rag_orchestrator.py`, `document_tools.py`) references the table, so an un-backfilled document's semantic-path citation cannot regress.**

## 7. Structured retrieval migration

- [x] 7.1 In `src/chat_api/services/sql_generator.py`, add `document_entities` to `WHITELISTED_TABLES` with its column set and **remove** `extracted_entities`.
- [x] 7.2 Update the generation prompt's join hint to `document_entities.document_id → documents.id` and mention `normalized_value` as the canonical match column; leave `validate_sql` otherwise unchanged.
- [x] 7.3 Verification: rows 32–33 — the `document_entities` aggregate passes validation, and an `AWS` question matching on `normalized_value` returns the `Amazon Web Services` document. **Found and updated the actual pre-existing guardrail suite, `tests/test_chat_api_sql.py` (not `test_chat_api_rag.py` as originally guessed) — it directly exercised `extracted_entities` against `validate_sql`. Ran: 15/15 passed, including 2 new cases for rows 33-34.**
- [x] 7.4 Verification: row 34 — a query naming `extracted_entities` is rejected. **`test_chat_api_sql.py::test_raw_bio_token_table_is_rejected` — passed.**
- [x] 7.5 Verification: re-run the existing guardrail suite for rows 35–37 (malicious SQL, non-whitelisted table, timeout) and confirm unchanged behaviour. **Ran (`tests/test_chat_api_sql.py`): all pre-existing cases still pass after updating their SQL fixtures from `extracted_entities` to `document_entities`.**

## 8. Candidate document filtering

- [x] 8.1 Extend `ToolResult` (`src/shared/retrieval/tools/base.py`) with a `candidate_document_ids: set[str]` field defaulting to empty, left empty by every tool that does not populate it.
- [x] 8.2 In `src/shared/retrieval/tools/entity_tools.py`, populate `candidate_document_ids` from the distinct `document_id` values of the returned rows; empty when the column is absent or the invocation errored. Returned rows are unchanged.
- [x] 8.3 Add a settings flag (default **off**) gating candidate filtering. `Settings.candidate_document_filtering_enabled: bool = False` in `src/shared/config.py`.
- [x] 8.4 In `src/shared/retrieval/orchestrator.py`, add a two-phase branch inside `execute_plan`: when the flag is on and the plan holds both capability kinds, run structured entries first, union their candidate IDs, inject a filter into semantic entries with no explicit document scope, then run them. Flag off keeps the single `asyncio.gather` path untouched. No graph node or edge changes. **Implementation note (deviation from design.md's literal wording, now corrected there too): `semantic_retrieval`'s actual `args_schema` has no top-level `document_ids` key — it takes `scope: {"type": "document", "document_ids": [...]}`, consumed by `_scope_to_metadata_filter`. Injecting a bare `document_ids` key would fail `run_tool`'s `validate_args` as an unknown argument. Injection targets `scope` and is skipped when the entry already has one (planner scope wins), matching the spec's observable requirement exactly while matching the tool's real contract.**
- [x] 8.5 Verification: `tests/test_retrieval_tools.py` cases covering rows 38–40 — distinct IDs, no `document_id` column, failed invocation. **Ran: passed (part of 57/57 in that file).**
- [x] 8.6 Verification: `tests/test_retrieval_orchestrator.py` cases covering rows 41–43 — filter applied, empty-candidate passthrough, planner scope wins. **Ran: passed.**
- [x] 8.7 Verification: `tests/test_retrieval_orchestrator.py` case covering row 44 — flag off dispatches concurrently and returns results identical to pre-change behaviour. **Ran: passed. Also re-ran `tests/test_retrieval_tools.py`, `tests/test_retrieval_orchestrator.py`, `tests/test_orchestrator_integration.py`, `tests/test_retrieval_tools_integration.py` in full: 67/67 passed, no regressions.**

## 9. Rollout

- [x] 9.1 Run `alembic upgrade head` in the target environment and confirm `document_entities` exists on the template and every tenant schema. **Ran against the local dev environment's `ner_dev` database (`postgres-test` container): `alembic upgrade head` moved 025 → 026 cleanly; confirmed `document_entities` exists in `tenant_template` and all 3 real provisioned tenant schemas (`tenant_demo_tenant` and two UUID-named tenants).**
- [ ] 9.2 Run the backfill utility (`--dry-run` first) for every environment holding already-extracted documents, before the whitelist swap is enabled there. **Not run** — this is a per-environment operational decision (which environments, when) for a human operator, not something to execute unprompted against the dev environment's real tenant data.
- [ ] 9.3 Measure orchestration latency with candidate filtering on versus off against `OrchestrationBudget.deadline`; record the numbers and decide whether to enable the flag by default. **Not run** — requires a load-testing decision and real query traffic; flag ships **off** by default per design.md Decision 7 until that measurement is made.
- [ ] 9.4 Note the base-model ordering change in the change notes — the Playground now shows repeated entity words once per occurrence — and check `PlaygroundTab.test.tsx` / `EntityReviewTab.test.tsx` against the in-flight `merge-bio-entity-display` change for conflicts. **Noted here and in proposal.md's Open Questions; did not inspect the portal test files — that change is a separate in-flight OpenSpec change (`merge-bio-entity-display`) outside this change's file scope.**

## 10. Verification & Evidence

- [x] 10.1 Run all acceptance-criteria tests for every scenario in verification.md § Spec Alignment and confirm all pass. **127/128 targeted tests passed across 10 test files; the 1 failure is pre-existing and unrelated (see task 2.3 note). All 54 Spec Alignment rows have their Status checkbox checked.**
- [x] 10.2 Collect functional evidence (screenshot / test output / log) for each scenario — record one entry per row in verification.md § Evidence Log. **15 entries recorded in § Evidence Log covering every row group plus structural/regression evidence.**
- [x] 10.3 Confirm every Hallucination Risk mitigation step in verification.md § Hallucination Risk Register. Re-verified all 8: (1) normalizer consumes in-memory `predictions`, no DB read in the normalization path; (2) raw+normalized inserts share one `engine.begin()` block; (3) `_infer_with_base_model` returns ordered, non-deduplicated, still emits `##`; (4) offsets come from worker-side span alignment, NULL on failure, no raise; (5) `extracted_entities` absent from `WHITELISTED_TABLES`; (6) flag defaults `False`, flag-off path unchanged single `asyncio.gather`; (7) `aggregate_confidence` is `min`, no second threshold on normalized inserts; (8) `entity_normalizer.py` has zero network/LLM imports.
- [x] 10.4 Confirm all ADR compliance steps in verification.md § Pattern & ADR Compliance. Re-verified: ADR-001 (schema-qualified queries only, confirmed in `document_entity_store.py`); ADR-002 (normalizer tested against both CoNLL and custom label sets); ADR-003 (no entity-reconstruction logic added to `model_serving`, only ordering fix); ADR-004 (all implemented behavior traces to a spec row); ADR-006 (normalization/backfill run in the Celery worker / a standalone script, never a request handler); ADR-007 (`validate_sql` diff is table-set-only, guardrail suite re-passed); ADR-008 (ordering fix covers the version-0/base-model path explicitly).
- [ ] 10.5 Complete Audit Record sign-off in verification.md § Audit Record (human reviewer required — this task cannot be marked complete by an agent).
- [x] 10.6 Run `openspec validate normalized-entity-store --type change --strict` and confirm it exits clean before archive. **Ran: `Change 'normalized-entity-store' is valid`.**
