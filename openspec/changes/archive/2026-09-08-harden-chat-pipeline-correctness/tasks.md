# Tasks — Harden chat pipeline correctness

Groups are ordered by dependency and follow design.md § Migration Plan. Groups 1–2 are the
security repair and ship independently. Group 3 is the load-bearing contract every later
group reads. Groups 4–6 are the correctness, orchestration, and retrieval repairs. Group 7
is evaluation. Group 8 is the verification gate.

## 1. Security — table-reference resolution

- [x] 1.1 Add a single routine in `src/chat_api/services/sql_generator.py` that enumerates every table reference in a statement: extract each `SELECT`'s `FROM` clause, split the comma-separated table list, strip `AS` and bare aliases, and yield each reference. Replace both existing `re.findall(r'\bFROM\s+(\w+)')` / `\bJOIN\s+(\w+)` scans and the separate subquery scan so exactly one routine feeds the whitelist check (design Decision 1).
- [x] 1.2 Reject any reference that is not a bare identifier present in `WHITELISTED_TABLES`. Schema-qualified names SHALL be rejected, never normalised by stripping the qualifier. Include the offending reference in the `SQLValidationError` message.
- [x] 1.3 Add `SET ROLE` and `SET SESSION AUTHORIZATION` to the disallowed-statement checks in `validate_sql`.
- [x] 1.4 Create `tests/test_sql_table_whitelist.py` with `test_non_whitelisted_table_rejected`, `test_comma_joined_public_table_rejected`, `test_subquery_non_whitelisted_table_rejected`, `test_whitelisted_comma_join_accepted`, `test_role_switch_statements_rejected` (verification rows 8, 9, 10, 11, 12, 4).
- [x] 1.5 Run the existing `tests/test_chat_api_sql.py`, `tests/test_sql_filename_defect.py`, and `tests/test_sql_generator_document_name_fix.py` suites and confirm no previously-accepted legitimate statement shape is now rejected.

## 2. Security — least-privilege execution role

- [x] 2.1 Define the restricted role and its grants: `SELECT` on the tables named in `WHITELISTED_TABLES` within tenant schemas, and no grants on any `public` relation. Derive the grant list from `WHITELISTED_TABLES` rather than restating it (design Decision 2).
- [x] 2.2 Apply the role in `SQLGenerator.execute_sql` via `SET LOCAL ROLE` inside the existing `BEGIN READ ONLY` transaction, so it cannot outlive the statement or leak across the connection. Do not change the read-only transaction control itself.
- [x] 2.3 Add a configuration toggle in `src/shared/config.py` selecting between the current connection role and the restricted role, so step 2.2 is revertable without a redeploy (design § Migration Plan step 2).
- [x] 2.4 Add `tests/test_sql_execution_privileges.py` with `test_cross_tenant_relation_denied_by_role`, `test_whitelisted_join_succeeds_under_restricted_role`, `test_write_denied_by_role_and_by_read_only_tx` (verification rows 1, 2, 3).
- [x] 2.5 Add `test_structured_tool_declares_no_connection_arguments` to `tests/test_retrieval_tools.py`, asserting the structured capability's `args_schema` declares no role/user/connection argument and that `assert_no_tenancy_params` still rejects `schema`, `tenant_id`, `tenant`, `purpose` (verification row 5).
- [x] 2.6 Run a read-only smoke query per tenant schema under the restricted role before enabling the toggle in any environment.

## 3. Error contract — RetrievalStatus end to end

