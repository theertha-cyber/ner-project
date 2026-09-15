# Verification Plan

**Change:** external-postgresql-chat-sql-generation
**Generated:** 2026-09-13
**Status:** 🔴 Incomplete — a human reviewer must fill in the Evidence Log and Audit Record before archive.

---

## 1. Spec Alignment

Every requirement and scenario in this change maps to a testable acceptance criterion. Each row drives one evidence entry in Section 5.

Test files:
- `T-GEN` = `tests/test_external_sql_generator.py`
- `T-DESC` = `tests/test_external_pg_contract_descriptions.py`
- `T-TOOL` = `tests/test_external_database_tool.py`
- `T-WIRE` = `tests/test_external_chat_graph_wiring.py`
- `T-CAP4` = `tests/test_external_postgresql_chat.py` (existing CAP-4 suite, regression)

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | external-postgresql-sql-generation | Contract-grounded SQL generation | Prompt is built from the published contract version | Given tenant A with published v2 describing `fisc_user_profile`, when a prompt is built, then it contains v2's entry text and no other version's, connection's, or tenant's entries | `T-GEN::test_prompt_uses_published_version_entries_only` | - [x] |
| 2 | external-postgresql-sql-generation | Contract-grounded SQL generation | Generated statement uses placeholders for values | Given an LLM returning a placeholder statement with `params {"p1": "0"}`, when generation runs, then the statement is accepted and `"0"` reaches execution only via params | `T-GEN::test_placeholder_statement_accepted_and_value_bound` | - [x] |
| 3 | external-postgresql-sql-generation | Contract-grounded SQL generation | Malformed LLM output is not executed | Given non-JSON or wrongly shaped LLM output, when parsed, then the fixture DB records zero executions and the attempt reason is `malformed_output` | `T-GEN::test_malformed_output_never_executes` | - [x] |
| 4 | external-postgresql-sql-generation | Contract-grounded SQL generation | Missing parameter value is not executed | Given `sql` with `%(p2)s` and no `p2` param, when checked, then zero executions and reason `missing_param` | `T-GEN::test_missing_param_never_executes` | - [x] |
| 5 | external-postgresql-sql-generation | Local validation with bounded reason-guided retry | Rejected statement is retried with reason feedback | Given attempt 1 rejected `unapproved_column`/`ssn`, when attempt 2 runs, then its prompt contains both, and the fixture DB saw no introspect/execute for attempt 1 | `T-GEN::test_retry_prompt_carries_reason_and_reference` | - [x] |
| 6 | external-postgresql-sql-generation | Local validation with bounded reason-guided retry | Attempts are bounded | Given an always-rejected LLM, when generation runs, then exactly 3 LLM calls happen, the outcome is `generation_exhausted`, and there are zero executions | `T-GEN::test_attempts_bounded_to_three` | - [x] |
| 7 | external-postgresql-sql-generation | Local validation with bounded reason-guided retry | Accepted statement executes once through the drift gate | Given acceptance on attempt 2, when handed to execution, then `introspect` is called once before exactly one `execute` | `T-GEN::test_accepted_statement_executes_once_after_drift` | - [x] |
| 8 | external-postgresql-sql-generation | Bounded schema context without retrieval | Oversized contract fails closed | Given rendered context over budget, when asked, then zero LLM calls and reason `schema_context_too_large` | `T-GEN::test_oversized_schema_context_fails_closed` | - [x] |
| 9 | external-postgresql-sql-generation | Generation telemetry is content-free | Rejected attempt logs no SQL | Given a rejected attempt, when caplog records are inspected, then they include reason and attempt number and exclude SQL text and param values | `T-GEN::test_rejected_attempt_logs_no_sql_or_params` | - [x] |
| 10 | external-postgresql-chat | Versioned tenant-isolated schema contracts | Valid contract is published | Given an admin with an active connection, when a valid contract is uploaded and published, then canonical, state, and index are retained, tenant-only | `T-CAP4::test_valid_contract_publish_creates_tenant_index` | - [x] |
| 11 | external-postgresql-chat | Versioned tenant-isolated schema contracts | Invalid contract is rejected safely | Given invalid JSON/shape/join key/duplicate, when uploaded, then rejected with finite reason + field paths and no index entry | `T-CAP4::test_invalid_contract_rejected_with_finite_reason` | - [x] |
| 12 | external-postgresql-chat | Versioned tenant-isolated schema contracts | Cross-tenant contract access is denied | Given tenant A's contract, when tenant B names it, then not found and no index entry retrievable | `T-CAP4::test_cross_tenant_contract_and_index_denied` | - [x] |
| 13 | external-postgresql-chat | Versioned tenant-isolated schema contracts | Descriptions are retained and indexed | Given relation and column descriptions, when published, then canonical JSON keeps both and `entry_text` contains both | `T-DESC::test_descriptions_retained_and_indexed` | - [x] |
| 14 | external-postgresql-chat | Versioned tenant-isolated schema contracts | Descriptions do not change the fingerprint | Given two contracts differing only in descriptions, when fingerprinted, then the fingerprints are equal | `T-DESC::test_descriptions_excluded_from_fingerprint` | - [x] |
| 15 | external-postgresql-chat | Versioned tenant-isolated schema contracts | Description for an undeclared column is rejected | Given `column_descriptions` naming undeclared `discount`, when uploaded, then rejected with field `relations.orders.column_descriptions.discount` and no description value echoed | `T-DESC::test_undeclared_column_description_rejected` | - [x] |
| 16 | external-postgresql-chat | Versioned tenant-isolated schema contracts | Overlong description is rejected | Given a description over 2,000 chars, when uploaded, then rejected with `invalid_shape` | `T-DESC::test_overlong_description_rejected` | - [x] |
| 17 | external-postgresql-chat | Versioned tenant-isolated schema contracts | Contract without descriptions remains valid | Given a names-only contract, when uploaded and published, then accepted and indexed as before | `T-DESC::test_contract_without_descriptions_unchanged` + `T-CAP4` passing unmodified | - [x] |
| 18 | external-postgresql-chat | Contract-authorized SQL execution | Approved join and aggregation executes | Given an approved join + aggregation, when executed, then it completes within cap/timeout with response-only rows | `T-CAP4::test_approved_join_aggregation_executes` | - [x] |
| 19 | external-postgresql-chat | Contract-authorized SQL execution | Disallowed statement is rejected safely | Given write/DDL/multi/subquery/CTE/UNION/window/unapproved statements, when validated, then none reach the DB and telemetry has a finite reason only | `T-CAP4::test_disallowed_statements_rejected_safely` | - [x] |
| 20 | external-postgresql-chat | Contract-authorized SQL execution | Unparameterized literal never reaches the database | Given an inline literal, when handled, then it is bound or rejected, with no interpolated value in executed text | `T-CAP4::test_inline_literals_bound_or_rejected` | - [x] |
| 21 | external-postgresql-chat | Contract-authorized SQL execution | Row cap and timeout are enforced by the server | Given >100 rows / >10 s, when executed, then ≤100 rows and server-side cancellation | `T-CAP4::test_server_row_cap_and_timeout_enforced` | - [x] |
| 22 | external-postgresql-chat | Contract-authorized SQL execution | External rows are never retained | Given a completed query with rows, when platform tables are inspected, then no row value exists | `T-CAP4::test_external_rows_never_retained` | - [x] |
| 23 | external-postgresql-chat | Contract-authorized SQL execution | External citation carries no row values | Given an external answer row `{"person_firstname": "Arjun"}`, when persisted message sources are read, then the `external_postgresql` source lists relation names only and no source contains `Arjun` | `T-WIRE::test_external_citation_persists_relation_names_only` | - [x] |
| 24 | external-postgresql-chat | Contract-authorized SQL execution | Capability resolves server-side per authenticated tenant | Given tenants A and B, when A queries, then only A's connection/contract/credential are used | `T-CAP4::test_capability_resolves_per_authenticated_tenant` | - [x] |
| 25 | external-postgresql-chat | Safe external chat outcomes | Drift produces an administrator-action message | Given `drift_mismatch`, when the turn completes, then the prompt/answer carries the fixed schema-changed message and zero executions | `T-WIRE::test_drift_outcome_yields_fixed_admin_message` | - [x] |
| 26 | external-postgresql-chat | Safe external chat outcomes | Database failure text is not surfaced | Given a DB error whose text contains a value, when the turn completes, then only the fixed `execution_failed` message appears in response, persisted message, and logs | `T-WIRE::test_execution_failure_text_not_surfaced` | - [x] |
| 27 | retrieval-tools | External database retrieval tool | Tool arguments expose no scope identifiers | Given the tool, when `args_schema.properties` is read, then the keys are exactly `{"query"}` | `T-TOOL::test_args_schema_only_query` | - [x] |
| 28 | retrieval-tools | External database retrieval tool | Successful query returns rows | Given an executable tenant and a fixture returning 2 rows, when called, then `error is None` and 2 rows | `T-TOOL::test_successful_call_returns_rows` | - [x] |
| 29 | retrieval-tools | External database retrieval tool | Drift block is returned as a finite error | Given drifted metadata, when called, then `ToolResult.error == "drift_mismatch"` and no exception | `T-TOOL::test_drift_returns_finite_error` | - [x] |
| 30 | retrieval-tools | Per-request tool availability | Tenant without a connection is never offered the tool | Given no active connection, when turn schemas are exported, then there is no `external_database` | `T-WIRE::test_tool_not_offered_without_capability` | - [x] |
| 31 | retrieval-tools | Per-request tool availability | Tenant with a published contract is offered the tool | Given an active connection + contract naming `fisc_user_profile`, when exported, then `external_database` is present with a description mentioning `fisc_user_profile` | `T-WIRE::test_tool_offered_with_contract_relations_in_description` | - [x] |
| 32 | retrieval-tools | Per-request tool availability | Unoffered tool call is rejected | Given the tool not offered, when the planner names it, then the entry is rejected and never executed | `T-WIRE::test_unoffered_external_entry_rejected` | - [x] |
| 33 | retrieval-tools | Per-request tool availability | Fallback plan excludes the external tool | Given an offered tool and a planner exception, when the fallback is built, then there is no `external_database` entry | `T-WIRE::test_fallback_plan_excludes_external_tool` | - [x] |

