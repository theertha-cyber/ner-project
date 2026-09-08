# Verification Plan

**Change:** bounded-sql-retry-loop
**Generated:** 2026-08-10
**Status:** 🔴 Incomplete — Evidence Log and Audit Record must be filled by a human reviewer before archive.

---

## 1. Spec Alignment

Map every requirement and every scenario in this change to a testable acceptance criterion.
Each row drives one evidence entry in Section 5.

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | sql-query-recovery | Bounded SQL attempt loop | Successful first attempt makes exactly one generation call | Given an attempt cap of 3, when the first generated query validates, executes, and returns rows, then those rows are returned and exactly one generation call and one execution occurred | `tests/test_chat_api_sql_retry.py::TestLoopBounds::test_successful_first_attempt_makes_one_generation_call` | - [x] |
| 2 | sql-query-recovery | Bounded SQL attempt loop | Loop stops at the configured attempt cap | Given an attempt cap of 3 and a generator that always fails, when the third attempt fails, then no fourth generation call and no fourth execution occur | `tests/test_chat_api_sql_retry.py::TestLoopBounds::test_three_failures_stop_at_cap` | - [x] |
| 3 | sql-query-recovery | Bounded SQL attempt loop | Attempt cap of 1 reproduces single-pass behaviour | Given `sql_max_attempts` is 1, when the first attempt fails validation, then no second generation call occurs and the invocation reports failure | `tests/test_chat_api_sql_retry.py::TestLoopBounds::test_max_attempts_one_makes_single_pass` | - [x] |
| 4 | sql-query-recovery | Bounded SQL attempt loop | Loop stops early when the retrieval deadline has passed | Given an attempt failed and the tool-context deadline has elapsed, when a further attempt is considered, then no further generation call occurs and the invocation reports failure | `tests/test_chat_api_sql_retry.py::TestLoopBounds::test_elapsed_deadline_stops_loop`; guard `::test_live_deadline_does_not_stop_loop` | - [x] |
| 5 | sql-query-recovery | Attempt outcome classification | Validation failure is classified and retried | Given a first query referencing a non-whitelisted table, when validation rejects it, then the attempt is classified `validation_error`, the query is not executed, and a second attempt is made | `tests/test_chat_api_sql_retry.py::TestOutcomeClassification::test_validation_error_retried` | - [x] |
| 6 | sql-query-recovery | Attempt outcome classification | Execution failure is classified and retried | Given a first query that passes validation and raises an undefined-column error, when the attempt completes, then it is classified `execution_error`, a second attempt is made, and a successful second attempt returns its rows | `tests/test_chat_api_sql_retry.py::TestOutcomeClassification::test_execution_error_retried_and_second_succeeds` | - [x] |
| 7 | sql-query-recovery | Attempt outcome classification | Generation failure is classified and retried | Given the generation call raises or returns unusable text, when the attempt completes, then it is classified `generation_error` and a second attempt is made | `tests/test_chat_api_sql_retry.py::TestOutcomeClassification::test_generation_error_retried`, `::test_empty_generation_output_is_a_generation_error` | - [x] |
| 8 | sql-query-recovery | Zero rows is a legitimate result unless a deterministic defect explains it | Unexplained empty result is not retried | Given a query that validates, executes cleanly, returns zero rows, and names only existing entity types, when the attempt completes, then it is classified `success`, no second generation call occurs, and an empty result is returned without error | `tests/test_chat_api_sql_retry.py::TestEmptyResultPolicy::test_unexplained_empty_not_retried` | - [x] |
| 9 | sql-query-recovery | Zero rows is a legitimate result unless a deterministic defect explains it | Empty result caused by a nonexistent entity type is retried | Given tenant types `PER`/`ORG`/`SKILL` and a first query filtering `entity_type = 'EMPLOYER'` returning zero rows, when the attempt completes, then it is classified `empty_with_defect`, a second attempt is made, and its rows are returned on success | `tests/test_chat_api_sql_retry.py::TestEmptyResultPolicy::test_empty_with_unknown_entity_type_retried` | - [x] |
| 10 | sql-query-recovery | Zero rows is a legitimate result unless a deterministic defect explains it | Non-empty result is never retried | Given a query returning at least one row, when the attempt completes, then it is classified `success` regardless of other signals and no further generation call occurs | `tests/test_chat_api_sql_retry.py::TestEmptyResultPolicy::test_non_empty_never_retried`; defect-signal units `test_defect_detection_*` (5) | - [x] |
| 11 | sql-query-recovery | Previous-attempt feedback is supplied to the generator | Retry prompt contains the previous SQL and its failure reason | Given the first attempt failed with a database error, when the second attempt's prompt is constructed, then it contains the first attempt's SQL, a sanitized failure description, and a corrective instruction | `tests/test_chat_api_sql_retry.py::TestFeedback::test_retry_prompt_contains_previous_sql_and_reason`, `::test_retry_prompt_carries_validation_rejection` | - [x] |
| 12 | sql-query-recovery | Previous-attempt feedback is supplied to the generator | Bound parameters are stripped from error feedback | Given a database error whose message appends the statement and bound parameters, when it is rendered into feedback, then the appended statement and parameter echo are absent and the text is truncated to the configured budget | `tests/test_chat_api_sql_retry.py::TestFeedback::test_sanitizer_strips_sql_and_parameter_echo`, `::test_sanitizer_truncates_to_budget`, `::test_sanitizer_names_the_exception_type` | - [x] |
| 13 | sql-query-recovery | Previous-attempt feedback is supplied to the generator | Empty-result feedback states the row count and the defect | Given a first attempt that returned zero rows because it filtered on a nonexistent entity type, when the second prompt is constructed, then it states zero rows were returned and names the offending entity-type literal | `tests/test_chat_api_sql_retry.py::TestFeedback::test_empty_defect_feedback_names_entity_type` | - [x] |
| 14 | sql-query-recovery | Bounded tenant entity profile in the generation context | Sample values appear in the generation context | Given a tenant whose `SKILL` entities include values such as `python`, when the generation prompt is constructed, then it lists `SKILL` with a bounded sample of its actual values | `tests/test_chat_api_sql_retry.py::TestEntityProfile::test_profile_samples_in_prompt` | - [x] |
| 15 | sql-query-recovery | Bounded tenant entity profile in the generation context | Sample size is bounded per type and in total | Given a tenant with many types and many distinct values, when the profile is fetched, then no type contributes more than the per-type cap and the total does not exceed the overall cap | `tests/test_chat_api_sql_retry.py::TestEntityProfile::test_profile_caps_per_type_and_total`, `::test_profile_truncates_long_sample_values` | - [x] |
| 16 | sql-query-recovery | Bounded tenant entity profile in the generation context | Entity types with no sampled values are still listed | Given an entity type whose rows all have NULL normalized values, when the prompt is constructed, then that type still appears in the available entity types | `tests/test_chat_api_sql_retry.py::TestEntityProfile::test_null_valued_type_still_listed` | - [x] |
| 17 | sql-query-recovery | Bounded tenant entity profile in the generation context | Profile is fetched once per invocation | Given an invocation requiring three attempts, when the loop completes, then the entity-profile queries executed once, not once per attempt | `tests/test_chat_api_sql_retry.py::TestEntityProfile::test_profile_fetched_once_per_invocation` | - [x] |
| 18 | sql-query-recovery | Tenant isolation and validation hold across every attempt | Every retried query is validated | Given attempts 1 and 2 failed and attempt 3 is generated, when attempt 3 is processed, then its SQL passed through the validation layer before execution | `tests/test_chat_api_sql_retry.py::TestSecurityInvariants::test_every_retry_is_validated` | - [x] |
| 19 | sql-query-recovery | Tenant isolation and validation hold across every attempt | A retry cannot escape the table whitelist | Given a retry whose SQL references a non-whitelisted table, when the attempt is processed, then validation rejects it and the query is not executed | `tests/test_chat_api_sql_retry.py::TestSecurityInvariants::test_retry_cannot_escape_whitelist` | - [x] |
| 20 | sql-query-recovery | Tenant isolation and validation hold across every attempt | Retries execute against the schema from request context | Given an invocation for a schema supplied by request context, when three attempts are made, then every attempt executed against that schema and none against a schema named in generated SQL or in the question | `tests/test_chat_api_sql_retry.py::TestSecurityInvariants::test_all_attempts_use_request_context_schema`, `::TestToolBoundary::test_tool_context_schema_reaches_the_generator` | - [x] |
| 21 | sql-query-recovery | Tenant isolation and validation hold across every attempt | Retries remain read-only | Given any retry attempt, when it is executed, then it uses the same read-only transaction path and timeout as the first attempt | `tests/test_chat_api_sql_retry.py::TestSecurityInvariants::test_retries_use_read_only_path` | - [x] |
| 22 | sql-query-recovery | Exhausted retries report failure rather than an empty result | Exhausted retries surface as a structured-retrieval error | Given an invocation whose every attempt fails, when the loop terminates, then the structured-retrieval capability reports an error result and the turn's structured-retrieval error state is populated | `tests/test_chat_api_sql_retry.py::TestToolBoundary::test_exhausted_retries_surface_tool_error` | - [x] |
| 23 | sql-query-recovery | Exhausted retries report failure rather than an empty result | A legitimate empty result is not reported as an error | Given a first attempt that succeeds with zero rows, when the invocation completes, then the capability reports a successful result with no rows and no error | `tests/test_chat_api_sql_retry.py::TestToolBoundary::test_legitimate_empty_is_not_an_error` | - [x] |
| 24 | sql-query-recovery | Exhausted retries report failure rather than an empty result | Exhausted retries do not produce a fabricated answer | Given a turn whose structured retrieval failed on every attempt with no other sources, when the answer is generated, then the source-citation guardrail replaces the reply with the controlled fallback response | `tests/test_chat_api_sql_retry_integration.py::TestFailureReachesTheControlledFallback::test_exhausted_retries_produce_no_fabricated_answer`, `::test_legitimate_empty_does_not_set_sql_error` | - [x] |
| 25 | sql-query-recovery | Per-attempt observability | A recovered query is fully traceable | Given a first attempt that failed and a second that succeeded, when the invocation completes, then the trace holds two records carrying attempt index, SQL, outcome, sanitized error (first) and row count (second) | `tests/test_chat_api_sql_retry.py::TestToolBoundary::test_trace_records_both_attempts`, `::test_trace_survives_a_total_failure` | - [x] |
| 26 | sql-query-recovery | Per-attempt observability | Attempt diagnostics stay out of the chat response | Given a turn that required retries, when the chat response is returned, then the payload contains no generated SQL and no attempt diagnostics | `tests/test_chat_api_sql_retry_integration.py::TestDiagnosticsStayInternal::test_response_payload_carries_no_sql_or_diagnostics` | - [x] |
| 27 | chat-api | SQL query generation and validation | Valid SQL query is executed | Given a question about entity counts, when generation produces a valid aggregate query, then validation passes it, it executes read-only, results reach the RAG pipeline, and no further generation call is made | `tests/test_chat_api_sql_retry_integration.py::TestRecoveredQueryReachesAnswerGeneration::test_existing_successful_query_still_costs_one_generation_call`; regression `tests/test_chat_api_sql.py::TestSQLValidation::test_6_valid_sql_passes_validation` | - [x] |
| 28 | chat-api | SQL query generation and validation | Malicious SQL is rejected | Given a generated `DROP TABLE`, when validation inspects it, then it is rejected and logged, generation retries within budget, and if no attempt succeeds the SQL source is skipped, the failure is recorded as a structured-retrieval error, and the response indicates the SQL source was unavailable | `tests/test_chat_api_sql_retry_integration.py::TestFailureReachesTheControlledFallback::test_drop_table_is_rejected_retried_and_reported` | - [x] |
| 29 | chat-api | SQL query generation and validation | Query with non-whitelisted table is rejected | Given a generated query referencing `pg_authid`, when validation inspects the table name, then it is rejected, identically on a first attempt and on any retry | `tests/test_chat_api_sql.py::TestSQLValidation::test_8_non_whitelisted_table_rejected` (first attempt); `tests/test_chat_api_sql_retry.py::TestSecurityInvariants::test_retry_cannot_escape_whitelist` (retry) | - [x] |
| 30 | chat-api | SQL query generation and validation | Query exceeds timeout | Given a valid query running longer than 10 seconds, when it is executed, then execution is cancelled and the RAG pipeline skips the SQL source for the turn | `tests/test_chat_api_sql_retry.py::TestOutcomeClassification::test_timeout_is_cancelled_and_classified_as_execution_error` | - [x] |
| 31 | chat-api | SQL query generation and validation | Failed query is recovered within the attempt budget | Given a first query that fails to execute, when a revised query informed by that failure validates and executes, then its results reach the RAG pipeline and the turn proceeds through the unchanged answer-generation pipeline | `tests/test_chat_api_sql_retry_integration.py::TestRecoveredQueryReachesAnswerGeneration::test_recovered_turn_matches_a_first_attempt_success` | - [x] |
| 32 | chat-api | SQL query generation and validation | Generation context carries bounded tenant entity values | Given a tenant with a `SKILL` type containing values such as `python`, when the generation prompt is constructed, then it includes `SKILL` with a bounded sample of actual values drawn only from the request-context schema | `tests/test_chat_api_sql_retry_integration.py::TestDiagnosticsStayInternal::test_profile_queries_use_the_tool_context_schema` | - [x] |