- [x] 3.1 Define `RetrievalStatus` in `src/shared/retrieval/orchestrator.py`: one entry per plan entry carrying `capability_name`, `outcome` ∈ {`not_attempted`, `ok`, `empty`, `failed`, `skipped`}, `error`, `result_count`, and the per-attempt diagnostics; plus turn-level `planning_degraded` and `stop_reason` (design Decision 3).
- [x] 3.2 Populate it in `_accumulate` / `execute_plan`. Preserve the specific error text per entry — do not replace it with a generic all-invocations-failed string, and do not gate the signal on every invocation of a kind having failed.
- [x] 3.3 Replace `sql_error` and `retrieval_error` in `src/chat_api/graph/state.py` with the status field. Update `retrieval_execution_node` and `orchestrator_node` to write it, including the degraded-fallback paths.
- [x] 3.4 Thread the status into `ContextAssembler.assemble()` and render a `Retrieval status:` block when any capability reported `failed` or `skipped`, or planning degraded. Charge its tokens against the budget (design Decision 3; verification rows 26, 27, 74, 75, 76, 77).
- [x] 3.5 Thread the status into `GuardrailService.enforce_sources` and branch: all-empty yields a no-match reply; any failure or skip yields an incomplete-result reply that does not assert absence. Leave the clarification exemption untouched (design Decision 11).
- [x] 3.6 Add the additive `retrieval_status` field to `ChatResponse` in `src/chat_api/api/v1/schemas.py` and populate it in `src/chat_api/api/v1/chat.py` for both the JSON and streaming routes. No existing field changes shape.
- [x] 3.7 Update `src/shared/retrieval/eval/runner.py` to read the new status instead of the removed fields.
- [x] 3.8 Add `test_partial_structured_failure_reported_per_entry`, `test_rejected_entry_reports_not_attempted`, `test_zero_row_success_reports_empty_without_error`, `test_specific_error_text_survives_accumulation`, `test_plan_trace_records_shape_and_discard_reasons` to `tests/test_retrieval_orchestrator.py` (verification rows 22, 23, 24, 25, 38).
- [x] 3.9 Add `test_failed_structured_status_rendered_into_prompt`, `test_clean_turn_has_no_failure_statement`, `test_failure_status_statement_rendered`, `test_skipped_recovery_statement_rendered`, `test_clean_turn_renders_no_status_block`, `test_status_block_cost_counted_in_budget` to `tests/test_context_assembler.py` (verification rows 26, 27, 74, 75, 76, 77).
- [x] 3.10 Add `test_empty_retrieval_yields_no_match_reply` and `test_failed_retrieval_yields_incomplete_reply_not_absence` to `tests/test_chat_api_guardrails.py` (verification rows 14, 15).
- [x] 3.11 Create `tests/test_chat_api_retrieval_status.py` with `test_response_reports_per_capability_status`, `test_retrieval_status_is_additive_to_response_schema`, `test_degraded_planning_surfaces_in_prompt_and_response` (verification rows 18, 19, 28).
- [x] 3.12 Confirm `grep -r "sql_error\|retrieval_error" src/` returns nothing.

## 4. Correctness — multi-subject entity resolution

- [x] 4.1 Extend `ResolutionResult` in `src/chat_api/services/entity_resolver.py` with `resolved_document_ids: list[str]` and a per-mention breakdown (design Decision 4).
- [x] 4.2 Change `resolve_entity` to evaluate every distinct mention that matched rather than stopping at the first `winning` mention, and return the union of their documents. Keep `AMBIGUOUS` meaning one mention matching several people; apply `OVER_CAP` to the union size.
- [x] 4.3 Exclude single-character mentions from contributing to the union.
- [x] 4.4 Change `_rewrite_plan_for_resolution` in `src/chat_api/graph/nodes.py` to take `document_ids: list[str]` and apply the whole set to every affected entry. Update every call site, including the pending-clarification resume path and the anaphoric-inheritance path.
- [x] 4.5 Update the resolved-document post-filter in `retrieval_execution_node` to retain rows from every resolved document.
- [x] 4.6 Add `test_two_named_subjects_resolve_to_union`, `test_single_subject_resolution_unchanged`, `test_union_over_cap_returns_narrowing` to `tests/test_entity_resolver.py` (verification rows 41, 43, 45).
- [x] 4.7 Add `test_single_character_mention_excluded_from_union` to `tests/test_entity_resolver_mentions.py` (verification row 46).
- [x] 4.8 Add `test_partially_resolved_comparison_does_not_exclude_unmatched_subject`, `test_single_mention_ambiguity_still_clarifies`, `test_rewrite_sets_semantic_scope_to_full_set`, `test_rewrite_sets_structured_constraint_to_full_set`, `test_post_filter_retains_all_resolved_documents` to `tests/test_entity_resolution_graph.py` (verification rows 42, 44, 47, 48, 49).
- [x] 4.9 Add `test_anaphoric_followup_inherits_full_bound_set` to `tests/test_chat_api_entity_resolution.py` (verification row 50).
- [x] 4.10 Run `tests/test_entity_resolution_flag_off.py` and confirm the flag-off path is unaffected.