> **Rule:** Every `#### Scenario:` block in every `specs/**/*.md` file for this change
> MUST appear as a row in this table. A missing scenario is a P1 gap that blocks archive.

---

## 2. Hallucination Risk Register

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|-------------------|----------------------|
| 1 | Prompt vs validator grammar (Design D4) | The prompt lists functions or constructs the validator rejects (e.g. `ILIKE` fine, but `STRING_AGG` or `LIMIT 10` permitted in prose). Every demo question then burns retries. | Confirm the test asserting prompt function list == `validator._ALLOWED_FUNCTIONS` exists and passes. Read the prompt for any mention of LIMIT other than "never write". |
| 2 | Row leakage into persistence (D6, ADR-015) | External rows routed through `sql_results`, or the external `Source.value` built from `admitted.rows` instead of relation names. | Grep `source_assembly_node` and `_accumulate` for external handling. Confirm no `json.dumps(` of external rows anywhere a `Source` is built. Run scenario 23 against the real test DB. |
| 3 | Retry path touching the tenant DB (D3) | The implementation calls `execute_external_query` inside the retry loop, so each attempt runs drift introspection. | In `T-GEN`, confirm the fixture counts `introspect` calls == 1 for a multi-attempt success. Read the loop: only `validate_statement` inside. |
| 4 | Contract description persistence (D1) | `store_draft` keeps arbitrary unknown relation keys (current accidental pass-through) instead of normalizing to the four allowed keys; or the fingerprint accidentally includes descriptions. | Upload a contract with an extra key `"foo"` and confirm the stored canonical has no `foo`. Scenario 14 test passes. `canonical_fingerprint` diff shows no change. |
| 5 | Per-turn registry scope (D5) | The turn registry is stored on the shared `RAGOrchestrator` instance (cross-request/cross-tenant leak) instead of graph state; or capability resolution errors break platform chat. | Confirm `orchestrator.tool_registry` is never reassigned. The turn registry exists only in `ChatState`. A test with capability resolution raising still returns a platform answer. |
| 6 | Telemetry / tracing (D7) | The external generator client gets wrapped with `wrap_openai`, or logs `sql`/`params` in debug statements. | Grep `external_sql_generator.py` for `wrap_openai`, `sql` in logger `extra`, and `params` in logs. Scenario 9 test passes. |
| 7 | Skeleton script column set (D8) | The script queries a different catalog (e.g. `pg_attribute` including dropped/system columns), so the contract never matches drift introspection. | Run the script against the demo Azure DB, publish, and confirm the first chat query is not `drift_mismatch`. The script uses the same `information_schema.columns` + `table_schema='public'` predicate as `AzureExternalDatabase.introspect`. |

