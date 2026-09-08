# Verification Plan

**Change:** harden-chat-pipeline-correctness
**Generated:** 2026-08-13
**Status:** 🔴 Incomplete — Evidence Log and Audit Record must be filled by a human reviewer before archive.

---

## 1. Spec Alignment

Map every requirement and every scenario in this change to a testable acceptance criterion.
Each row drives one evidence entry in Section 5.

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | sql-execution-privileges | Generated SQL executes under a least-privilege role | Generated SQL cannot read cross-tenant relations even if validation is bypassed | Given a statement referencing `public.widget_api_keys` admitted past the validator, when it executes on the generated-SQL path, then the database raises insufficient privilege, no row is returned, and the turn records a structured retrieval failure | integration test: `tests/test_sql_execution_privileges.py::test_cross_tenant_relation_denied_by_role` | - [ ] |
| 2 | sql-execution-privileges | Generated SQL executes under a least-privilege role | Legitimate tenant-scoped query succeeds under the restricted role | Given a validated statement joining `document_entities` to `documents` in the caller's schema, when executed under the restricted role, then it succeeds and returns rows identical to those the prior role returned | integration test: `tests/test_sql_execution_privileges.py::test_whitelisted_join_succeeds_under_restricted_role` | - [ ] |
| 3 | sql-execution-privileges | Generated SQL executes under a least-privilege role | Restricted role cannot write | Given an `UPDATE document_entities` statement reaching the database on the generated-SQL path, when executed, then the database rejects it on privileges and the read-only transaction control remains independently in force | integration test: `tests/test_sql_execution_privileges.py::test_write_denied_by_role_and_by_read_only_tx` | - [ ] |
| 4 | sql-execution-privileges | Execution role is server-controlled | Role cannot be selected by generated SQL | Given generated SQL containing `SET ROLE` or `SET SESSION AUTHORIZATION`, when it reaches validation, then it is rejected and no role change reaches the database | unit test: `tests/test_sql_table_whitelist.py::test_role_switch_statements_rejected` | - [ ] |
| 5 | sql-execution-privileges | Execution role is server-controlled | Role is applied without a tool argument | Given the structured retrieval capability's declared argument schema, when inspected at registration, then no argument names a role, user, or connection, and the forbidden-tenancy-argument assertion still rejects `schema`, `tenant_id`, `tenant`, `purpose` | unit test: `tests/test_retrieval_tools.py::test_structured_tool_declares_no_connection_arguments` | - [ ] |
| 6 | chat-api | SQL query generation and validation | Valid SQL query is executed | Given a count question, when generation produces a whitelisted SELECT with a LIMIT, then validation passes, the statement executes read-only, and results reach the pipeline | unit test: `tests/test_chat_api_sql.py::test_valid_select_passes_and_executes` | - [ ] |
| 7 | chat-api | SQL query generation and validation | Malicious SQL is rejected | Given a `DROP TABLE` statement, when validation inspects it, then it is rejected, logged, the SQL source is skipped, and the turn reports the SQL source as unavailable | unit test: `tests/test_chat_api_sql.py::test_ddl_rejected_and_reported_unavailable` | - [ ] |
| 8 | chat-api | SQL query generation and validation | Query with non-whitelisted table is rejected | Given a statement referencing `pg_authid`, when validation inspects the table name, then it is rejected | unit test: `tests/test_sql_table_whitelist.py::test_non_whitelisted_table_rejected` | - [ ] |
| 9 | chat-api | SQL query generation and validation | Comma-joined non-whitelisted table is rejected | Given `SELECT d.filename FROM documents d, public.users u WHERE u.tenant_id <> d.tenant_id LIMIT 10`, when validation inspects it, then it is rejected, the reason names the offending reference, and nothing reaches the database | unit test: `tests/test_sql_table_whitelist.py::test_comma_joined_public_table_rejected` | - [ ] |
| 10 | chat-api | SQL query generation and validation | Non-whitelisted table in a subquery FROM clause is rejected | Given a statement whose subquery selects from a relation outside the whitelist, when validation inspects it, then it is rejected | unit test: `tests/test_sql_table_whitelist.py::test_subquery_non_whitelisted_table_rejected` | - [ ] |
| 11 | chat-api | SQL query generation and validation | Multi-table whitelisted comma join is accepted | Given `SELECT e.entity_value, d.filename FROM document_entities e, documents d WHERE d.id = e.document_id LIMIT 100`, when validation inspects it, then it passes and executes | unit test: `tests/test_sql_table_whitelist.py::test_whitelisted_comma_join_accepted` | - [ ] |
| 12 | chat-api | SQL query generation and validation | Role-switching statement is rejected | Given a statement containing `SET ROLE postgres`, when validation inspects it, then it is rejected | unit test: `tests/test_sql_table_whitelist.py::test_role_switch_statements_rejected` | - [ ] |
| 13 | chat-api | SQL query generation and validation | Query exceeds timeout | Given a statement running longer than 10 seconds, when executed, then execution is cancelled and the SQL source is skipped for the turn | unit test: `tests/test_chat_api_sql.py::test_execution_timeout_cancels_and_skips_source` | - [ ] |
| 14 | chat-api | Guardrail — source citation enforcement | Response with no sources after successful empty retrieval | Given every attempted capability reported `empty` with no error and the reply has no sources, when the guardrail inspects it, then the reply states no matching information was found in the tenant's data, and the event is logged | unit test: `tests/test_chat_api_guardrails.py::test_empty_retrieval_yields_no_match_reply` | - [ ] |
| 15 | chat-api | Guardrail — source citation enforcement | Response with no sources after a retrieval failure | Given at least one capability reported `failed` and the reply has no sources, when the guardrail inspects it, then the reply states a retrieval source failed and the result is incomplete, does not assert absence, and the failing capability name is logged | unit test: `tests/test_chat_api_guardrails.py::test_failed_retrieval_yields_incomplete_reply_not_absence` | - [ ] |
| 16 | chat-api | RAG chat endpoint | Chat with simple entity count query | Given a tenant with ORG entities, when a Tenant Admin posts a count question with a null conversation id, then status is 200 and the body carries `reply`, at least one `sources` entry, and `conversation_id` | integration test: `tests/test_chat_api_conversations.py::test_entity_count_turn_returns_reply_sources_and_conversation_id` | - [ ] |
| 17 | chat-api | RAG chat endpoint | Chat with document context query | Given a tenant with embedded chunks, when a document-content question is asked, then status is 200 and each chunk source carries `document_id`, `chunk_index`, `relevance_score` | integration test: `tests/test_chat_api_conversations.py::test_document_context_turn_returns_chunk_sources` | - [ ] |
| 18 | chat-api | RAG chat endpoint | Response reports per-capability retrieval status | Given a turn where structured retrieval failed and semantic retrieval returned chunks, when the endpoint responds, then status is 200, `retrieval_status` reports `failed` for structured and `ok` for semantic | integration test: `tests/test_chat_api_retrieval_status.py::test_response_reports_per_capability_status` | - [ ] |
| 19 | chat-api | RAG chat endpoint | retrieval_status is additive for existing clients | Given a client deserializing only the pre-existing `ChatResponse` fields, when it receives a response carrying `retrieval_status`, then every prior field retains its shape and meaning and the client functions unmodified | unit test: `tests/test_chat_api_retrieval_status.py::test_retrieval_status_is_additive_to_response_schema` | - [ ] |
| 20 | chat-api | RAG chat endpoint | Chat with existing conversation | Given conversation `conv-abc`, when a message is sent with that id, then status is 200, the message is appended, and prior history appears in the LLM prompt | integration test: `tests/test_chat_api_conversations.py::test_existing_conversation_appends_and_includes_history` | - [ ] |
| 21 | chat-api | RAG chat endpoint | Chat without authentication | Given no JWT, when POSTing to `/api/v1/chat`, then status is 401 | integration test: `tests/test_chat_api_conversations.py::test_unauthenticated_chat_returns_401` | - [ ] |
| 22 | retrieval-orchestration | Per-invocation retrieval status | One of two structured invocations fails | Given two structured entries where the first raises and the second returns rows, when the plan executes, then the first reports `failed` with its error text, the second reports `ok`, and the second's rows are accumulated | unit test: `tests/test_retrieval_orchestrator.py::test_partial_structured_failure_reported_per_entry` | - [ ] |
| 23 | retrieval-orchestration | Per-invocation retrieval status | Rejected entry is distinguishable from a failed one | Given an entry rejected at validation and never dispatched, when the plan executes, then it reports `not_attempted` and not `empty` | unit test: `tests/test_retrieval_orchestrator.py::test_rejected_entry_reports_not_attempted` | - [ ] |
| 24 | retrieval-orchestration | Per-invocation retrieval status | Legitimate empty result is distinguishable from failure | Given a structured entry whose validated query matched no rows, when the plan executes, then it reports `empty` with no error text | unit test: `tests/test_retrieval_orchestrator.py::test_zero_row_success_reports_empty_without_error` | - [ ] |
| 25 | retrieval-orchestration | Per-invocation retrieval status | Underlying error text survives accumulation | Given a structured entry failing with a specific database error, when the orchestration result is produced, then the entry retains that specific detail and is not replaced by a generic all-failed string | unit test: `tests/test_retrieval_orchestrator.py::test_specific_error_text_survives_accumulation` | - [ ] |
| 26 | retrieval-orchestration | Retrieval status reaches the answer model | Failed structured retrieval is visible in the prompt | Given a turn whose only structured entry failed, when the prompt is assembled, then it contains a retrieval-status statement naming structured as failed and does not present the turn as having no matching data | unit test: `tests/test_context_assembler.py::test_failed_structured_status_rendered_into_prompt` | - [ ] |
| 27 | retrieval-orchestration | Retrieval status reaches the answer model | Fully successful turn carries no failure statement | Given every capability reported `ok` or `empty`, when the prompt is assembled, then it contains no failure statement | unit test: `tests/test_context_assembler.py::test_clean_turn_has_no_failure_statement` | - [ ] |
| 28 | retrieval-orchestration | Retrieval status reaches the answer model | Degraded planning is surfaced rather than silent | Given a turn where planning raised and the fallback plan was substituted, when the turn completes, then the status records the degradation and stop reason and both are readable by prompt assembly and the response payload | integration test: `tests/test_chat_api_retrieval_status.py::test_degraded_planning_surfaces_in_prompt_and_response` | - [ ] |
| 29 | retrieval-orchestration | Bounded structured-to-semantic recovery | Structured-only plan returning nothing recovers semantically | Given a plan with one structured entry and no semantic entry that matched no rows, when dispatch completes, then exactly one semantic invocation runs on the original question, its chunks are accumulated, and it appears in the status | unit test: `tests/test_orchestrator_recovery.py::test_structured_only_empty_triggers_one_semantic_recovery` | - [ ] |
| 30 | retrieval-orchestration | Bounded structured-to-semantic recovery | Recovery is not attempted when a semantic entry already ran | Given a plan with both a structured and a semantic entry where structured returned nothing, when execution completes, then no additional semantic invocation is made | unit test: `tests/test_orchestrator_recovery.py::test_no_recovery_when_semantic_entry_present` | - [ ] |
| 31 | retrieval-orchestration | Bounded structured-to-semantic recovery | Recovery is not attempted when structured retrieval failed rather than emptied | Given a plan whose only structured entry reported `failed`, when execution completes, then the failure is reported in the status and the original failure and the recovery outcome are recorded separately | unit test: `tests/test_orchestrator_recovery.py::test_failed_structured_records_failure_and_recovery_separately` | - [ ] |
| 32 | retrieval-orchestration | Bounded structured-to-semantic recovery | Recovery is skipped when the remaining budget is insufficient | Given a structured-only plan returning no rows and less than the configured minimum budget remaining, when recovery would fire, then it is skipped, the status records the skip and reason, and the skip is not represented as an empty result | unit test: `tests/test_orchestrator_recovery.py::test_recovery_skipped_below_min_budget_records_skip` | - [ ] |
| 33 | retrieval-orchestration | Bounded structured-to-semantic recovery | Recovery is at most one invocation | Given a structured-only plan returning no rows and a recovery invocation that also returns no chunks, when execution completes, then no further retrieval invocation is made | unit test: `tests/test_orchestrator_recovery.py::test_recovery_runs_at_most_once` | - [ ] |
| 34 | retrieval-orchestration | Consistent cross-invocation score semantics | Reranked and fallback results merge on a comparable basis | Given two semantic invocations where one returns reranker scores and the other fusion scores, when chunks are merged and ordered, then ordering uses one normalised scale and no chunk outranks another solely due to its scoring basis | unit test: `tests/test_retrieval_orchestrator.py::test_mixed_scale_invocations_merge_on_normalised_rank` | - [ ] |
| 35 | retrieval-orchestration | Consistent cross-invocation score semantics | Single-invocation ordering is unchanged | Given a plan with exactly one semantic invocation, when chunks are ordered, then the relative order equals the retriever's order | unit test: `tests/test_retrieval_orchestrator.py::test_single_invocation_order_preserved` | - [ ] |
| 36 | retrieval-orchestration | Conjunctive and multi-source planning contract | Conjunctive question yields one composed structured invocation | Given "Find backend engineers with AWS and Kubernetes experience", when the planner produces a plan, then it does not contain two independent structured entries each carrying one condition, and the conditions are carried by a single structured invocation | eval case: `tests/test_retrieval_query_class_eval.py::test_conjunctive_question_plan_shape` | - [ ] |
| 37 | retrieval-orchestration | Conjunctive and multi-source planning contract | Enumeration question is planned with both capabilities | Given a question asking which documents or subjects mention a named value, when the planner produces a plan, then it contains both a structured and a semantic entry | eval case: `tests/test_retrieval_query_class_eval.py::test_enumeration_question_plans_both_capabilities` | - [ ] |
| 38 | retrieval-orchestration | Conjunctive and multi-source planning contract | Plan shape is observable for evaluation | Given any planned turn, when its trace is inspected, then every entry's capability name and argument keys are recorded, and entries discarded by the invocation cap carry their discard reason | unit test: `tests/test_retrieval_orchestrator.py::test_plan_trace_records_shape_and_discard_reasons` | - [ ] |
| 39 | retrieval-orchestration | Structural document-scope enforcement for structured retrieval | Scope is applied as a constraint, not a suggestion | Given a turn resolved to a document set, when structured retrieval executes, then the executed statement constrains `document_id` to that set without depending on the generating model honouring prose | unit test: `tests/test_chat_api_structured_scope.py::test_document_scope_applied_as_bound_predicate` | - [ ] |
| 40 | retrieval-orchestration | Structural document-scope enforcement for structured retrieval | Out-of-scope rows cannot consume the row budget | Given an unconstrained query that would fill the row limit before reaching the in-scope document, and a turn resolved to that document, when structured retrieval executes, then the in-scope rows are returned and the result is not empty because out-of-scope rows filled the limit | integration test: `tests/test_chat_api_structured_scope.py::test_scope_applied_before_row_limit_truncation` | - [ ] |
| 41 | entity-resolution | Multi-subject resolution scopes to every matched document | Two named subjects both resolve | Given person entities for "Girish" in D1 and "Arjun Jayakumar" in D2, when the user asks to compare them, then the outcome carries D1 and D2, the semantic scope lists both, and the structured constraint lists both | unit test: `tests/test_entity_resolver.py::test_two_named_subjects_resolve_to_union` | - [ ] |
| 42 | entity-resolution | Multi-subject resolution scopes to every matched document | One named subject resolves and another does not | Given a person entity for "Girish" and none matching "Hannah", when the user asks to compare them, then the turn is not treated as a unique single-document match excluding the unmatched subject, retrieval can still surface evidence for it, and the prompt does not contain evidence for only one of the two | integration test: `tests/test_entity_resolution_graph.py::test_partially_resolved_comparison_does_not_exclude_unmatched_subject` | - [ ] |
| 43 | entity-resolution | Multi-subject resolution scopes to every matched document | Single named subject still resolves uniquely | Given exactly one person entity matching "Girish" in D1, when the user asks about Girish, then the outcome carries exactly D1 and the plan is scoped to D1, unchanged from prior single-subject behaviour | unit test: `tests/test_entity_resolver.py::test_single_subject_resolution_unchanged` | - [ ] |
| 44 | entity-resolution | Multi-subject resolution scopes to every matched document | Ambiguity within one mention still requests clarification | Given two distinct people whose stored names both match "Girish", when the user asks about Girish, then the clarification reply listing candidates is returned and the turn terminates without retrieval | integration test: `tests/test_entity_resolution_graph.py::test_single_mention_ambiguity_still_clarifies` | - [ ] |
| 45 | entity-resolution | Multi-subject resolution scopes to every matched document | Union above the candidate cap falls back to narrowing | Given distinct mentions resolving to more documents than `entity_resolution_max_candidates`, when resolution completes, then the narrowing reply is returned and no arbitrary subset is scoped | unit test: `tests/test_entity_resolver.py::test_union_over_cap_returns_narrowing` | - [ ] |
| 46 | entity-resolution | Multi-subject resolution scopes to every matched document | Single-character mentions do not contribute to the union | Given a stored person name containing a single-character token and a message containing that character as a standalone word naming no person, when mentions are evaluated, then that mention contributes no document and the outcome is unresolved if nothing else matches | unit test: `tests/test_entity_resolver_mentions.py::test_single_character_mention_excluded_from_union` | - [ ] |
| 47 | entity-resolution | Plan rewriting preserves every resolved document | Semantic scope receives the full set | Given an outcome carrying D1 and D2, when the plan is rewritten, then every semantic entry's scope lists both | unit test: `tests/test_entity_resolution_graph.py::test_rewrite_sets_semantic_scope_to_full_set` | - [ ] |
| 48 | entity-resolution | Plan rewriting preserves every resolved document | Structured constraint receives the full set | Given an outcome carrying D1 and D2, when the plan is rewritten, then every structured entry is constrained to both | unit test: `tests/test_entity_resolution_graph.py::test_rewrite_sets_structured_constraint_to_full_set` | - [ ] |
| 49 | entity-resolution | Plan rewriting preserves every resolved document | Post-execution row filter respects the full set | Given an outcome carrying D1 and D2 and structured rows from both, when the resolved-document filter runs, then rows from both are retained | unit test: `tests/test_entity_resolution_graph.py::test_post_filter_retains_all_resolved_documents` | - [ ] |
| 50 | entity-resolution | Plan rewriting preserves every resolved document | Anaphoric follow-up inherits the full bound set | Given a prior turn resolved to D1 and D2 and a follow-up containing an anaphoric reference and no new mention, when resolution runs, then the plan is scoped to both | integration test: `tests/test_chat_api_entity_resolution.py::test_anaphoric_followup_inherits_full_bound_set` | - [ ] |
| 51 | sql-query-recovery | Wrong-entity-type defect detection | Value exists under a different entity type | Given a tenant holding `aws` only under `TOOL_FRAMEWORK` and a validated statement filtering `PROGRAMMING_LANGUAGE` with `normalized_value = 'aws'`, when it returns zero rows, then the attempt is classified a retryable defect identifying the literal and the type it actually occurs under | unit test: `tests/test_chat_api_sql_retry.py::test_value_under_other_entity_type_is_a_defect` | - [ ] |
| 52 | sql-query-recovery | Wrong-entity-type defect detection | Defect feedback names the correct entity type | Given an attempt classified with a wrong-entity-type defect for `aws`, when the retry prompt renders, then the feedback states the literal occurs under the other type and includes the failing statement | unit test: `tests/test_chat_api_sql_retry.py::test_defect_feedback_names_actual_entity_type` | - [ ] |
| 53 | sql-query-recovery | Wrong-entity-type defect detection | Retry budget is spent on the defect | Given a first attempt classified with a wrong-entity-type defect and remaining attempts and budget, when the loop continues, then a second attempt is generated with the feedback and the loop does not terminate as success on the zero-row first attempt | integration test: `tests/test_chat_api_sql_retry_integration.py::test_wrong_type_defect_consumes_retry_budget` | - [ ] |
| 54 | sql-query-recovery | Wrong-entity-type defect detection | Genuinely absent value is not a defect | Given a literal occurring under no entity type and a statement returning zero rows, when classified, then it is a success with zero rows and no retry is triggered by row count alone | unit test: `tests/test_chat_api_sql_retry.py::test_absent_value_zero_rows_is_success` | - [ ] |
| 55 | sql-query-recovery | Wrong-entity-type defect detection | Detection does not fire when the tenant profile is unavailable | Given an unfetchable entity profile and a statement returning zero rows, when classified, then it is a success with zero rows and the unavailable profile is not read as evidence of absence | unit test: `tests/test_chat_api_sql_retry.py::test_missing_profile_does_not_produce_defect` | - [ ] |
| 56 | sql-query-recovery | Structured retrieval reports result completeness | Truncated result is reported as incomplete | Given a query matching 142 rows under a limit of 100, when it executes, then the result reports 100 returned and 142 matched and is marked truncated | integration test: `tests/test_chat_api_sql.py::test_truncated_result_reports_returned_and_matched` | - [ ] |
| 57 | sql-query-recovery | Structured retrieval reports result completeness | Complete result is reported as complete | Given a query matching 12 rows under a limit of 100, when it executes, then the result reports 12 and 12 and is not marked truncated | integration test: `tests/test_chat_api_sql.py::test_complete_result_not_marked_truncated` | - [ ] |
| 58 | sql-query-recovery | Structured retrieval reports result completeness | Completeness reporting does not change returned rows | Given any executed statement, when completeness is determined, then the rows handed to the caller are identical to those returned and the row limit is unchanged | unit test: `tests/test_chat_api_sql.py::test_completeness_reporting_does_not_alter_rows_or_limit` | - [ ] |
| 59 | sql-query-recovery | Failed recovery is reported, never laundered into an empty result | Exhausted attempts propagate as failure | Given a recovery loop whose every attempt failed, when it terminates, then the caller observes a failure carrying the attempts and not an empty successful result | unit test: `tests/test_chat_api_sql_retry.py::test_all_attempts_failed_raises_not_empty` | - [ ] |
| 60 | sql-query-recovery | Failed recovery is reported, never laundered into an empty result | Deadline-abandoned recovery is distinguishable from exhausted attempts | Given a failed first attempt and an already-exhausted deadline, when the loop terminates, then the failure identifies deadline exhaustion and the trace records the attempts actually made | unit test: `tests/test_chat_api_sql_retry.py::test_deadline_abandon_distinguishable_from_exhaustion` | - [ ] |
| 61 | sql-query-recovery | Failed recovery is reported, never laundered into an empty result | Per-attempt trace reaches the turn's status | Given a structured invocation that failed after multiple attempts, when the turn's retrieval status is produced, then it carries the per-attempt outcomes for that invocation | integration test: `tests/test_chat_api_sql_retry_integration.py::test_attempt_trace_reaches_retrieval_status` | - [ ] |
| 62 | context-assembly | Structured evidence degrades by truncation, never by silent omission | Oversized structured result is truncated, not dropped | Given a structured result costing more tokens than remain, when the prompt is assembled, then a structured block is present, contains as many complete rows as the budget admits, and states it was truncated | unit test: `tests/test_context_assembler.py::test_oversized_structured_result_truncates_not_drops` | - [ ] |
| 63 | context-assembly | Structured evidence degrades by truncation, never by silent omission | Fitting structured result is admitted whole | Given a structured result fitting the budget, when assembled, then every row appears and no truncation is stated | unit test: `tests/test_context_assembler.py::test_fitting_structured_result_admitted_whole` | - [ ] |
| 64 | context-assembly | Structured evidence degrades by truncation, never by silent omission | Structured evidence retains budget ahead of chunks | Given both structured rows and chunks and a budget insufficient for both, when assembled, then at least one structured row is admitted and chunks are not admitted while the structured block is omitted entirely | unit test: `tests/test_context_assembler.py::test_structured_rows_reserved_ahead_of_chunks` | - [ ] |
| 65 | context-assembly | Exhaustiveness claims match what was admitted | Row-limit truncation suppresses the exhaustiveness claim | Given a result reporting 100 of 142 matched, when assembled, then the prompt states the listing is partial with the matched total and does not instruct the model to report the block as the complete set | unit test: `tests/test_context_assembler.py::test_row_limit_truncation_suppresses_exhaustiveness_claim` | - [ ] |
| 66 | context-assembly | Exhaustiveness claims match what was admitted | Complete result retains the exhaustiveness instruction | Given a result reporting 12 of 12 admitted without assembler truncation, when assembled, then the prompt instructs the model to report every distinct value | unit test: `tests/test_context_assembler.py::test_complete_result_retains_exhaustiveness_instruction` | - [ ] |
| 67 | context-assembly | Exhaustiveness claims match what was admitted | Assembler truncation also suppresses the claim | Given a complete query result truncated by the assembler, when assembled, then the prompt states the listing is partial | unit test: `tests/test_context_assembler.py::test_assembler_truncation_suppresses_claim` | - [ ] |
| 68 | context-assembly | Duplicate structured values are collapsed before rendering | Identical rows from the same document collapse | Given four rows identical in every rendered field, when the block renders, then one such row appears | unit test: `tests/test_context_assembler.py::test_identical_rendered_rows_collapse` | - [ ] |
| 69 | context-assembly | Duplicate structured values are collapsed before rendering | Same value from different documents does not collapse | Given two rows with the same entity value but different source documents, when the block renders, then both appear with their own source | unit test: `tests/test_context_assembler.py::test_same_value_different_documents_not_collapsed` | - [ ] |
| 70 | context-assembly | Duplicate structured values are collapsed before rendering | Collapse is reflected in the completeness statement | Given a result whose rows collapse to fewer distinct ones, when the block renders, then the completeness statement uses the matched total, not the post-collapse count, as the basis for partiality | unit test: `tests/test_context_assembler.py::test_completeness_statement_uses_matched_total_after_collapse` | - [ ] |
| 71 | context-assembly | Citations are derived from admitted evidence | Omitted structured evidence yields no structured citation | Given a turn whose structured block was omitted or fully truncated away, when citations are produced, then none claims structured evidence the prompt lacked | unit test: `tests/test_context_assembly_path_equivalence.py::test_no_structured_citation_when_block_absent` | - [ ] |
| 72 | context-assembly | Citations are derived from admitted evidence | Every admitted chunk is citable | Given a prompt that admitted five chunks, when citations are produced, then the citation set covers those five and is not reduced by a cap unrelated to admission | unit test: `tests/test_context_assembly_path_equivalence.py::test_citations_cover_every_admitted_chunk` | - [ ] |
| 73 | context-assembly | Citations are derived from admitted evidence | Structured citation reflects the admitted rows | Given a structured block truncated to a subset, when the structured citation is produced, then it represents the admitted subset and indicates the underlying result was larger | unit test: `tests/test_context_assembly_path_equivalence.py::test_structured_citation_matches_admitted_subset` | - [ ] |
| 74 | context-assembly | Retrieval status is rendered into the prompt | Failure statement is rendered | Given a turn whose structured capability reported `failed`, when assembled, then the prompt contains a retrieval-status statement naming structured as failed | unit test: `tests/test_context_assembler.py::test_failure_status_statement_rendered` | - [ ] |
| 75 | context-assembly | Retrieval status is rendered into the prompt | Skipped recovery is rendered | Given a turn whose semantic recovery was skipped for budget, when assembled, then the prompt states a recovery step was skipped | unit test: `tests/test_context_assembler.py::test_skipped_recovery_statement_rendered` | - [ ] |
| 76 | context-assembly | Retrieval status is rendered into the prompt | Clean turn renders no status block | Given every capability `ok` or `empty` and no planning degradation, when assembled, then no retrieval-status block appears | unit test: `tests/test_context_assembler.py::test_clean_turn_renders_no_status_block` | - [ ] |
| 77 | context-assembly | Retrieval status is rendered into the prompt | Status block does not displace evidence | Given a turn with a status block and retrievable evidence, when assembled, then the block's token cost is accounted for in the budget and admitted evidence still respects the total budget | unit test: `tests/test_context_assembler.py::test_status_block_cost_counted_in_budget` | - [ ] |
| 78 | context-assembly | Chunk caps are independently configurable | Prompt chunk cap is set independently of retrieval top-k | Given a configuration where retrieval top-k and the prompt chunk cap differ, when a turn is assembled, then admitted chunks follow the prompt cap and per-invocation retrieval follows top-k | unit test: `tests/test_retrieval_config.py::test_prompt_chunk_cap_independent_of_top_k` | - [ ] |
| 79 | context-assembly | Chunk caps are independently configurable | Citation cap is not hardcoded | Given the source-assembly stage, when it selects chunk citations, then the count comes from a named setting and not a literal at the call site | unit test: `tests/test_retrieval_config.py::test_citation_cap_is_a_named_setting` | - [ ] |
| 80 | context-assembly | Chunk caps are independently configurable | Defaults preserve existing behaviour where unchanged | Given a deployment setting none of the new settings, when a turn is assembled, then each setting takes its documented default and the defaults match those recorded in design.md | unit test: `tests/test_env_config.py::test_new_chunk_cap_defaults_match_design` | - [ ] |
| 81 | retrieval-eval | Degraded and failed queries score zero | Orchestrator failure scores zero | Given a golden-set query whose orchestrated run reported a retrieval failure, when metrics are computed, then it contributes zero to every metric and is counted in the denominator | unit test: `tests/test_retrieval_eval_runner.py::test_orchestrator_failure_scores_zero_and_counts` | - [ ] |
| 82 | retrieval-eval | Degraded and failed queries score zero | Degraded planning scores zero | Given a query whose run substituted the degraded fallback plan, when metrics are computed, then it contributes zero and the run records degradation | unit test: `tests/test_retrieval_eval_runner.py::test_degraded_planning_scores_zero` | - [ ] |
| 83 | retrieval-eval | Degraded and failed queries score zero | Aggregate reports failure counts alongside scores | Given a run containing successful and failed queries, when the aggregate is produced, then it reports degraded and failed counts and the score is computed over every dispatched query | unit test: `tests/test_retrieval_eval_runner.py::test_aggregate_reports_failure_counts` | - [ ] |
| 84 | retrieval-eval | Degraded and failed queries score zero | Baseline is regenerated for the new scoring rule | Given a baseline produced under the prior skip-based scoring, when the gate compares a run under the new rule, then the comparison uses a baseline regenerated under the new rule and the baseline metadata identifies its scoring rule | unit test: `tests/test_retrieval_eval_gate.py::test_gate_requires_baseline_matching_scoring_rule` | - [ ] |
| 85 | retrieval-eval | Answer-level correctness evaluation | Answer containing the required facts passes | Given an answer-level case naming a question and required facts, when the reply contains every required fact, then the case passes | eval test: `tests/test_retrieval_answer_eval.py::test_case_passes_when_all_required_facts_present` | - [ ] |
| 86 | retrieval-eval | Answer-level correctness evaluation | Answer omitting a required fact fails | Given a case whose required facts include a value the reply omits, when evaluated, then the case fails and the report names the omitted fact | eval test: `tests/test_retrieval_answer_eval.py::test_case_fails_and_names_omitted_fact` | - [ ] |
| 87 | retrieval-eval | Answer-level correctness evaluation | Answer asserting absence of retrievable data fails | Given a case whose required fact exists in the tenant's data and a reply stating it could not be found, when evaluated, then the case fails | eval test: `tests/test_retrieval_answer_eval.py::test_false_absence_claim_fails_the_case` | - [ ] |
| 88 | retrieval-eval | Query-class evaluation coverage | Multi-document comparison is covered | Given the eval suite, when cases are enumerated, then at least one names two subjects and requires facts about both, and fails if the reply carries evidence for only one | eval test: `tests/test_retrieval_query_class_eval.py::test_multi_document_comparison_case_present_and_strict` | - [ ] |
| 89 | retrieval-eval | Query-class evaluation coverage | Multi-condition question is covered | Given the eval suite, when cases are enumerated, then at least one carries AND-composing conditions and records the orchestrator's plan shape | eval test: `tests/test_retrieval_query_class_eval.py::test_multi_condition_case_records_plan_shape` | - [ ] |
| 90 | retrieval-eval | Query-class evaluation coverage | Failed-retrieval turn is covered | Given a case constructed so structured retrieval fails, when evaluated, then it asserts the reply does not claim absence and that the retrieval status reports the failure | eval test: `tests/test_retrieval_query_class_eval.py::test_failed_retrieval_case_asserts_no_absence_claim` | - [ ] |
| 91 | retrieval-eval | Query-class evaluation coverage | Every class has at least one case | Given the enumerated query classes, when the suite is validated, then each maps to at least one case and a class with none fails validation | unit test: `tests/test_retrieval_query_class_eval.py::test_every_query_class_has_a_case` | - [ ] |
| 92 | retrieval-eval | Evaluation runs against tenant-representative data | Run identifies its corpus | Given any completed eval run, when its report is produced, then the report names the corpus used | unit test: `tests/test_retrieval_eval.py::test_report_names_corpus` | - [ ] |
| 93 | retrieval-eval | Evaluation runs against tenant-representative data | Synthetic-fixture score is not a tenant claim | Given a run against the synthetic fixture corpus, when compared against a tenant-corpus baseline, then the comparison is rejected and the rejection names the corpus mismatch | unit test: `tests/test_retrieval_eval_gate.py::test_corpus_mismatch_rejected` | - [ ] |
| 94 | retrieval-eval | Evaluation runs against tenant-representative data | Tenant-corpus run is reproducible from configuration | Given a tenant-corpus eval configuration, when the run is repeated with the same configuration, then corpus selection and query set are identical between runs | unit test: `tests/test_retrieval_eval.py::test_tenant_corpus_run_is_reproducible` | - [ ] |