## 5. Correctness — SQL defect detection, completeness, and recovery

- [x] 5.1 Add a wrong-entity-type defect check in `src/chat_api/services/sql_generator.py`: after a validated statement returns zero rows and no existing defect matched, test whether a literal compared against `normalized_value` occurs under a different `entity_type`. Return no defect when the entity profile is unavailable (design Decision; spec `sql-query-recovery`).
- [x] 5.2 Extend `_render_attempt_feedback` to state the entity type the literal actually occurs under, alongside the failing statement.
- [x] 5.3 Report result completeness from structured retrieval: fetch one row beyond the limit to detect truncation cheaply, compute the exact matched total only when truncated (inside the existing read-only transaction and its timeout), and report it as unknown if that count fails. Do not change the returned rows or the row limit.
- [x] 5.4 Surface `returned`, `matched`, and `truncated` through `ToolResult` from `src/shared/retrieval/tools/entity_tools.py` so context assembly can read them.
- [x] 5.5 Implement bounded structured-to-semantic recovery in `execute_plan`: when the plan contained no `semantic_retrieval` entry and every `structured_retrieval` entry reported `empty` or `failed`, issue exactly one `semantic_retrieval` call on the turn's original question. No loop, no recursion, no planner call (design Decision 5).
- [x] 5.6 Add `retrieval_recovery_min_budget_seconds` (default `2.0`) to `src/shared/config.py`. Skip recovery below it and record `skipped` with a reason. Count the recovery invocation against `orchestrator_max_invocations`.
- [x] 5.7 Apply the resolved document scope to structured retrieval as a bound `document_id = ANY(:ids)` predicate wrapping the validated statement, replacing the appended natural-language hint. Retain the post-execution filter as a secondary check only (design Decision 10).
- [x] 5.8 Add `test_value_under_other_entity_type_is_a_defect`, `test_defect_feedback_names_actual_entity_type`, `test_absent_value_zero_rows_is_success`, `test_missing_profile_does_not_produce_defect`, `test_all_attempts_failed_raises_not_empty`, `test_deadline_abandon_distinguishable_from_exhaustion` to `tests/test_chat_api_sql_retry.py` (verification rows 51, 52, 54, 55, 59, 60).
- [x] 5.9 Add `test_wrong_type_defect_consumes_retry_budget` and `test_attempt_trace_reaches_retrieval_status` to `tests/test_chat_api_sql_retry_integration.py` (verification rows 53, 61).
- [x] 5.10 Add `test_truncated_result_reports_returned_and_matched`, `test_complete_result_not_marked_truncated`, `test_completeness_reporting_does_not_alter_rows_or_limit`, `test_valid_select_passes_and_executes`, `test_ddl_rejected_and_reported_unavailable`, `test_execution_timeout_cancels_and_skips_source` to `tests/test_chat_api_sql.py` (verification rows 56, 57, 58, 6, 7, 13).
- [x] 5.11 Create `tests/test_orchestrator_recovery.py` with `test_structured_only_empty_triggers_one_semantic_recovery`, `test_no_recovery_when_semantic_entry_present`, `test_failed_structured_records_failure_and_recovery_separately`, `test_recovery_skipped_below_min_budget_records_skip`, `test_recovery_runs_at_most_once` (verification rows 29, 30, 31, 32, 33).
- [x] 5.12 Create `tests/test_chat_api_structured_scope.py` with `test_document_scope_applied_as_bound_predicate` and `test_scope_applied_before_row_limit_truncation` (verification rows 39, 40).