---

## 3. Pattern & ADR Compliance

| ADR | Decision Summary | Constraint on This Change | Verification Step |
|-----|-----------------|--------------------------|-------------------|
| 001-tenant-data-isolation | Tenant context from authenticated state; per-tenant schemas | Contract, index, and capability lookups use JWT-derived tenant only; tool args carry no scope ids | `T-TOOL::test_args_schema_only_query` passes. `ToolRegistry.register` accepts the tool (forbidden-arg check). Grep the generator for any tenant/connection id taken from args. |
| 011-tenant-scoped-azure-connection-control-plane | Live access only via an active connection row + resolved secret reference | Live database built by `resolve_live_database` only | Grep for `AzureExternalDatabase(` outside `azure_database.py` — none. |
| 013-contract-governed-external-postgresql-chat | Contract authorizes; index context-only; drift before every query; LLM has no DB access; telemetry content-free | All execution through `execute_external_query`; generator never receives credentials or configuration; index text never consulted for authorization | Grep: no `database.execute(` call in the generator/tool. `validate_statement` is given `contract["canonical"]`, not index text. Scenarios 7, 9 pass. |
| 015-external-chat-reply-persistence | Reply persists; rows never in citations/storage | External `Source` holds relation names only | Scenario 23 passes against a real DB. Code review of `source_assembly_node`. |
| 016-contract-grounded-external-sql-generation | Schema from contract; local validation first; per-turn offering; whole-contract context with budget; untraced external generation | Implementation matches D1–D7 | Code review against design.md Decisions 1–7. Scenarios 5–8, 30–33 pass. |