> **Rule:** Every `#### Scenario:` block in every `specs/**/*.md` file for this change
> MUST appear as a row in this table. A missing scenario is a P1 gap that blocks archive.

---

## 2. Hallucination Risk Register

For each area of complexity in this change, identify what an AI agent might get wrong
and how a human reviewer can detect and correct it.

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|-------------------|----------------------|
| 1 | The empty-result retry policy (design.md Decision 3) | The obvious-looking implementation is `if not rows: retry`. An agent may write exactly that, or widen the defect signal with plausible-sounding heuristics (multi-word literal, `=` on a narrative type, "no JOIN present") that design.md deliberately rejected as guessing | Read the empty-result branch line by line: the only permitted trigger is an `entity_type` literal absent from the tenant's fetched type list. Any other condition that can send a zero-row result to a retry is out of spec. Confirm test row 8 fails if the condition is loosened |
| 2 | Failure propagation contract change (Decision 4) | `generate_and_execute` must now *raise* on exhausted retries but still *return `[]`* for a legitimate empty result. An agent may collapse both into one path — raising on every empty result, or reverting to `return None` on failure — either of which silently restores the original defect | Confirm two distinct exit paths exist and that `StructuredRetrievalTool` reports `error` for one and a clean empty result for the other. Rows 22 and 23 must both pass; a single implementation that passes only one is the tell |
| 3 | Error sanitization for feedback and logs (Decision 6) | An agent may pass `str(exception)` through, or strip only the prefix. SQLAlchemy appends the executed statement *and bound parameters* to `DBAPIError.__str__`, so an incomplete strip round-trips tenant values into the prompt and the log | Construct a `DBAPIError`-shaped message containing a `[SQL: … ] [parameters: … ]` tail and assert neither the statement nor the parameters survive sanitization. Grep the new log statements for any use of a raw exception string |
| 4 | Tenant isolation across retries (Decision 1, ADR-001) | An agent may re-read `schema` inside the loop, thread it through the feedback record, or accept it as a parameter of the retry helper — creating a path where a value derived from generated SQL could reach `SET search_path` | Confirm `schema` is bound once before the loop from the function parameter and is never assigned inside it. Grep for `search_path` and confirm every occurrence takes the same bound value. Row 20 must assert the executed schema, not merely that no error occurred |
| 5 | Entity-profile bounding and completeness (Decision 5) | Two failure directions: an agent may merge the two queries into one and silently drop entity types that have no non-null values, or may implement the caps only per-type and leave the total unbounded (or apply `LIMIT` before the window function, corrupting the ranking) | Verify against a fixture tenant with (a) a type whose values are all NULL and (b) more types × values than the total cap. Rows 15 and 16 must both hold. Inspect the SQL: the `ROW_NUMBER()` window must be applied before any outer limit |
| 6 | Early-exit on success (Decision 1, cost control) | An agent may structure the loop so the trace, the profile refresh, or a "verification" step runs after a successful attempt, adding an LLM call to the happy path — the exact cost regression this change is meant to avoid | Assert call counts, not just results: row 1 must fail if generation is invoked twice. Confirm the entity profile is fetched outside the loop (row 17) |
| 7 | Attempt-cap configuration (Decision 7) | An agent may hard-code `3`, use `range(3)`, or leave a stale literal in a guard alongside the setting, so changing the config no longer changes behaviour | Grep the touched files for a bare `3` in any attempt-related expression. Row 3 (`sql_max_attempts = 1`) is the functional check — it must genuinely suppress the second attempt |