> **Rule:** Every `#### Scenario:` block in every `specs/**/*.md` file for this change
> MUST appear as a row in this table. A missing scenario is a P1 gap that blocks archive.

---

## 2. Hallucination Risk Register

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|-------------------|----------------------|
| 1 | Table-reference resolution (design Decision 1) | An agent may "fix" the whitelist by adding a second `re.findall` for comma-joined tables while leaving the original first-identifier-only scans in place, so `FROM a, b JOIN c, d` is still only partially covered. It may also silently admit schema-qualified names by stripping the qualifier instead of rejecting the reference. | Read the final `validate_sql` and confirm there is exactly one routine that enumerates table references and that every reference flows through it. Manually run the four rejection cases and the one acceptance case from rows 8–12 and confirm the reason strings name the offending reference. Confirm a schema-qualified name is *rejected*, not normalised. |
| 2 | `RetrievalStatus` producer without a reader (design Decision 3) | The defect being repaired is precisely a written-but-unread state field. An agent may add `RetrievalStatus` to `ChatState` and to `_accumulate` but wire only one of the three required consumers (assembler, guardrail, response), reproducing the original bug in a new shape. It may also leave `sql_error` / `retrieval_error` in place "for compatibility". | Grep for the new status field and confirm at least three distinct read sites outside the writing node. Grep for `sql_error` and `retrieval_error` and confirm zero remaining occurrences in `src/`. Confirm the eval runner was updated rather than left referencing removed fields. |
| 3 | Multi-document resolution (design Decision 4) | An agent may change `_rewrite_plan_for_resolution` to accept a list but keep `resolve_entity`'s first-match-wins `winning` selection, so the list always has one member and the P0 survives with passing type signatures. It may also drop the single-character mention gate as an "edge case". | Run row 41 against real data and confirm the resolved set has two members, not one. Read `resolve_entity` and confirm mention selection iterates all matched mentions. Confirm the single-character gate exists and row 46 covers it. |
| 4 | Bounded recovery becoming a loop (design Decision 5, proposal non-goal) | An agent may generalise the single fallback invocation into a retry loop, a second planning call, or a recursive "keep trying capabilities until something returns" construct — reintroducing the retired agentic loop the proposal explicitly excludes. | Read the recovery code path and confirm it is a single unconditional invocation with no loop, no recursion, and no planner call. Confirm row 33 asserts at-most-once and that it fails if the code is made iterative. |
| 5 | Node reordering (design Decision 7) | An agent may add nodes, add a conditional edge, or merge `prompt_assembly` and `source_assembly` rather than reordering two edges — changing the topology the proposal preserves. It may also leave `source_assembly` recomputing its own chunk slice instead of consuming admitted evidence. | Diff `builder.py` and confirm the node set and both routing predicates are unchanged and only edge wiring moved. Confirm `source_assembly` reads admitted evidence from state and contains no independent slice or budget calculation. |
| 6 | Exhaustiveness and truncation (design Decision 8) | An agent may implement truncation but leave the original "authoritative and exhaustive" sentence unconditionally in `SYSTEM_PROMPT`, so the model still claims completeness over a partial block — the exact defect Finding 8 describes. It may also collapse duplicates on the entity value alone, destroying per-document provenance. | Read the assembled prompt for a truncated case (row 65) and confirm the exhaustiveness sentence is absent and a partial-listing statement is present. Confirm the collapse key is the full rendered row by checking row 69 fails if the key is narrowed to the value. |
| 7 | Eval scoring change (design Migration step 7) | An agent may change the runner to score zero but not regenerate `baseline.json`, leaving the gate red and tempting a tolerance increase instead. It may also record the new baseline without noting the scoring rule, making future comparisons silently incomparable. | Confirm `baseline.json` was regenerated in this change and its metadata records both the scoring rule and the corpus. Confirm the gate tolerance was not loosened to accommodate the new scoring. |

