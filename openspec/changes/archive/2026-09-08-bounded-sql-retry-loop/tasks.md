## 1. Configuration

- [x] 1.1 Add `sql_max_attempts: int = 3`, `sql_entity_sample_values_per_type: int = 8`, and `sql_entity_sample_max_values: int = 120` to `Settings` in `src/shared/config.py`, placed with the existing `orchestrator_max_invocations` / `retrieval_deadline_seconds` budget block.
- [x] 1.2 In `src/chat_api/services/sql_generator.py`, read `settings.sql_max_attempts` once in `SQLGenerator.__init__` into `self.max_attempts`, clamped to `max(1, …)`. Confirm no attempt-count literal appears anywhere else in the module.

## 2. Attempt model and outcome classification

- [x] 2.1 Add an `SQLAttemptOutcome` enum (or string constants) with exactly `success`, `generation_error`, `validation_error`, `execution_error`, `empty_with_defect`, and a `RETRYABLE_OUTCOMES` set excluding `success`.
- [x] 2.2 Add an `SQLAttempt` dataclass carrying `attempt` (1-based), `max_attempts`, `sql`, `outcome`, `row_count`, `error`, `defect`. Add an `as_trace_dict()` returning a plain dict for the sink.
- [x] 2.3 Add `SQLGenerationFailed(Exception)` carrying `attempts: list[SQLAttempt]`, raised when every attempt fails.
- [x] 2.4 Add `_sanitize_error(exc)` — class name plus first line of the message, everything from a `[SQL:` marker onward removed, truncated to a fixed budget constant. Unit-tested in 7.4.

## 3. Bounded tenant entity profile

- [x] 3.1 Add an `EntityProfile` dataclass holding `entity_types: list[str]` and `samples: dict[str, list[str]]`.
- [x] 3.2 Keep `_fetch_known_entity_types` unchanged as the complete-type-list source, so a type whose rows all have NULL `normalized_value` is never dropped.
- [x] 3.3 Add `_fetch_entity_value_samples(session, schema)` — one query using `ROW_NUMBER() OVER (PARTITION BY entity_type ORDER BY COUNT(*) DESC, normalized_value)` over a grouped scan of non-null, non-empty `normalized_value`, with the per-type cap applied inside the window filter and the total cap as the outer `LIMIT`. Truncate each value to a fixed character budget. Return `{}` and log a warning on any exception, matching the existing degradation style.
- [x] 3.4 Add `_fetch_entity_profile(session, schema)` composing 3.2 and 3.3 into an `EntityProfile`. It runs **once per invocation**, before the attempt loop.
- [x] 3.5 Extend `generate_sql`'s prompt construction to render the profile as a type-with-examples block, replacing the current `entity_types_desc` string. Keep the existing "a type not on this list matches nothing at all" instruction.

## 4. Feedback construction

- [x] 4.1 Add `_render_attempt_feedback(attempts: list[SQLAttempt]) -> str` producing a bounded block: for each prior attempt, the SQL (truncated at `MAX_SQL_LENGTH`), the outcome, the sanitized reason, and — for `empty_with_defect` — the row count and the offending entity-type literal, followed by the fixed corrective instruction naming entity types, values, operators, joins, and filters.
- [x] 4.2 Add an optional `previous_attempts: list[SQLAttempt] | None = None` parameter to `generate_sql`; when present, append the rendered block to the prompt. Attempt 1 must produce a byte-identical prompt to today's plus the profile change from 3.5 — no feedback section.

## 5. The bounded loop

- [x] 5.1 Add `_entity_type_defect(sql, entity_types) -> str | None` — extract `entity_type` string literals compared with `=` / `IN` from the SQL, case-fold, and return the first literal absent from the tenant's type list. Return `None` when the SQL names no `entity_type` literal.
- [x] 5.2 Rewrite `generate_and_execute` as a bounded loop over `range(self.max_attempts)`. Bind `schema` once from the function parameter before the loop; never reassign it inside. Fetch the entity profile once before the loop. Per attempt: generate (with feedback from prior attempts) → `validate_sql` → `execute_sql` → classify → append an `SQLAttempt`.
- [x] 5.3 Classify each attempt per Decision 2: generation exception/unusable text → `generation_error`; `SQLValidationError` → `validation_error`; execution exception → `execution_error`; rows returned → `success`; zero rows with an entity-type defect → `empty_with_defect`; zero rows without a defect → `success`.
- [x] 5.4 Return rows immediately on `success` — including a zero-row `success`, which returns `[]`. No generation call may occur after a success.
- [x] 5.5 Break out of the loop before generating a further attempt when the caller-supplied deadline has elapsed.
- [x] 5.6 Raise `SQLGenerationFailed(attempts)` when the loop exits without a `success`.

## 6. Wiring: sink, failure propagation, trace