> Aim for 3–7 entries. Do not invent risks without basis in design.md.

---

## 3. Pattern & ADR Compliance

List every currently-in-force ADR that constrains this change (as identified in design.md).

| ADR | Decision Summary | Constraint on This Change | Verification Step |
|-----|-----------------|--------------------------|-------------------|
| ADR-001 Tenant Data Isolation via Separate Database Schemas | Per-tenant Postgres schemas; extracted data must never leak across tenants | Schema for every attempt and for both entity-profile queries comes from authenticated request context, never from generated SQL, feedback, or the user's question | Grep the diff for `search_path` and for every assignment to the schema variable; confirm one binding, before the loop, from the function parameter. Run rows 20 and 32 |
| ADR-004 OpenSpec Spec-Driven Development Governance | Every change traceable from intent to evidence | Behaviour is specified with scenarios before implementation; each scenario maps to a verification artifact | Confirm Section 1 covers every `#### Scenario:` in `specs/**/*.md` (32 rows) and that the tasks step filled the Verification Artifact column for all of them |
| ADR-007 Chatbot Architecture with Full RAG and Guardrails | Three-source RAG; mandatory SQL validation layer; read-only transactions with timeouts; citation enforcement; graceful degradation; P95 < 10s | No attempt may bypass `validate_sql` or the read-only execution path; exhausted retries degrade gracefully rather than fabricating an answer; the attempt cap plus the existing retrieval deadline protect the latency target | Confirm the loop body has exactly one call site each for validation and execution, both inside the loop. Run rows 18, 19, 21, 24. Confirm `retrieval_deadline_seconds` still bounds the invocation (row 4) and that answer generation, citation enrichment, and reranking are untouched in the diff |