---

## 4. Evidence Requirements

Every item below MUST be collected and logged in Section 5 before archive. Do not archive while any item remains unchecked.

### Functional Evidence

- [x] Scenario 1: `T-GEN::test_prompt_uses_published_version_entries_only` passes
- [x] Scenario 2: `T-GEN::test_placeholder_statement_accepted_and_value_bound` passes
- [x] Scenario 3: `T-GEN::test_malformed_output_never_executes` passes
- [x] Scenario 4: `T-GEN::test_missing_param_never_executes` passes
- [x] Scenario 5: `T-GEN::test_retry_prompt_carries_reason_and_reference` passes
- [x] Scenario 6: `T-GEN::test_attempts_bounded_to_three` passes
- [x] Scenario 7: `T-GEN::test_accepted_statement_executes_once_after_drift` passes
- [x] Scenario 8: `T-GEN::test_oversized_schema_context_fails_closed` passes
- [x] Scenario 9: `T-GEN::test_rejected_attempt_logs_no_sql_or_params` passes
- [x] Scenarios 10–12, 18–22, 24: `T-CAP4` suite passes unmodified (pytest output)
- [x] Scenario 13: `T-DESC::test_descriptions_retained_and_indexed` passes
- [x] Scenario 14: `T-DESC::test_descriptions_excluded_from_fingerprint` passes
- [x] Scenario 15: `T-DESC::test_undeclared_column_description_rejected` passes
- [x] Scenario 16: `T-DESC::test_overlong_description_rejected` passes
- [x] Scenario 17: `T-DESC::test_contract_without_descriptions_unchanged` passes
- [x] Scenario 23: `T-WIRE::test_external_citation_persists_relation_names_only` passes
- [x] Scenario 25: `T-WIRE::test_drift_outcome_yields_fixed_admin_message` passes
- [x] Scenario 26: `T-WIRE::test_execution_failure_text_not_surfaced` passes
- [x] Scenario 27: `T-TOOL::test_args_schema_only_query` passes
- [x] Scenario 28: `T-TOOL::test_successful_call_returns_rows` passes
- [x] Scenario 29: `T-TOOL::test_drift_returns_finite_error` passes
- [x] Scenario 30: `T-WIRE::test_tool_not_offered_without_capability` passes
- [x] Scenario 31: `T-WIRE::test_tool_offered_with_contract_relations_in_description` passes
- [x] Scenario 32: `T-WIRE::test_unoffered_external_entry_rejected` passes
- [x] Scenario 33: `T-WIRE::test_fallback_plan_excludes_external_tool` passes
- [ ] Live demo rehearsal: against the real Azure Postgres, a published contract answers at least three rehearsed questions (count, filter by name, group-by). Screenshot of chat responses, plus a query showing no external row values in `chat_messages.sources`.

