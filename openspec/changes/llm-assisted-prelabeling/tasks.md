## 1. Prerequisites & Open Questions

- [ ] 1.1 Obtain a decision on the PII / data-residency open question from proposal.md (may tenant documents be sent to an external LLM provider; is a per-tenant opt-in or self-hosted fallback required). This is a hard gate — do not start group 3 or later without it.
- [ ] 1.2 Obtain a decision on the concrete LLM provider/model and how credentials are supplied via environment variables only (per the AGENTS.md secret-hygiene invariant — no defaults for secret-class settings).
- [ ] 1.3 Obtain reviewer sign-off on the duplicate-quote resolution rule (first non-overlapping occurrence) recorded in design.md Open Questions.

## 2. Schema & Migrations

- [ ] 2.1 Add `qa_examples` column (nullable JSON array of `{question, answer}` objects) to `public.entity_definitions` via a new Alembic migration under `alembic/versions/`.
- [ ] 2.2 Add `source` column (text, not null, default `'keyword'`) to `{tenant_schema}.suggested_spans` in the same or a paired Alembic migration, applied across all tenant schemas following the existing per-tenant migration pattern.
- [ ] 2.3 Update `tenant_schema_ddl.py` so newly provisioned tenant schemas include the `source` column on `suggested_spans` from creation.
- [ ] 2.4 Verify migration is additive-only and reversible: run upgrade then downgrade against a scratch database and confirm no data loss on existing `suggested_spans` rows.

## 3. Entity Config — QA Pairs

- [ ] 3.1 Extend the entity type create/update API schemas in the gateway/entity-config layer to accept and persist optional `qa_examples`, validating each element has string `question` and `answer` fields.
- [ ] 3.2 Ensure `qa_examples` updates increment the entity type `version`, consistent with existing field-update behavior.
- [ ] 3.3 Add a tenant entity-config version/hash accessor that produces a stable value over (active entity types, their `examples`, their `qa_examples`) — required as a cache key component in group 7.
- [ ] 3.4 Extend `tests/test_entity_config.py` with `test_create_entity_type`, `test_update_entity_type`, `test_add_qa_examples_increments_version`, and `test_entity_type_without_qa_examples_is_valid` covering Spec Alignment rows 17-20.

## 4. LLM Client & Prompt Construction

- [ ] 4.1 Add a provider-agnostic LLM client interface in `src/annotation_service` with the concrete provider selected via environment configuration; no provider SDK details may leak into grounding or storage code.
- [ ] 4.2 Implement prompt construction that enumerates every active entity type for the tenant with its `description` and `examples`, attaches each type's `qa_examples` as few-shot context for that type only, and instructs full-document extraction of all occurrences of all types.
- [ ] 4.3 Constrain the response contract to a list of `{entity_type, quote}` objects only — the parser MUST reject or ignore any offset fields, so offsets can never originate from the model (design.md Decision 2).
- [ ] 4.4 Add `tests/test_llm_prelabel_extraction_scope.py` with `test_entity_types_without_qa_pairs_are_extracted` and `test_qa_pairs_do_not_limit_extraction_scope`, using a stubbed LLM client, covering Spec Alignment rows 4-5.

## 5. Grounding & Verification

- [ ] 5.1 Implement a pure `ground_quote(document_text, quote, claimed_ranges)` function performing exact case-insensitive matching and returning `(char_start, char_end)` or `None` — no fuzzy, normalized, or nearest-match fallback (design.md Decision 4).
- [ ] 5.2 Implement first-non-overlapping-occurrence selection when a quote matches multiple locations, mirroring the overlap handling in the existing `prelabel_document`.
- [ ] 5.3 Drop any LLM-returned entity whose `entity_type` is not an active tenant entity type, reusing the validation approach of `validate_entity_type` in `src/annotation_service/api/v1/spans.py`.
- [ ] 5.4 Track and expose per-job counts of returned vs. grounded vs. dropped suggestions so grounding drop-rate is observable (design.md Risks).
- [ ] 5.5 Add `tests/test_llm_prelabel_grounding.py` with `test_quote_grounds_to_single_location`, `test_unmatched_quote_is_dropped`, `test_duplicate_quote_takes_first_occurrence`, `test_unconfigured_entity_type_is_dropped`, and `test_non_extractive_answer_is_not_stored` covering Spec Alignment rows 6-10.