- [x] 6.1 Add an optional `attempt_sink: list | None = None` parameter to `generate_and_execute`; append every `SQLAttempt.as_trace_dict()` to it, mirroring the `degraded_sink` pattern in `RerankingRetriever.retrieve`.
- [x] 6.2 Widen the `SqlSearch` callable type in `src/shared/retrieval/tools/base.py` to accept the optional sink, and add a `diagnostics: list[dict]` field to `ToolResult` (default empty).
- [x] 6.3 In `src/chat_api/services/rag_orchestrator.py`, forward the sink from `_sql_source` to `generate_and_execute`.
- [x] 6.4 In `src/shared/retrieval/tools/entity_tools.py`, allocate the sink per call, pass it through, and attach it to `ToolResult.diagnostics`. Let `SQLGenerationFailed` propagate so `run_tool` converts it into `ToolResult(error=…)` — do not catch it.
- [x] 6.5 Add a `diagnostics: list[dict]` field to `PlanTraceEntry` in `src/shared/retrieval/orchestrator.py`, populated from `ToolResult.diagnostics` in `_invoke_entry`, so the trace reaches the existing `ChatState["plan_trace"]` via the existing `asdict` conversion. Confirm no response schema in `src/chat_api/api/v1/schemas.py` exposes it.
- [x] 6.6 Add the per-attempt structured log line (attempt index, cap, outcome, row count, sanitized error, SQL) at INFO for success and WARNING for failures. Confirm no raw exception string is logged.

## 7. Tests — `tests/test_chat_api_sql_retry.py`

- [x] 7.1 Row 1 — `test_successful_first_attempt_makes_one_generation_call`: assert rows returned and generation mock called exactly once, execution once.
- [x] 7.2 Rows 2 and 5–7 — `test_three_failures_stop_at_cap`, `test_validation_error_retried`, `test_execution_error_retried_and_second_succeeds`, `test_generation_error_retried`: assert call counts and per-attempt outcomes; assert no fourth call.
- [x] 7.3 Rows 3–4 — `test_max_attempts_one_makes_single_pass`, `test_elapsed_deadline_stops_loop`.
- [x] 7.4 Rows 11–13 — `test_retry_prompt_contains_previous_sql_and_reason`, `test_sanitizer_strips_sql_and_parameter_echo`, `test_empty_defect_feedback_names_entity_type`: capture the second-attempt prompt from the generation mock and assert on its content.
- [x] 7.5 Rows 8–10 — `test_unexplained_empty_not_retried`, `test_empty_with_unknown_entity_type_retried`, `test_non_empty_never_retried`.
- [x] 7.6 Rows 14–17 — `test_profile_samples_in_prompt`, `test_profile_caps_per_type_and_total`, `test_null_valued_type_still_listed`, `test_profile_fetched_once_per_invocation`.
- [x] 7.7 Rows 18–21 — `test_every_retry_is_validated`, `test_retry_cannot_escape_whitelist`, `test_all_attempts_use_request_context_schema` (assert the schema argument actually passed to each execution), `test_retries_use_read_only_path`.
- [x] 7.8 Rows 22–23, 25 — `test_exhausted_retries_surface_tool_error`, `test_legitimate_empty_is_not_an_error`, `test_trace_records_both_attempts`: exercise through `StructuredRetrievalTool.call` so the `ToolResult` boundary is what is asserted.

## 8. Tests — integration and regression

- [x] 8.1 Row 24 — in `tests/test_chat_api_rag.py` (or a new graph-level test), assert a turn whose structured retrieval fails on every attempt and has no other sources terminates in `FALLBACK_REPLY` with empty sources.
- [x] 8.2 Row 26 — assert the chat response payload for a retried turn contains no generated SQL and no attempt diagnostics.
- [x] 8.3 Row 31 — end-to-end test: attempt 1 fails, attempt 2 succeeds, and the turn produces the same reply/citation structure as an equivalent first-attempt success.
- [x] 8.4 Rows 27, 29, 30 — confirm the existing `tests/test_chat_api_sql.py` scenarios still pass unmodified; extend row 27's case with a generation-call-count assertion.
- [x] 8.5 Row 28 — `test_drop_table_generation_retried_then_reported`: rejected, logged, retried within budget, ends as a structured-retrieval error with the SQL source skipped.
- [x] 8.6 Row 32 — assert the generation prompt's sampled values are drawn only from the request-context schema (assert the schema used by the profile queries).
- [x] 8.7 Run the full existing chat/retrieval suite and confirm green: `test_chat_api_sql.py`, `test_chat_api_structured_value_sql.py`, `test_sql_generator_document_name_fix.py`, `test_chat_api_rag.py`, `test_chat_api_streaming.py`, `test_retrieval_tools.py`, `test_retrieval_orchestrator.py`, `test_orchestrator_integration.py`, `test_chat_graph_topology.py`.
- [x] 8.8 Fill in the Verification Artifact column for all 32 rows in `verification.md` § Spec Alignment with the test names created in groups 7 and 8.

## 9. Verification & Evidence

- [x] 9.1 Run all acceptance-criteria tests for every scenario in verification.md § Spec Alignment and confirm all pass.
- [x] 9.2 Collect functional evidence (test output / captured prompt / log excerpt) for each scenario — record one entry per row in verification.md § Evidence Log.
- [x] 9.3 Confirm every Hallucination Risk mitigation step in verification.md § Hallucination Risk Register.
- [x] 9.4 Confirm all ADR compliance steps in verification.md § Pattern & ADR Compliance.
- [ ] 9.5 Complete Audit Record sign-off in verification.md § Audit Record (human reviewer required — this task cannot be marked complete by an agent).
- [x] 9.6 Run `openspec validate bounded-sql-retry-loop --type change --strict` and confirm it exits clean before archive.