---

## 3. Pattern & ADR Compliance

| ADR | Decision Summary | Constraint on This Change | Verification Step |
|-----|-----------------|--------------------------|-------------------|
| ADR-001-tenant-data-isolation | Tenant data isolated via separate database schemas | The least-privilege role must reinforce schema isolation, never substitute for it. `schema` must continue to be bound from authenticated request context and never derived from generated SQL or tool arguments. | Grep `sql_generator.py` and `nodes.py` for every assignment to `schema` and confirm each traces to request state. Confirm `assert_no_tenancy_params` still rejects `schema`, `tenant_id`, `tenant`, `purpose` (row 5). Run row 1 and confirm the cross-tenant read fails on privileges. |
| ADR-003-model-serving-topology | Per-tenant model serving | Unchanged. The reranker continues to call model-serving over HTTP with the caller's token; no serving-topology change is introduced. | Diff `reranker.py` and `retriever.py` and confirm no change to the model-serving call, its URL construction, or its auth header. |
| ADR-004-openspec-governance | Spec-driven development governance | Every behavioural change lands as a delta spec with scenarios; verification.md gates archive. | Run `openspec validate harden-chat-pipeline-correctness` and confirm it passes. Confirm every scenario in `specs/**/*.md` appears in Section 1. |
| ADR-007-chatbot-architecture | Full RAG with SQL validation, citation enforcement, tenant scoping, disclaimer, rate limiting, P95 < 10s | SQL validation, citation enforcement, and tenant scoping are strengthened, not relaxed. The recovery invocation must fit the existing retrieval deadline so the P95 target is not breached. | Confirm no validation rule was removed (compare `validate_sql` rejection set before and after). Confirm the disclaimer and rate-limiting paths are untouched. Review the eval latency report per query class and confirm P95 remains under the target with recovery enabled (rows 29, 32). |