## 6. Async Task & Trigger Endpoint

- [ ] 6.1 Register a new Celery task on a dedicated non-GPU queue (e.g. `annotation.llm_jobs`) — must not use the `training.jobs` queue or any GPU node-pool selector (design.md Decision 6).
- [ ] 6.2 Implement the task body: resolve tenant schema, load document text and entity config, call the LLM client, ground results, write to `{tenant_schema}.suggested_spans` with `source: "llm"`, replacing all prior suggestions for that document.
- [ ] 6.3 Reuse the service-to-service token pattern from `src/training_service/worker.py` (`_make_service_token`) for any cross-service calls the task makes.
- [ ] 6.4 Add `POST /api/v1/documents/{doc_id}/prelabel/llm` returning 202 with a `job_id`; return 422 for a document with no extracted text and 422 for a tenant with no active entity types. Do not modify the existing `/prelabel` endpoint's behavior.
- [ ] 6.5 Add a job-status endpoint (or extend an existing job-status mechanism) so a completed job is observable and its spans retrievable via the existing `/spans?type=suggested` listing.
- [ ] 6.6 Add `tests/test_llm_prelabel_api.py` with `test_trigger_returns_202_with_job_id`, `test_trigger_422_no_extracted_text`, `test_trigger_422_no_entity_types`, `test_llm_prelabel_replaces_existing_suggestions`, `test_trigger_returns_before_llm_completes`, `test_job_status_reflects_completion`, and `test_llm_prelabel_is_tenant_scoped` covering Spec Alignment rows 1-3, 11-13, 16.

## 7. Result Caching

- [ ] 7.1 Implement cache key derivation from (document content hash, tenant entity-config version from task 3.3) and a cache read/write path around the LLM invocation.
- [ ] 7.2 Ensure a cache hit stores/returns suggestions without invoking the LLM client, and that the response indicates the result was served from cache.
- [ ] 7.3 Add `tests/test_llm_prelabel_cache.py` with `test_unchanged_document_and_config_uses_cache` and `test_entity_config_change_invalidates_cache`, asserting LLM client call counts, covering Spec Alignment rows 14-15.

## 8. Source Tracking on the Existing Keyword Path

- [ ] 8.1 Update `prelabel_document` in `src/annotation_service/api/v1/spans.py` to write `source: "keyword"` explicitly on every suggested span it inserts — behavior-neutral otherwise.
- [ ] 8.2 Include `source` in the suggested-spans listing response (`/spans?type=suggested`) and in the LLM trigger's completed-job output.
- [ ] 8.3 Confirm promotion of a suggested span is source-agnostic — no branching on `source` in the promote path.
- [ ] 8.4 Extend `tests/test_annotation_workspace.py` so the existing keyword pre-label test asserts `source: "keyword"`, and add `test_list_suggested_spans_includes_source` and `test_promote_llm_sourced_span`, covering Spec Alignment rows 21-28 (rows 22-25 and 27 are existing regression tests that must continue to pass unchanged).

## 9. Verification & Evidence

- [ ] 9.1 Run all acceptance-criteria tests for every scenario in verification.md § Spec Alignment and confirm all pass.
- [ ] 9.2 Collect functional evidence (screenshot / test output / log) for each scenario — record one entry per row in verification.md § Evidence Log.
- [ ] 9.3 Confirm every Hallucination Risk mitigation step in verification.md § Hallucination Risk Register.
- [ ] 9.4 Confirm all ADR compliance steps in verification.md § Pattern & ADR Compliance.
- [ ] 9.5 Complete Audit Record sign-off in verification.md § Audit Record (human reviewer required — this task cannot be marked complete by an agent).
- [ ] 9.6 Run `openspec validate llm-assisted-prelabeling --type change --strict` and confirm it exits clean before archive.