---

## 4. Evidence Requirements

Evidence that **MUST** be collected and logged in Section 5 before this change is archived.
Do not archive while any item below remains unchecked.

### Functional Evidence

*(Minimum one item per row in Section 1 — test output, screenshot, log excerpt, or API
trace proving the THEN was observed in a real execution.)*

- [x] Row 1 — test output proving a successful first attempt returns rows with a generation-call count of exactly 1
- [x] Row 2 — test output proving a three-failure run makes exactly 3 generation calls and 3 executions, never a fourth
- [x] Row 3 — test output proving `sql_max_attempts = 1` suppresses the second generation call
- [x] Row 4 — test output proving an elapsed tool-context deadline stops further attempts
- [x] Row 5 — test output proving a whitelist rejection is classified `validation_error`, skips execution, and triggers a second attempt
- [x] Row 6 — test output proving an undefined-column error is classified `execution_error` and that the succeeding second attempt's rows are returned
- [x] Row 7 — test output proving a raising/unusable generation call is classified `generation_error` and retried
- [x] Row 8 — test output proving a clean zero-row result returns `[]` with no error and a generation-call count of exactly 1
- [x] Row 9 — test output proving a zero-row result naming a nonexistent entity type is retried and the second attempt's rows are returned
- [x] Row 10 — test output proving a non-empty result is never retried
- [x] Row 11 — captured second-attempt prompt showing the first attempt's SQL, a sanitized failure description, and the corrective instruction
- [x] Row 12 — test output proving a `[SQL: …] [parameters: …]` tail is absent from sanitized feedback and that the result is truncated
- [x] Row 13 — captured second-attempt prompt showing the zero-row statement and the named offending entity-type literal
- [x] Row 14 — captured generation prompt showing `SKILL` with sampled tenant values
- [x] Row 15 — test output proving the per-type cap and the total cap both hold against an over-sized fixture
- [x] Row 16 — test output proving an all-NULL-value entity type still appears in the prompt's type list
- [x] Row 17 — test output proving the profile queries execute once across a three-attempt invocation
- [x] Row 18 — test output proving attempt 3's SQL passed through the validation layer
- [x] Row 19 — test output proving a non-whitelisted retry is rejected and never executed
- [x] Row 20 — test output asserting the schema actually used by every attempt equals the request-context schema
- [x] Row 21 — test output or code-path trace proving retries use the same read-only execution path and timeout
- [x] Row 22 — test output proving exhausted retries produce a `ToolResult` error and populate the turn's structured-retrieval error state
- [x] Row 23 — test output proving a first-attempt zero-row success produces a non-error `ToolResult` with no rows
- [x] Row 24 — test output proving a turn with only a failed structured retrieval terminates in the existing controlled fallback reply
- [x] Row 25 — captured trace showing two attempt records with index, SQL, outcome, sanitized error, and row count
- [x] Row 26 — captured chat response payload confirming no generated SQL and no attempt diagnostics
- [x] Row 27 — regression test output from the existing SQL suite proving valid queries still execute unchanged with a single generation call
- [x] Row 28 — test output proving a `DROP TABLE` generation is rejected, logged, retried within budget, and ends in a skipped SQL source with the failure recorded
- [x] Row 29 — test output proving `pg_authid` rejection behaves identically on a first attempt and on a retry
- [x] Row 30 — test output proving the 10-second timeout still cancels execution and skips the SQL source
- [x] Row 31 — end-to-end test output proving a recovered query's rows reach answer generation with citations and response structure unchanged
- [x] Row 32 — captured prompt confirming bounded sampled values drawn only from the request-context schema