---

## 4. Evidence Requirements

Evidence that **MUST** be collected and logged in Section 5 before this change is archived.
Do not archive while any item below remains unchecked.

### Functional Evidence

*(One item per row in Section 1 — test output, log excerpt, or API trace proving the THEN was observed in a real execution.)*

- [ ] Row 1 — integration test output showing the cross-tenant read denied on privileges under the restricted role
- [ ] Row 2 — test output showing identical rows returned under the restricted and prior roles for the same statement
- [ ] Row 3 — test output showing the write rejected on privileges
- [ ] Row 4 — test output showing `SET ROLE` / `SET SESSION AUTHORIZATION` rejected at validation
- [ ] Row 5 — test output showing the structured tool's argument schema declares no connection/role argument
- [ ] Row 6 — test output showing a whitelisted SELECT validated and executed read-only
- [ ] Row 7 — test output showing DDL rejected, logged, and the SQL source reported unavailable
- [ ] Row 8 — test output showing `pg_authid` rejected
- [ ] Row 9 — test output showing the comma-joined `public.users` statement rejected with the offending reference named
- [ ] Row 10 — test output showing a subquery referencing a non-whitelisted relation rejected
- [ ] Row 11 — test output showing the whitelisted comma join accepted and executed
- [ ] Row 12 — test output showing `SET ROLE postgres` rejected
- [ ] Row 13 — test output showing execution cancelled at the timeout and the source skipped
- [ ] Row 14 — test output showing the no-match reply on an all-empty turn
- [ ] Row 15 — test output showing the incomplete-result reply on a failed turn, asserting no absence claim
- [ ] Row 16 — API trace of a 200 response carrying `reply`, `sources`, `conversation_id`
- [ ] Row 17 — API trace showing chunk sources with `document_id`, `chunk_index`, `relevance_score`
- [ ] Row 18 — API trace showing `retrieval_status` with `failed` for structured and `ok` for semantic
- [ ] Row 19 — test output showing a legacy-shaped client deserializes the response unchanged
- [ ] Row 20 — API trace showing the turn appended to `conv-abc` and prior history present in the prompt
- [ ] Row 21 — API trace showing 401 without a JWT
- [ ] Row 22 — test output showing per-entry `failed` and `ok` with the second entry's rows accumulated
- [ ] Row 23 — test output showing a rejected entry reports `not_attempted`
- [ ] Row 24 — test output showing a zero-row success reports `empty` with no error
- [ ] Row 25 — test output showing the specific database error text present in the entry status
- [ ] Row 26 — captured prompt showing the retrieval-status statement naming structured as failed
- [ ] Row 27 — captured prompt from a clean turn showing no failure statement
- [ ] Row 28 — API trace and captured prompt showing degraded planning and its stop reason
- [ ] Row 29 — test output showing exactly one recovery invocation with the original question and its chunks accumulated
- [ ] Row 30 — test output showing no recovery when a semantic entry was already planned
- [ ] Row 31 — test output showing the original failure and the recovery outcome recorded separately
- [ ] Row 32 — test output showing recovery skipped below the minimum budget with the skip recorded
- [ ] Row 33 — test output showing no second recovery invocation after an empty recovery
- [ ] Row 34 — test output showing mixed-scale invocations ordered on a single normalised basis
- [ ] Row 35 — test output showing single-invocation order matches the retriever's order
- [ ] Row 36 — eval report showing the conjunctive question produced one composed structured invocation
- [ ] Row 37 — eval report showing the enumeration question planned both capabilities
- [ ] Row 38 — test output showing plan trace records capability names, argument keys, and discard reasons
- [ ] Row 39 — captured executed statement showing the bound `document_id` predicate
- [ ] Row 40 — integration output showing in-scope rows returned despite a limit-filling unconstrained result
- [ ] Row 41 — test output showing both D1 and D2 in the resolved set and in both capability arguments
- [ ] Row 42 — captured prompt for the partially-resolved comparison showing evidence is not restricted to the matched subject
- [ ] Row 43 — test output showing single-subject resolution unchanged
- [ ] Row 44 — test output showing the clarification reply and no retrieval
- [ ] Row 45 — test output showing the narrowing reply above the candidate cap
- [ ] Row 46 — test output showing a single-character mention contributes no document
- [ ] Row 47 — test output showing semantic scope carries the full set
- [ ] Row 48 — test output showing the structured constraint carries the full set
- [ ] Row 49 — test output showing the post-filter retains rows from every resolved document
- [ ] Row 50 — integration output showing an anaphoric follow-up scoped to the full bound set
- [ ] Row 51 — test output showing the wrong-entity-type defect raised for `aws`
- [ ] Row 52 — captured retry prompt showing the correct entity type named and the failing statement included
- [ ] Row 53 — integration output showing a second attempt generated from the defect feedback
- [ ] Row 54 — test output showing a genuinely absent value classified as zero-row success
- [ ] Row 55 — test output showing no defect raised when the profile is unavailable
- [ ] Row 56 — integration output showing 100 returned of 142 matched, marked truncated
- [ ] Row 57 — integration output showing 12 of 12, not truncated
- [ ] Row 58 — test output showing rows and limit unchanged by completeness reporting
- [ ] Row 59 — test output showing exhausted attempts raise rather than return empty
- [ ] Row 60 — test output distinguishing deadline abandonment from attempt exhaustion
- [ ] Row 61 — integration output showing per-attempt outcomes present in the turn status
- [ ] Row 62 — captured prompt showing a truncated structured block with its truncation statement
- [ ] Row 63 — captured prompt showing a fitting result admitted whole with no truncation statement
- [ ] Row 64 — captured prompt showing at least one structured row admitted under a constrained budget
- [ ] Row 65 — captured prompt showing the partial-listing statement and absence of the exhaustiveness sentence
- [ ] Row 66 — captured prompt showing the exhaustiveness instruction retained for a complete result
- [ ] Row 67 — captured prompt showing the partial statement after assembler-side truncation
- [ ] Row 68 — captured block showing four identical rows rendered once
- [ ] Row 69 — captured block showing the same value from two documents rendered twice with distinct sources
- [ ] Row 70 — captured block showing the completeness statement based on the matched total
- [ ] Row 71 — captured citations showing no structured citation when the block was absent
- [ ] Row 72 — captured citations covering all five admitted chunks
- [ ] Row 73 — captured structured citation matching the admitted subset and indicating a larger result
- [ ] Row 74 — captured prompt showing the failure statement naming the structured capability
- [ ] Row 75 — captured prompt showing the skipped-recovery statement
- [ ] Row 76 — captured prompt from a clean turn showing no status block
- [ ] Row 77 — test output showing the status block's tokens counted against the budget
- [ ] Row 78 — test output showing prompt cap and retrieval top-k taking effect independently
- [ ] Row 79 — test output showing the citation cap read from a named setting
- [ ] Row 80 — test output showing the four defaults match the values recorded in design.md Decision 9
- [ ] Row 81 — eval output showing an orchestrator failure scored zero and counted
- [ ] Row 82 — eval output showing degraded planning scored zero
- [ ] Row 83 — eval report showing degraded and failed counts alongside the aggregate
- [ ] Row 84 — gate output showing a baseline mismatch on scoring rule rejected
- [ ] Row 85 — eval output showing a fully-answered case passing
- [ ] Row 86 — eval output showing a case failing and naming the omitted fact
- [ ] Row 87 — eval output showing a false-absence reply failing its case
- [ ] Row 88 — eval output for the multi-document comparison case, failing on single-subject evidence
- [ ] Row 89 — eval output for the multi-condition case including the recorded plan shape
- [ ] Row 90 — eval output for the failed-retrieval case asserting no absence claim and a reported failure
- [ ] Row 91 — suite validation output showing every query class mapped to a case
- [ ] Row 92 — eval report showing the corpus named
- [ ] Row 93 — gate output showing a corpus mismatch rejected
- [ ] Row 94 — two eval runs from one configuration showing identical corpus selection and query set

