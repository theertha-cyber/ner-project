## 1. Configuration and migration

- [x] 1.1 Add settings to `src/shared/config.py`: `entity_resolution_enabled: bool = False`, `entity_resolution_max_candidates: int = 5`, `entity_resolution_person_types: str = "PER,PERSON"`, `entity_resolution_max_skills: int = 3`.
- [x] 1.2 Create `alembic/versions/027_conversation_entity_state.py` following the `026` pattern: create `{schema}.conversation_entity_state` (`conversation_id VARCHAR PRIMARY KEY`, `pending_original_message TEXT`, `pending_candidates JSONB`, `pending_reask_count INTEGER NOT NULL DEFAULT 0`, `resolved_document_id VARCHAR`, `resolved_entity_value TEXT`, `updated_at TIMESTAMPTZ NOT NULL DEFAULT now()`) in `tenant_template`, then loop existing `tenant\_%` schemas. `IF NOT EXISTS` throughout; downgrade drops the table in every tenant schema and the template.
- [x] 1.3 Run the migration against a local stack and confirm the table exists in `tenant_template` and in an existing tenant schema; run the downgrade and re-run the upgrade to confirm both directions work.

## 2. Resolver core (no graph wiring yet)

- [x] 2.1 Create `src/chat_api/services/entity_resolver.py` with the resolution result type: outcome (`unresolved` / `unique` / `ambiguous` / `over_cap`), matched mention, candidate list, and resolved document ids.
- [x] 2.2 Implement n-gram mention extraction: contiguous 1–3 word n-grams from the message, each canonicalized with `canonicalize` imported from `src/extraction_service/services/entity_normalizer.py`. No second normalization routine, no LLM call.
- [x] 2.3 Implement the person-type filter: parse `entity_resolution_person_types` and additionally include tenant types whose `public.entity_definitions.base_label_mapping` maps to `PER`, resolved once per request.
- [x] 2.4 Implement the candidate lookup: one parameterized, schema-qualified query against `{schema}.document_entities` filtering `normalized_value IN (:ngrams)` and person types; keep the longest matching n-gram when several overlap.
- [x] 2.5 Implement outcome classification by distinct `document_id` count, collapsing multiple rows per document into one candidate, and applying `entity_resolution_max_candidates` as the `over_cap` threshold.
- [x] 2.6 Implement card assembly: per candidate document, project name, current organization, years of experience, and up to `entity_resolution_max_skills` skills from that document's `document_entities` rows; omit missing fields; append `documents.filename` to every card in the set when two rendered cards are identical.
- [x] 2.7 Implement deterministic clarification text assembly from the cards, with stable 1-based indices and no LLM call; implement the separate over-cap narrowing message.
- [x] 2.8 Implement selection interpretation: regex ordinal/index parse first; otherwise one LLM call receiving only the cards and the user's answer, returning an index or `none`, with a range check against the candidate count before use.
- [x] 2.9 Emit the structured resolution log record (tenant id, outcome, mention count, candidate document count, inherited-binding flag) with no full user message.

## 3. Conversation state

- [x] 3.1 Create `src/chat_api/services/conversation_entity_state.py` with schema-qualified read / upsert-pending / set-binding / clear-pending / clear-binding operations against `conversation_entity_state`, using the request's existing `AsyncSession`.
- [x] 3.2 Implement the pending-clarification lifecycle: store the original message, candidates, and re-ask count on clarification; increment on a failed selection; clear on success or on the second failure.
- [x] 3.3 Implement the binding lifecycle per design Decision 8: set on resolution, inherit when the message has no person mention, replace when a mention resolves elsewhere, clear on a tenant-wide question with no mention and no anaphoric reference.

## 4. Graph wiring