### Structural Evidence

*(Code review and architectural compliance.)*

- [ ] Code review completed — implementation matches design.md decisions (no undocumented deviations)
- [ ] All ADR compliance steps in Section 3 confirmed ✓
- [ ] No undocumented architectural patterns introduced
- [ ] No AI-invented requirements present in generated code (cross-checked against spec files)
- [x] Diff confirms `src/chat_api/graph/builder.py` topology is unchanged — no LangGraph cycle introduced
- [x] Diff confirms answer generation, `ContextAssembler`, citation enrichment, and reranking are untouched
- [x] Full existing test suite for chat/retrieval run: 209 passed, 2 failed — both failures (`test_chat_api_rag.py::TestGuardrailEnforcement::test_chat_response_sources`, `test_chat_graph_topology.py::...::test_single_topology_expected_nodes_only`) reproduce identically with this change's source files stashed, so both pre-date it

### Edge Case Evidence

*(One item per Hallucination Risk from Section 2.)*

- [x] Risk 1 mitigation confirmed — empty-result branch reviewed; the only retry trigger is the nonexistent-`entity_type` literal, and no other zero-row condition reaches a retry
- [x] Risk 2 mitigation confirmed — two distinct exit paths verified; exhausted retries raise, legitimate empties return `[]`, and rows 22 and 23 both pass
- [x] Risk 3 mitigation confirmed — sanitization tested against a message carrying a `[SQL: …] [parameters: …]` tail; neither statement nor parameters survive, and no raw exception string is logged
- [x] Risk 4 mitigation confirmed — `schema` bound exactly once before the loop; no assignment inside it; every `search_path` occurrence uses the bound value
- [x] Risk 5 mitigation confirmed — profile verified against a fixture with an all-NULL-value type and an over-cap type/value count; window function applied before any outer limit
- [x] Risk 6 mitigation confirmed — generation-call counts asserted on the success path; profile fetch verified outside the loop
- [x] Risk 7 mitigation confirmed — no bare attempt-count literal remains; `sql_max_attempts = 1` functionally suppresses retries