### Structural Evidence

- [ ] Code review completed — implementation matches design.md decisions (no undocumented deviations)
- [ ] All ADR compliance steps in Section 3 confirmed ✓
- [ ] No undocumented architectural patterns introduced
- [ ] No AI-invented requirements present in generated code (cross-checked against spec files)
- [x] `builder.py` diff confirms node set and routing predicates unchanged; only the `prompt_assembly` / `source_assembly` edge order moved — E6
- [x] `grep -r "sql_error\|retrieval_error" src/` returns no results — E6
- [x] No new runtime dependency added to `pyproject.toml` — E6
- [x] No migration added under `alembic/versions/` — E6

### Edge Case Evidence

- [x] Risk 1 mitigation confirmed — single table-reference routine verified; schema-qualified names rejected rather than normalised — E1, E6
- [x] Risk 2 mitigation confirmed — at least three read sites for the new status field; no residual `sql_error` / `retrieval_error` — E6
- [x] Risk 3 mitigation confirmed — resolved set contains two members for the real comparison query; mention selection iterates all matches — E3
- [x] Risk 4 mitigation confirmed — recovery path contains no loop, recursion, or planner call — E4, E6
- [x] Risk 5 mitigation confirmed — `source_assembly` contains no independent slice or budget calculation — E5, E6
- [x] Risk 6 mitigation confirmed — exhaustiveness sentence conditional; collapse key is the full rendered row — E5
- [x] Risk 7 mitigation confirmed — `baseline.json` regenerated with scoring-rule and corpus metadata; gate tolerance unchanged — E7

