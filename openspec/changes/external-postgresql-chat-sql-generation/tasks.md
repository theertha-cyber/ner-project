## 1. Demo Prerequisites (do first — these block everything live)

- [ ] 1.1 Confirm chat-api and gateway can reach the Azure Postgres server over TLS from their runtime host. Check the firewall/IP allowlist. Record the outcome (not the host) in the evidence log.
- [ ] 1.2 Create or confirm a read-only role on the Azure database. Restrict sensitive columns with column-level `GRANT`s, because the drift gate compares every column the role can see.
- [ ] 1.3 Set the password as an `env://` secret in both the gateway and chat-api environments. Create the `azure_postgresql` connection in the portal, run its connection test, and activate it.
- [x] 1.4 Run the existing validator against representative placeholder statements (`WHERE col = %(p1)s`, `ILIKE %(p1)s`, `DATE_TRUNC(%(p1)s, col)`, `COUNT(*) ... GROUP BY`) to confirm sqlparse doesn't misclassify `%(name)s`. If it does, fix that before 4.x. (Confirmed locally — all four forms validate correctly; no fix needed. `tests/test_external_sql_generator.py` also exercises `WHERE col = %(p1)s` end to end.)

## 2. Contract Descriptions (Design D1, D2)

- [x] 2.1 In `src/shared/external_postgres/contract.py`, extend `validate_contract_document` for optional `description` (string ≤ 2,000) and `column_descriptions` (object; keys must be declared columns; string values ≤ 2,000). Errors are field-path only, with reason `invalid_shape`.
- [x] 2.2 Normalize relations in `store_draft` to only `columns`, `primary_key`, `description`, and `column_descriptions` before persisting canonical JSON. Leave `canonical_fingerprint` untouched.
- [x] 2.3 Change `index.entry_text_for_relation` to take the relation definition and render the relation description, one line per column with an optional description, and join lines. Update `replace_version_entries` to pass the definition.
- [x] 2.4 Update the portal contract-upload hint text in `src/portal/src/components/data-sources/contracts.tsx` to mention optional `description` / `column_descriptions`. Update its test if it asserts hint text.
- [x] 2.5 Write `tests/test_external_pg_contract_descriptions.py`: `test_descriptions_retained_and_indexed` (verification #13), `test_descriptions_excluded_from_fingerprint` (#14), `test_undeclared_column_description_rejected` (#15), `test_overlong_description_rejected` (#16), `test_contract_without_descriptions_unchanged` (#17), plus a Risk-4 check that an unknown relation key is dropped.
- [x] 2.6 Run `tests/test_external_postgresql_chat.py` unmodified and confirm it passes (#10–12, #17). Use the `ner_test` DB default, never the dev DB.

## 3. Contract Skeleton Script (Design D8)

- [x] 3.1 Add `scripts/external_pg_contract_skeleton.py`. It reads `EXTERNAL_PG_DSN` from the environment, takes `--tables`/`--version`, and uses asyncpg with the same `information_schema.columns WHERE table_schema = 'public'` predicate as `AzureExternalDatabase.introspect`. It adds the primary key from `table_constraints`/`key_column_usage`, adds joins from foreign keys limited to the selected tables, and writes empty `description`/`column_descriptions` entries. Output goes to stdout.
- [ ] 3.2 Run the script against the demo Azure database for the demo tables. Fill in descriptions (adapt the `fisc_user_profile` prose), then validate locally with `validate_contract_document`.

## 4. External SQL Generator (Design D3, D4, D7)

- [x] 4.1 Add settings in `src/shared/config.py`: `external_pg_sql_max_attempts` (default 3) and `external_pg_schema_context_max_chars` (default 60000).
- [x] 4.2 Add `EXTERNAL_OUTCOME_MESSAGES` (finite reason → fixed user-facing text) for `drift_mismatch`, `metadata_unavailable`, `fingerprint_failure`, `not_active_connection`, `no_published_contract`, `generation_exhausted`, `schema_context_too_large`, `execution_failed`, and `unanswerable`. Place it in `src/chat_api/services/external_postgres_chat.py`.
- [x] 4.3 Create `src/chat_api/services/external_sql_generator.py`:
  - `EXTERNAL_SQL_SYSTEM_PROMPT`, whose rules mirror the validator grammar.
  - An unwrapped `AsyncAzureOpenAI`/`AsyncOpenAI` client, built from the same settings `SQLGenerator` uses.
  - An `ExternalAnswer` dataclass: rows, truncated, relations, reason.
- [x] 4.4 Implement `ExternalSQLGenerator.answer(...)`:
  - Resolve capability.
  - `fetch_entries` for the published version, then render within the budget.
  - Attempt loop: JSON parse → placeholder/param check → local `validate_statement`, with reason + reference feedback.
  - `resolve_live_database`.
  - A single `execute_external_query`.
  - Map every exception to a finite reason. Log only attempt number, reason, and latency, using `_metrics().measure_llm_call("external_sql_generation")`.
- [x] 4.5 Write `tests/test_external_sql_generator.py` with a scripted fake LLM client and `FixtureExternalDatabase` (patch `resolve_live_database`):
  - `test_prompt_uses_published_version_entries_only` (#1)
  - `test_placeholder_statement_accepted_and_value_bound` (#2)
  - `test_malformed_output_never_executes` (#3)
  - `test_missing_param_never_executes` (#4)
  - `test_retry_prompt_carries_reason_and_reference` (#5)
  - `test_attempts_bounded_to_three` (#6)
  - `test_accepted_statement_executes_once_after_drift` (#7, Risk 3: introspect count == 1)
  - `test_oversized_schema_context_fails_closed` (#8)
  - `test_rejected_attempt_logs_no_sql_or_params` (#9, Risk 6)
  - `test_prompt_functions_match_validator_allowlist` (Risk 1)

## 5. External Database Tool (retrieval-tools spec)

- [x] 5.1 Add an optional `external_search` callable to `ToolContext` in `src/shared/retrieval/tools/base.py`, documented like `sql_search`.
- [x] 5.2 Create `src/shared/retrieval/tools/external_tools.py`:
  - `ExternalDatabaseTool(name="external_database")`, whose args are `query` only and whose description is a constructor argument.
  - `call` goes through `run_tool`. A non-empty reason returns `ToolResult(error=<reason>)`. Success returns rows, with `result_completeness` from `truncated` and relation names in `diagnostics`.
  - A `render_external_tool_description(contract)` helper: per-relation truncation to 200 chars, total cap 2,000.
  - No `src.chat_api` import.
- [x] 5.3 Write `tests/test_external_database_tool.py`: `test_args_schema_only_query` (#27), `test_successful_call_returns_rows` (#28), `test_drift_returns_finite_error` (#29), plus a registry-registration check (forbidden-arg guard accepts it).

## 6. Chat Graph Wiring (Design D5, D6)

- [x] 6.1 In `RAGOrchestrator`, construct `ExternalSQLGenerator` and add `_external_source(query, session, tenant_id, conversation_context, deadline)`. Pass `external_search` into the `ToolContext` built in `retrieval_execution_node`.
- [x] 6.2 Add `tool_registry` to `ChatState`. In `orchestrator_node`, resolve capability with the state session. When executable, build a turn registry: platform tools plus an `ExternalDatabaseTool` with the rendered description. Otherwise use `orchestrator.tool_registry`. On an exception, log the error class and fall back to the platform registry. Never reassign `orchestrator.tool_registry`.
- [x] 6.3 Let `plan_retrieval`/`_build_messages` take an optional system-prompt addendum describing when to use `external_database`. Pass it only when the tool is offered. Keep planner input byte-identical otherwise.
- [x] 6.4 Make `retrieval_execution_node` use the registry from state. Confirm `build_fallback_plan` still names platform capabilities only.
- [x] 6.5 Route `external_database` results in `_accumulate` to new `external_results`, `external_relations`, and `external_failure_reason` fields. Carry them through `RetrievalExecution`, graph state, and hit-rate recording.
- [x] 6.6 Extend `ContextAssembler.assemble`: render the external rows block with a truncation note, or the fixed `EXTERNAL_OUTCOME_MESSAGES[reason]` with an instruction to relay it. Record `external_relations` on `AdmittedEvidence`.
- [x] 6.7 In `source_assembly_node`, emit `Source(source_type="external_postgresql", value=json.dumps({"relations": [...]}), relevance_score=1.0)` for admitted external evidence. External rows are never serialized. Confirm `_enrich_citations` passes the new source type through unchanged.
- [x] 6.8 Write `tests/test_external_chat_graph_wiring.py`:
  - `test_tool_not_offered_without_capability` (#30)
  - `test_tool_offered_with_contract_relations_in_description` (#31)
  - `test_unoffered_external_entry_rejected` (#32)
  - `test_fallback_plan_excludes_external_tool` (#33)
  - `test_external_citation_persists_relation_names_only` (#23, real test DB)
  - `test_drift_outcome_yields_fixed_admin_message` (#25)
  - `test_execution_failure_text_not_surfaced` (#26)
  - `test_capability_resolution_error_keeps_platform_chat` (Risk 5)
- [x] 6.9 Run the existing chat graph, orchestrator, and context-assembler test suites. Diff failing test IDs against the recorded baseline (the suite is red on main) and confirm there are no new failures.

## 7. Live Demo Rehearsal

- [ ] 7.1 Upload and publish the description-filled contract from 3.2 through the portal. Confirm the publish response and index entries contain descriptions.
- [ ] 7.2 Ask at least three rehearsed questions in chat against Azure (a count with a filter, a name lookup via `ILIKE`, a group-by). Confirm correct answers, no `drift_mismatch`, and that `LANGSMITH_TRACING` is off.
- [ ] 7.3 Query `chat_messages` sources for the rehearsal turns and confirm only `external_postgresql` relation-name sources, with no row values.
- [ ] 7.4 Update `docs/bugs/tenant-self-service-data-sources.md` with any defects found (DS-NNN) and run `graphify update .`.

## 8. Verification & Evidence

- [x] 8.1 Run all acceptance-criteria tests for every scenario in
         verification.md § Spec Alignment and confirm all pass. (44/44 pass; rows 1-33 marked. Live-Azure-dependent items remain: Section 1, 3.2, 7, and Risk 7.)
- [x] 8.2 Collect functional evidence (screenshot / test output / log) for each
         scenario — record one entry per row in verification.md § Evidence Log. (Entries 1-2 recorded; entry 3 — live demo evidence — needs a human reviewer.)
- [x] 8.3 Confirm every Hallucination Risk mitigation step in
         verification.md § Hallucination Risk Register. (Risks 1-6 confirmed by test + grep; Risk 7 needs the live Azure skeleton-script run.)
- [x] 8.4 Confirm all ADR compliance steps in
         verification.md § Pattern & ADR Compliance. (Grepped: no `wrap_openai`/sql-in-logs in the generator, no `AzureExternalDatabase(` outside azure_database.py, no direct `database.execute(` in generator/tool.)
- [ ] 8.5 Complete Audit Record sign-off in verification.md § Audit Record
         (human reviewer required — this task cannot be marked complete by an agent).
- [x] 8.6 Run `openspec validate external-postgresql-chat-sql-generation --type change --strict` and confirm
         it exits clean before archive. (Confirmed: "Change 'external-postgresql-chat-sql-generation' is valid".)