### Structural Evidence

- [ ] Code review completed — implementation matches design.md decisions (no undocumented deviations)
- [ ] All ADR compliance steps in Section 3 confirmed ✓
- [ ] No undocumented architectural patterns introduced
- [ ] No AI-invented requirements present in generated code (cross-checked against spec files)

### Edge Case Evidence

- [x] Risk 1: prompt/validator function-list equality test passes; prompt reviewed for LIMIT wording
- [x] Risk 2: no external rows serialized into any `Source`; scenario 23 green on real DB
- [x] Risk 3: fixture introspect count == 1 on a multi-attempt success
- [x] Risk 4: unknown relation key dropped from stored canonical; fingerprint function unchanged
- [x] Risk 5: turn registry lives only in graph state; capability-resolution exception still yields platform answer
- [x] Risk 6: no `wrap_openai` and no SQL/params in logs in the external generator
- [ ] Risk 7: skeleton-generated contract published against Azure → first query not drift-blocked

---

## 5. Evidence Log

| # | Evidence Type | Description / Link | Scenario(s) Covered | Collected By | Date |
|---|--------------|-------------------|---------------------|--------------|------|
| 1 | Test output | `pytest tests/test_external_sql_generator.py tests/test_external_pg_contract_descriptions.py tests/test_external_database_tool.py tests/test_external_chat_graph_wiring.py tests/test_external_postgresql_chat.py -v` — 44 passed | 1–33 | opsx:apply (agent) | 2026-09-13 |
| 2 | Regression sweep | `pytest tests/ -k "chat_api or retrieval or context_assembler or orchestrator or entity_resolution_graph or chat_graph or streaming"` — 596 passed, 3 skipped; 1 pre-existing failure (`test_chat_api_rag.py::test_chat_response_sources`, disclaimer wording, unrelated) and 1 pre-existing collection error (`test_analytics_dashboard.py`, syntax error, unrelated); no new failures | 6.9 regression check | opsx:apply (agent) | 2026-09-13 |
| 3 | | (live demo rehearsal, Risk 7, and Structural Evidence code review remain — human reviewer) | 7.1–7.4, Risk 7 | | |

---

## 6. Audit Record

> ⚠️ **GATE: A human reviewer must complete and sign this section before
> `/opsx:archive` is run.** An unsigned or incomplete Audit Record blocks archive.

**Change slug:** external-postgresql-chat-sql-generation
**Proposal:** `openspec/changes/external-postgresql-chat-sql-generation/proposal.md`
**Spec files reviewed:**
- specs/external-postgresql-sql-generation/spec.md
- specs/external-postgresql-chat/spec.md
- specs/retrieval-tools/spec.md

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