---

## 5. Evidence Log

Record collected evidence here. Every row in Section 1 must have at least one matching
entry. Do not pre-fill — entries must describe real observations.

Entries E1–E8 are observations from the implementation run. They record what was
executed and what it returned; they are **not** reviewer confirmations. The Section 4
Functional Evidence checkboxes and the Section 6 Audit Record remain the human gate.

Test environment note: the repository's `tests/conftest.py` defaults to
`localhost:54320`, and on the machine used here host port 5432 is held by a native
Postgres that shadows the Docker one. Runs below used the Docker `postgres-test`
container reached on a forwarded port, with `NER_DATABASE_URL` pointed at
`ner_test`.

| # | Evidence Type | Description / Link | Scenario(s) Covered | Collected By | Date |
|---|--------------|-------------------|---------------------|--------------|------|
| E1 | Test output | `pytest tests/test_sql_table_whitelist.py tests/test_sql_execution_privileges.py tests/test_chat_api_sql.py tests/test_sql_filename_defect.py tests/test_sql_generator_document_name_fix.py` — all passed. Comma-joined `public.widget_api_keys` rejected naming the offending reference; schema-qualified `public.documents` rejected, not normalised; whitelisted comma join still accepted; `SET ROLE` / `SET SESSION AUTHORIZATION` rejected. Restricted-role tests ran against a live schema: cross-tenant read denied on privileges, identical rows returned under both roles, write denied by role and independently by the read-only transaction. | Rows 1–5, 8–12 | implementation run | 2026-08-13 |
| E2 | Test output | `pytest tests/test_retrieval_orchestrator.py tests/test_context_assembler.py tests/test_chat_api_guardrails.py tests/test_chat_api_retrieval_status.py` — all passed. Per-entry status for partial failure, `not_attempted` for rejected entries, `empty` distinguished from `failed`, specific error text preserved; status rendered into the prompt and charged against the budget; guardrail returns distinct replies for empty vs failed; `retrieval_status` present on the HTTP response and omitted (not null) when the turn never retrieved. | Rows 14, 15, 18, 19, 22–28, 38, 74–77 | implementation run | 2026-08-13 |
| E3 | Test output | `pytest tests/test_entity_resolver.py tests/test_entity_resolver_mentions.py tests/test_entity_resolution_graph.py tests/test_chat_api_entity_resolution.py tests/test_entity_resolution_flag_off.py` — all passed. "Compare Girish and Arjun Jayakumar" resolves to a two-member union against a live tenant schema; single-subject resolution unchanged; union over cap returns narrowing; single-character mention excluded; both capabilities receive the full set; anaphoric follow-up inherits both documents. | Rows 41–50 | implementation run | 2026-08-13 |
| E4 | Test output | `pytest tests/test_chat_api_sql_retry.py tests/test_chat_api_sql_retry_integration.py tests/test_orchestrator_recovery.py tests/test_chat_api_structured_scope.py` — all passed. Wrong-entity-type defect detected and retried, feedback names the actual type, absent value stays a success, missing profile produces no defect; completeness reports returned/matched/truncated without altering rows or the row limit; recovery fires exactly once, is skipped with a reason below the budget threshold, and records failure and recovery as separate entries; document scope applied as a bound `ANY(:ids)` predicate inside the source. | Rows 6, 7, 13, 29–33, 39, 40, 51–61 | implementation run | 2026-08-13 |
| E5 | Test output | `pytest tests/test_context_assembler.py tests/test_context_assembly_path_equivalence.py tests/test_retrieval_config.py tests/test_env_config.py::test_new_chunk_cap_defaults_match_design tests/test_chat_graph_topology.py` — all passed. Oversized structured result truncates rather than dropping; exhaustiveness instruction replaced by the partial-listing instruction on both truncation paths; duplicates collapse on the full rendered row while the same value from two documents survives; citations cover every admitted chunk and the structured citation matches the admitted subset; four chunk caps independently configurable at the documented defaults. | Rows 34, 35, 62–73, 78–80 | implementation run | 2026-08-13 |
| E6 | Static analysis | Structural greps and `git diff`: exactly one table-reference routine (`iter_table_references`) feeding one whitelist check; zero code references to `sql_error` / `retrieval_error` in `src/` (comments only); six `retrieval_status` read sites across assembler, guardrail, and response; no `[:3]` or `sql_results[:5]` in `nodes.py`; recovery path is a single guarded invocation with no loop, recursion, or planner call; `builder.py` diff is three edge lines plus docstring, node set and both routing predicates unchanged; `pyproject.toml` unchanged; no file added under `alembic/versions/`. | Structural + Edge Case evidence | implementation run | 2026-08-13 |
| E7 | Eval run + artifact | `python scripts/run_retrieval_eval.py --k 5 --write-baseline` against the live test database. Regenerated `tests/fixtures/retrieval_eval/baseline.json` now records `scoring_rule: zero-degraded` and `corpus: synthetic-fixture` with `degraded_count: 0`, `failed_count: 0`; metric values are identical to the prior baseline because every query in this deterministic fixture succeeds, so the two scoring rules agree here. Gate tolerance unchanged at 0.02. Report now carries a per-query-class latency table. | Rows 81–84, 92–94 | implementation run | 2026-08-13 |
| E8 | Test output | `pytest tests/test_retrieval_answer_eval.py tests/test_retrieval_query_class_eval.py tests/test_retrieval_eval_runner.py tests/test_retrieval_eval_gate.py tests/test_retrieval_eval.py` — all passed. Answer-level cases pass on required facts, fail naming the omitted fact, and fail on a false absence claim; all eight query classes have a case and an uncovered class fails suite validation; conjunctive and multi-source plan shapes asserted from the trace; gate rejects a baseline whose scoring rule or corpus differs. | Rows 36, 37, 85–91 | implementation run | 2026-08-13 |