## 6. Retrieval and context assembly

- [x] 6.1 Normalise chunk scores to a rank-derived basis per invocation before cross-invocation merge in `_accumulate`, retaining the raw score and its basis for display. Single-invocation ordering must be unchanged by construction (design Decision 6).
- [x] 6.2 Add `retrieval_merge_max_chunks` (default `10`), change `context_max_chunks` to default `8` independently of `retrieval_top_k`, and add `citation_max_chunks` (default `8`) in `src/shared/config.py`. Replace the hardcoded `[:3]` in `source_assembly_node` with `citation_max_chunks` (design Decision 9).
- [x] 6.3 Change `ContextAssembler.assemble()` to admit the structured block by whole rows until the budget is exhausted, after collapsing exact duplicate rendered rows keyed on the full row, and to render an explicit `showing N of M matched rows` statement. Guarantee at least one structured row (design Decision 8).
- [x] 6.4 Make the `SYSTEM_PROMPT` exhaustiveness instruction conditional: replace it with a partial-listing instruction whenever the query was row-limit truncated or the assembler truncated the block.
- [x] 6.5 Change `ContextAssembler.assemble()` to return the admitted evidence — which chunks, which rows, and whether either was truncated — alongside the messages.
- [x] 6.6 Reorder the edges in `src/chat_api/graph/builder.py` to `retrieval_execution → prompt_assembly → source_assembly → generation`. Move document-name resolution into `prompt_assembly_node`. Do not add, remove, or merge nodes, and do not change either routing predicate (design Decision 7).
- [x] 6.7 Change `source_assembly_node` to build citations from `admitted_evidence` and `document_names` in state, removing its independent chunk slice and its `sql_results[:5]` value construction.
- [x] 6.8 Update `tests/test_chat_graph_topology.py` for the new edge order in the same commit as 6.6.
- [x] 6.9 Add `test_oversized_structured_result_truncates_not_drops`, `test_fitting_structured_result_admitted_whole`, `test_structured_rows_reserved_ahead_of_chunks`, `test_row_limit_truncation_suppresses_exhaustiveness_claim`, `test_complete_result_retains_exhaustiveness_instruction`, `test_assembler_truncation_suppresses_claim`, `test_identical_rendered_rows_collapse`, `test_same_value_different_documents_not_collapsed`, `test_completeness_statement_uses_matched_total_after_collapse` to `tests/test_context_assembler.py` (verification rows 62–70).
- [x] 6.10 Add `test_no_structured_citation_when_block_absent`, `test_citations_cover_every_admitted_chunk`, `test_structured_citation_matches_admitted_subset` to `tests/test_context_assembly_path_equivalence.py` (verification rows 71, 72, 73).
- [x] 6.11 Add `test_mixed_scale_invocations_merge_on_normalised_rank` and `test_single_invocation_order_preserved` to `tests/test_retrieval_orchestrator.py` (verification rows 34, 35).
- [x] 6.12 Add `test_prompt_chunk_cap_independent_of_top_k` and `test_citation_cap_is_a_named_setting` to `tests/test_retrieval_config.py`, and `test_new_chunk_cap_defaults_match_design` to `tests/test_env_config.py` (verification rows 78, 79, 80).
- [x] 6.13 Add `test_entity_count_turn_returns_reply_sources_and_conversation_id`, `test_document_context_turn_returns_chunk_sources`, `test_existing_conversation_appends_and_includes_history`, `test_unauthenticated_chat_returns_401` to `tests/test_chat_api_conversations.py` (verification rows 16, 17, 20, 21).
- [x] 6.14 Run `tests/test_chat_api_streaming.py`, `tests/test_chat_api_reranking.py`, `tests/test_hybrid_retrieval.py`, `tests/test_reranking_retriever.py` and confirm the preserved components are unaffected.