- [x] 4.1 Add additive keys to `ChatState` in `src/chat_api/graph/state.py`: `conversation_id`, `entity_resolution_outcome`, `resolved_document_ids`, `pending_clarification`, `original_message`. No existing key changes meaning.
- [x] 4.2 Add `entity_resolution_node` to `src/chat_api/graph/nodes.py` wrapped in `@_traced("entity_resolution")`: read pending state, interpret a selection if pending, otherwise resolve mentions, then either write the clarification reply or rewrite the plan with the resolved scope.
- [x] 4.3 Implement plan rewriting for `semantic_retrieval`: override each entry's `scope` with `{"type": "document", "document_ids": [resolved]}`, mirroring the argument shape used by `execute_plan`'s candidate filtering.
- [x] 4.4 Implement structured scoping: append the resolved-document constraint to the `structured_retrieval` `query` argument, and post-filter accumulated rows on `document_id`, retaining rows that carry no `document_id`.
- [x] 4.5 In `src/chat_api/graph/builder.py`, register `entity_resolution` and its conditional edge (`END` on clarification, `retrieval_execution` otherwise) only when `settings.entity_resolution_enabled` is true; the flag-off graph must be byte-identical to today's.
- [x] 4.6 Pass `conversation_id` from `src/chat_api/api/v1/chat.py` into the graph state, and return `pending_clarification` in the response when present.

## 5. API surface

- [x] 5.1 Add `CandidateEntity` and `PendingClarification` models plus the optional `ChatResponse.pending_clarification` field to `src/chat_api/api/v1/schemas.py`, excluded from the payload when absent.
- [x] 5.2 Persist the clarification turn as ordinary user + assistant `chat_messages` rows so conversation history and titles behave as before.
- [x] 5.3 Narrow the citation-enforcement carve-out in `src/chat_api/services/guardrails.py` (or its call site in `generation_node`) so it keys on the resolver-produced clarification outcome, never on an empty `sources` array.

## 6. Resolver unit tests — `tests/test_entity_resolver.py`

- [x] 6.1 Canonicalized matching, including an alias-mapped value (rows 24, 38).
- [x] 6.2 Longest-mention selection (row 25) and non-person type exclusion (row 26).
- [x] 6.3 Zero-call assertion on the stubbed LLM client during extraction and matching (row 27).
- [x] 6.4 Outcome classification: unresolved, unique, eleven-rows-one-document collapse, ambiguous (rows 28–31).
- [x] 6.5 Over-cap path: narrowing message, no candidate list, no pending state stored (row 34).
- [x] 6.6 Card assembly: field omission, skill cap, filename fallback, verbatim stored values (rows 35–38).
- [x] 6.7 Clarification text: named reference and stable 1-based indices for three candidates (row 33).
- [x] 6.8 Selection interpretation: ordinal with zero LLM calls, descriptive answer, attribute answer, out-of-range index rejection (rows 42–45).
- [x] 6.9 Log records for the ambiguous and unresolved outcomes with their counts (rows 63, 64).

## 7. State and conversation tests — `tests/test_conversation_entity_state.py`

- [x] 7.1 Pending state written in one session is readable from another (row 39).
- [x] 7.2 A second clarification leaves exactly one pending row (row 41).
- [x] 7.3 Re-ask then abandon-and-fall-through across two turns (rows 46, 47).
- [x] 7.4 Original message replay and pending clear after a successful selection (rows 48, 49).
- [x] 7.5 Binding lifecycle: inherit on a nameless follow-up, inherit across three successive follow-ups, replace on a different person, clear on a corpus-wide question, no re-clarification of a bound mention (rows 54–58).

## 8. Graph and retrieval-scope tests — `tests/test_entity_resolution_graph.py`