**Known gap — not evidence, a stated absence.** The ADR-007 P95 confirmation in
Section 3 is **not** covered above. Per-query-class latency is now recorded in the eval
report, but the committed harness runs offline against precomputed embeddings with no
planner or generation LLM call, and its structured-only recovery path never fires on a
document-content corpus. Those numbers therefore say nothing about production P95. A
live run against a tenant-representative corpus with recovery enabled is required before
this item can be checked. Task 7.12 is left open for the same reason.

---

## 6. Audit Record

> ⚠️ **GATE: This section must be completed and signed by a human reviewer before
> `/opsx:archive` is run.** An unsigned or incomplete Audit Record is a hard block on archive.

**Change slug:** harden-chat-pipeline-correctness
**Proposal:** `openspec/changes/harden-chat-pipeline-correctness/proposal.md`
**Spec files reviewed:**

- specs/sql-execution-privileges/spec.md
- specs/chat-api/spec.md
- specs/retrieval-orchestration/spec.md
- specs/entity-resolution/spec.md
- specs/sql-query-recovery/spec.md
- specs/context-assembly/spec.md
- specs/retrieval-eval/spec.md

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

**Archive approved by:** ___________________________

**Date:** ___________

**Notes:**
<!-- Any observations, caveats, or follow-up items for future changes. -->