## 7. Orchestration contract and evaluation

- [x] 7.1 Amend `ORCHESTRATION_SYSTEM_PROMPT` so a question whose conditions compose with AND is expressed as one structured invocation carrying every condition, and so enumeration and identity questions plan both capabilities. Do not add a plan-rewriting layer (design Decision 12).
- [x] 7.2 Change `src/shared/retrieval/eval/runner.py` and `metrics.py` so degraded, errored, and abandoned queries score zero and are counted in the aggregate denominator, instead of being marked `skipped` and excluded from the mean.
- [x] 7.3 Report degraded and failed counts in the aggregate produced by `metrics.aggregate`.
- [x] 7.4 Record the scoring rule and the corpus in eval report and baseline metadata; make `gate.check_regression` reject a comparison whose baseline scoring rule or corpus does not match the run.
- [x] 7.5 Create `tests/test_retrieval_answer_eval.py` — an answer-level harness where each case names a question and the facts the reply must contain — with `test_case_passes_when_all_required_facts_present`, `test_case_fails_and_names_omitted_fact`, `test_false_absence_claim_fails_the_case` (verification rows 85, 86, 87).
- [x] 7.6 Create `tests/test_retrieval_query_class_eval.py` covering the eight investigated query classes, with `test_conjunctive_question_plan_shape`, `test_enumeration_question_plans_both_capabilities`, `test_multi_document_comparison_case_present_and_strict`, `test_multi_condition_case_records_plan_shape`, `test_failed_retrieval_case_asserts_no_absence_claim`, `test_every_query_class_has_a_case` (verification rows 36, 37, 88, 89, 90, 91).
- [x] 7.7 Add `test_orchestrator_failure_scores_zero_and_counts`, `test_degraded_planning_scores_zero`, `test_aggregate_reports_failure_counts` to `tests/test_retrieval_eval_runner.py` (verification rows 81, 82, 83).
- [x] 7.8 Add `test_gate_requires_baseline_matching_scoring_rule` and `test_corpus_mismatch_rejected` to `tests/test_retrieval_eval_gate.py` (verification rows 84, 93).
- [x] 7.9 Add `test_report_names_corpus` and `test_tenant_corpus_run_is_reproducible` to `tests/test_retrieval_eval.py` (verification rows 92, 94).
- [x] 7.10 Add a tenant-representative eval corpus configuration alongside the existing synthetic fixture, without removing the fixture.
- [x] 7.11 Regenerate `tests/fixtures/retrieval_eval/baseline.json` under the new zero-scoring rule, recording the scoring rule and corpus in its metadata. Do not loosen the gate tolerance to accommodate the new scoring.
- [ ] 7.12 Record per-query-class latency in the eval report and confirm P95 remains within the ADR-007 target with recovery enabled.

## 8. Verification & Evidence

- [x] 8.1 Run all acceptance-criteria tests for every scenario in verification.md § Spec Alignment and confirm all pass.
- [ ] 8.2 Collect functional evidence (test output / captured prompt / API trace / eval report) for each scenario — record one entry per row in verification.md § Evidence Log.
- [x] 8.3 Confirm every Hallucination Risk mitigation step in verification.md § Hallucination Risk Register, including the structural checks: single table-reference routine, three or more status read sites, no residual `sql_error` / `retrieval_error`, no loop in the recovery path, no independent slice in `source_assembly`, conditional exhaustiveness sentence, regenerated baseline.
- [x] 8.4 Confirm all ADR compliance steps in verification.md § Pattern & ADR Compliance, including that no validation rule was removed and no new runtime dependency or migration was added.
- [ ] 8.5 Complete Audit Record sign-off in verification.md § Audit Record (human reviewer required — this task cannot be marked complete by an agent).
- [x] 8.6 Run `openspec validate harden-chat-pipeline-correctness --type change --strict` and confirm it exits clean before archive.