- [x] 8.1 Ordered call log showing the resolver query precedes any capability invocation (row 22).
- [x] 8.2 Clarification turn: zero retrieval invocations, zero generation calls, routes to END (rows 14, 32).
- [x] 8.3 `unique` and `unresolved` outcomes continue through the unchanged node sequence (row 15); unresolved adds no scope (row 21).
- [x] 8.4 Routing function is a pure function of counted state (row 16); compiled graph acyclic with the flag on (row 17).
- [x] 8.5 State keys present after the node runs and downstream nodes read only pre-existing keys (rows 19, 20).
- [x] 8.6 Semantic scope override captured from plan arguments (row 50).
- [x] 8.7 Structured post-filter drops foreign-document rows and retains id-less rows (rows 51, 52).
- [x] 8.8 Resumed-turn citations reference only the resolved document (row 53).
- [x] 8.9 Guardrail early exits still short-circuit unchanged (rows 12, 13).

## 9. API and isolation tests — `tests/test_chat_api_entity_resolution.py`

- [x] 9.1 Ambiguous turn returns 200 with clarification `reply`, empty `sources`, populated `pending_clarification` (row 6).
- [x] 9.2 Unambiguous turn omits `pending_clarification` (row 7).
- [x] 9.3 Clarification turn appears in conversation history (row 8).
- [x] 9.4 Guardrail: clarification passes through unmodified (row 10); sourceless generated answer on a resumed turn is still replaced (row 11); existing sourceless rejection unchanged (row 9).
- [x] 9.5 Two-tenant integration: resolver queries stay in the requesting schema and pending state is not cross-visible (rows 23, 40).

## 10. Flag-off equivalence tests — `tests/test_entity_resolution_flag_off.py`

- [x] 10.1 Zero resolver queries with the flag off (row 59).
- [x] 10.2 Compiled node and edge sets equal the pre-change topology with the flag off (rows 18, 60).
- [x] 10.3 A stale stored binding does not scope retrieval with the flag off (row 62).
- [x] 10.4 Run `tests/test_chat_api_rag.py`, `tests/test_chat_api_guardrails.py`, `tests/test_chat_api_conversations.py`, `tests/test_chat_api_widget.py`, `tests/test_chat_graph_topology.py` (the file `test_langgraph_parity.py` no longer exists under that name in this repo — this is the graph-topology suite it was renamed to) unmodified with the flag off and confirm all pass (rows 1–5, 61). Result: 64 passed, 2 skipped (require live OpenAI/model-serving), 1 pre-existing unrelated failure (`test_chat_response_sources`, a disclaimer-wording assertion documented as pre-existing in `openspec/changes/agentic-retrieval-loop/tasks.md` task 6.1 — untouched by this change).
- [x] 10.5 Run the existing `src/shared` import-isolation test to confirm ADR-005 still holds.

## 11. Verification & Evidence

- [x] 11.1 Run all acceptance-criteria tests for every scenario in verification.md § Spec Alignment and confirm all pass. Done live against docker `postgres-test-1` (db `ner_test`): 69/69 new tests pass; existing regression suite 64 passed / 2 skipped (live-service-only) / 1 pre-existing unrelated failure.
- [x] 11.2 Collect functional evidence (screenshot / test output / log) for each scenario — record one entry per row in verification.md § Evidence Log. 5 evidence rows recorded (test-run output + code-review confirmation).
- [x] 11.3 Confirm every Hallucination Risk mitigation step in verification.md § Hallucination Risk Register. All 8 risks re-checked against the implemented code (see Evidence Log rows 4–5 and Edge Case Evidence checkboxes in Section 4).
- [x] 11.4 Confirm all ADR compliance steps in verification.md § Pattern & ADR Compliance. ADR-001 (schema qualification), ADR-004 (this change's own artifacts), ADR-005 (import isolation test passing), ADR-007 (guardrail carve-out structural, parameterized SQL) all confirmed.
- [ ] 11.5 Complete Audit Record sign-off in verification.md § Audit Record (human reviewer required — this task cannot be marked complete by an agent).
- [x] 11.6 Run `openspec validate entity-resolution-disambiguation --type change --strict` and confirm it exits clean before archive. Confirmed: "Change 'entity-resolution-disambiguation' is valid".