---

## 5. Evidence Log

Record collected evidence here. Every row in Section 1 must have at least one matching
entry. Do not pre-fill — entries must describe real observations.

| # | Evidence Type | Description / Link | Scenario(s) Covered | Collected By | Date |
|---|--------------|-------------------|---------------------|--------------|------|
| 1 | Functional | `pytest tests/test_chat_api_sql_retry.py tests/test_chat_api_sql_retry_integration.py tests/test_chat_api_sql.py -v` → **62 passed in 1.34s**, 0 failed. Covers every artifact named in Section 1. | Rows 1–32 | apply session (agent) | 2026-08-10 |
| 2 | Functional | Retry-unit suite alone: `tests/test_chat_api_sql_retry.py` → 40 passed. Includes the call-count assertions (`llm.call_count == 1` on success, `== 3` at the cap, never 4). | Rows 1–23, 25, 30 | apply session (agent) | 2026-08-10 |
| 3 | Functional | Integration suite `tests/test_chat_api_sql_retry_integration.py` → 7 passed. Drives the real `execute_plan`, `StructuredRetrievalTool`, `GuardrailService`, and the real `source_assembly` / `prompt_assembly` / `generation` nodes. | Rows 24, 26, 27, 28, 31, 32 | apply session (agent) | 2026-08-10 |
| 4 | Structural | Chat/retrieval regression run (15 modules): 209 passed, 2 failed. Both failures reproduced with this change's 6 source files stashed (`git stash push -- <files>`), confirming they pre-date the change. | Existing behaviour | apply session (agent) | 2026-08-10 |
| 5 | Structural | Targeted baseline diff over `test_env_config.py`, `test_shared_config_ssl_and_retry.py`, `test_chat_api_reranking.py`, `test_semantic_normalizer_extensibility.py`, `test_chat_api_rag.py`, `test_chat_graph_topology.py`: failure list **identical to baseline** after updating the `generate_and_execute` test fakes. | No regression | apply session (agent) | 2026-08-10 |
| 6 | Structural | `git diff --stat` empty for `graph/builder.py`, `context_assembler.py`, `guardrails.py`, `retriever.py`, `reranker.py` — topology and answer generation untouched. | Rows 24, 31 | apply session (agent) | 2026-08-10 |
| 7 | Edge Case | Risk 4/7 greps: all three `SET search_path` sites in `sql_generator.py` use the bound `schema` parameter with no reassignment; no bare attempt-count literal remains. | Risks 4, 7 | apply session (agent) | 2026-08-10 |
| 8 | Edge Case | Latent defect found and fixed during apply: a failed statement left the session in an aborted transaction, which would have made attempt 2's `SET search_path` fail. `_rollback_quietly` added; asserted by `test_execution_error_retried_and_second_succeeds`. | Row 6 | apply session (agent) | 2026-08-10 |
| 9 | | *(reserved for human reviewer)* | | | |

---

## 6. Audit Record

> ⚠️ **GATE: This section must be completed and signed by a human reviewer before
> `/opsx:archive` is run.** An unsigned or incomplete Audit Record is a hard block on archive.

**Change slug:** bounded-sql-retry-loop
**Proposal:** `openspec/changes/bounded-sql-retry-loop/proposal.md`
**Spec files reviewed:**
  - specs/sql-query-recovery/spec.md
  - specs/chat-api/spec.md

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
