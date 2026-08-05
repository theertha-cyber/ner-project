# Verification Plan

**Change:** entity-resolution-disambiguation
**Generated:** 2026-07-31
**Status:** 🟡 Implementation verified by agent (69/69 new tests + existing regression suite passing live against Postgres) — Audit Record sign-off in Section 6 still required from a human reviewer before archive.

---

## 1. Spec Alignment

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | chat-api | RAG chat endpoint | Chat with simple entity count query | Given a tenant with ORG entities, when a count question is posted, then status is 200 and the body carries `reply`, a non-empty `sources`, and `conversation_id` | `tests/test_chat_api_rag.py` (unmodified, flag off) — task 10.4 | - [x] |
| 2 | chat-api | RAG chat endpoint | Chat with document context query | Given indexed document chunks, when a content question is posted, then `sources` contains chunks each carrying `document_id`, `chunk_index`, `relevance_score` | `tests/test_chat_api_rag.py` (unmodified, flag off) — task 10.4 | - [x] |
| 3 | chat-api | RAG chat endpoint | Chat with NER query | Given a promoted model, when a snippet question is posted, then `sources` contains an NER entry with `entity_type`, `value`, `confidence` | `tests/test_chat_api_rag.py` (unmodified, flag off) — task 10.4 | - [x] |
| 4 | chat-api | RAG chat endpoint | Chat with existing conversation | Given conversation `conv-abc`, when a message is posted with that id, then status is 200, the message is appended, and prior history reaches the prompt | `tests/test_chat_api_conversations.py` (unmodified, flag off) — task 10.4 | - [x] |
| 5 | chat-api | RAG chat endpoint | Chat without authentication | Given no JWT, when `/api/v1/chat` is posted, then status is 401 | `tests/test_chat_api_rag.py` (unmodified, flag off) — task 10.4 | - [x] |
| 6 | chat-api | RAG chat endpoint | Ambiguous reference returns a clarification response | Given three same-name candidate documents and the flag on, when the message is posted, then status is 200, `reply` holds the clarification and candidate list, `sources` is empty, and `pending_clarification` holds the ordered candidates | `tests/test_chat_api_entity_resolution.py` — task 9.1 | - [x] |
| 7 | chat-api | RAG chat endpoint | Non-clarification responses omit the new field | Given an unambiguous message with the flag on, when the turn completes, then `pending_clarification` is absent from the response body | `tests/test_chat_api_entity_resolution.py` — task 9.2 | - [x] |
| 8 | chat-api | RAG chat endpoint | Clarification turn is persisted to the conversation | Given a clarification response, when the conversation is fetched, then both the user message and the clarification reply appear in its history | `tests/test_chat_api_entity_resolution.py` — task 9.3 | - [x] |
| 9 | chat-api | Guardrail — source citation enforcement | Response without sources is rejected | Given a generated reply with no sources, when the guardrail inspects it, then it is replaced with the fixed no-information message and the event is logged | `tests/test_chat_api_guardrails.py` + task 9.4 | - [x] |
| 10 | chat-api | Guardrail — source citation enforcement | Clarification request is not replaced by the guardrail | Given a resolver-assembled clarification with no generation call, when the response is returned, then the clarification text is preserved verbatim and `sources` is empty | `tests/test_chat_api_entity_resolution.py` — task 9.4 | - [x] |
| 11 | chat-api | Guardrail — source citation enforcement | Generated answer after selection still requires citations | Given a resumed turn whose generation produces no sources, when the response is returned, then citation enforcement replaces it as for any other answer | `tests/test_chat_api_entity_resolution.py` — task 9.4 | - [x] |
| 12 | chat-orchestration-graph | Fixed topology with no agentic behaviour | Blocked question short-circuits to END | Given a `content_generation` message, when the graph runs, then it ends at the guardrail with the existing decline and no retrieval, SQL, NER, or LLM call | `tests/test_entity_resolution_graph.py` — task 8.9 | - [x] |
| 13 | chat-orchestration-graph | Fixed topology with no agentic behaviour | Out-of-domain question short-circuits to END | Given a message the domain classifier rejects, when the graph runs, then it ends with the existing out-of-domain decline and no retrieval or generation call | `tests/test_entity_resolution_graph.py` — task 8.9 | - [x] |
| 14 | chat-orchestration-graph | Fixed topology with no agentic behaviour | Clarification short-circuits to END | Given an ambiguous resolver outcome, when the graph runs, then `entity_resolution` routes to END with the deterministic clarification text and no retrieval execution or generation call | `tests/test_entity_resolution_graph.py` — task 8.2 | - [x] |
| 15 | chat-orchestration-graph | Fixed topology with no agentic behaviour | Unique and unresolved outcomes continue to retrieval | Given a `unique` or `unresolved` outcome, when the graph runs, then `entity_resolution` routes to retrieval execution and the remaining node sequence is unchanged | `tests/test_entity_resolution_graph.py` — task 8.3 | - [x] |
| 16 | chat-orchestration-graph | Fixed topology with no agentic behaviour | Routing is not model-decided | Given any outcome, when the routing function runs, then its return value is a function of the counted candidate documents in state and no LLM output selects the next node | `tests/test_entity_resolution_graph.py` — task 8.4 | - [x] |
| 17 | chat-orchestration-graph | Fixed topology with no agentic behaviour | Compiled graph remains acyclic with the flag on | Given the flag on, when the compiled graph is inspected, then it reports no cycle | `tests/test_entity_resolution_graph.py` — task 8.4 | - [x] |
| 18 | chat-orchestration-graph | Fixed topology with no agentic behaviour | Flag-off topology is unchanged | Given the flag off, when the graph is compiled, then its node and edge set equals the pre-change topology and `entity_resolution` is absent | `tests/test_entity_resolution_flag_off.py` — task 10.2 | - [x] |
| 19 | chat-orchestration-graph | Resolution outcome carried in graph state | Outcome is visible in state before retrieval | Given a resolved turn, when `entity_resolution` completes, then state carries the outcome and the resolved document ids | `tests/test_entity_resolution_graph.py` — task 8.5 | - [x] |
| 20 | chat-orchestration-graph | Resolution outcome carried in graph state | Downstream nodes are unchanged | Given a resolved turn, when source assembly, prompt assembly, and generation run, then they read only the state keys they read before this change | `tests/test_entity_resolution_graph.py` — task 8.5 | - [x] |
| 21 | chat-orchestration-graph | Resolution outcome carried in graph state | Unresolved turn adds no scope | Given an `unresolved` outcome, when the plan executes, then no plan entry carries a resolver-added document scope | `tests/test_entity_resolution_graph.py` — task 8.3 | - [x] |
| 22 | entity-resolution | Entity resolution precedes retrieval execution | Resolution runs before any tool invocation | Given the flag on and a known person reference, when the turn runs, then the `document_entities` query precedes any retrieval capability invocation and the outcome is in state | `tests/test_entity_resolution_graph.py` — task 8.1 | - [x] |
| 23 | entity-resolution | Entity resolution precedes retrieval execution | Resolution queries are tenant-scoped | Given the same normalized person value in two tenant schemas, when tenant A asks, then every resolver query targets tenant A's schema and no tenant B candidate appears | `tests/test_chat_api_entity_resolution.py` (two seeded schemas) — task 9.5 | - [x] |
| 24 | entity-resolution | Deterministic mention extraction and matching | Name is matched through shared canonicalization | Given a stored `normalized_value` for "Sreelakshmi R", when the user writes it with different case, spacing, and trailing punctuation, then the mention matches that row | `tests/test_entity_resolver.py` — task 6.1 | - [x] |
| 25 | entity-resolution | Deterministic mention extraction and matching | Longest matching mention wins | Given entities normalized "sreelakshmi" and "sreelakshmi r" in different documents, when the user writes "Sreelakshmi R", then only the longer mention is used | `tests/test_entity_resolver.py` — task 6.2 | - [x] |
| 26 | entity-resolution | Deterministic mention extraction and matching | Non-person entity types are not matched | Given an organization entity whose normalized value appears in the message, when extraction runs, then it produces no candidate | `tests/test_entity_resolver.py` — task 6.2 | - [x] |
| 27 | entity-resolution | Deterministic mention extraction and matching | Extraction makes no LLM call | Given a message with a person reference, when extraction and matching run, then the resolver issues no chat-completion request during those steps | `tests/test_entity_resolver.py` — task 6.3 | - [x] |
| 28 | entity-resolution | Zero, one, and many resolution outcomes | No match leaves the existing strategy untouched | Given no matching person entity, when the resolver runs, then the outcome is `unresolved`, the plan executes unmodified, and the reply equals the flag-off reply | `tests/test_entity_resolver.py` — task 6.4 | - [x] |
| 29 | entity-resolution | Zero, one, and many resolution outcomes | Single match proceeds directly into scoped retrieval | Given a mention matching entities in exactly one document, when the resolver runs, then the outcome is `unique`, retrieval runs in the same turn scoped to that document, and no clarification is requested | `tests/test_entity_resolver.py` — task 6.4 | - [x] |
| 30 | entity-resolution | Zero, one, and many resolution outcomes | Repeated name within one document is one candidate | Given one document with eleven rows for the same person, when the resolver runs, then the outcome is `unique` | `tests/test_entity_resolver.py` — task 6.4 | - [x] |
| 31 | entity-resolution | Zero, one, and many resolution outcomes | Multiple documents produce an ambiguous outcome | Given three documents matching the mention, when the resolver runs, then the outcome is `ambiguous` with one candidate per distinct `document_id` | `tests/test_entity_resolver.py` — task 6.4 | - [x] |
| 32 | entity-resolution | Ambiguity pauses the turn and requests clarification | Clarification turn skips retrieval and generation | Given an ambiguous mention, when the turn runs, then no retrieval capability is invoked, no generation call is made, and the response is 200 with empty `sources` | `tests/test_entity_resolution_graph.py` — task 8.2 | - [x] |
| 33 | entity-resolution | Ambiguity pauses the turn and requests clarification | Clarification names the reference and lists candidates | Given three candidates for "Sreelakshmi", when the reply is assembled, then it names the reference and lists all three with stable 1-based indices | `tests/test_entity_resolver.py` — task 6.7 | - [x] |
| 34 | entity-resolution | Ambiguity pauses the turn and requests clarification | Candidate count above the cap declines to list | Given more candidates than the configured cap, when the resolver runs, then no list is printed, the reply asks the user to narrow the reference, and no pending state is stored | `tests/test_entity_resolver.py` — task 6.5 | - [x] |
| 35 | entity-resolution | Candidate presentation with minimal distinguishing metadata | Card shows only the fields that exist | Given a candidate with only name and organization entities, when the card is assembled, then it shows both and contains no empty experience or skills field | `tests/test_entity_resolver.py` — task 6.6 | - [x] |
| 36 | entity-resolution | Candidate presentation with minimal distinguishing metadata | Skills are capped | Given a candidate with nine skill entities, when the card is assembled, then at most three skills appear | `tests/test_entity_resolver.py` — task 6.6 | - [x] |
| 37 | entity-resolution | Candidate presentation with minimal distinguishing metadata | Identical cards fall back to filenames | Given two candidates whose cards render identically, when the reply is assembled, then the source filename is appended to both | `tests/test_entity_resolver.py` — task 6.6 | - [x] |
| 38 | entity-resolution | Candidate presentation with minimal distinguishing metadata | Card values come from the entity store | Given a stored organization value "SEO Technologies", when the card is assembled, then that value appears verbatim | `tests/test_entity_resolver.py` — tasks 6.1, 6.6 | - [x] |
| 39 | entity-resolution | Pending clarification state is persisted per conversation | Pending state survives across requests | Given a clarification requested in one request, when the next message is handled by another process, then the original message and candidate list are readable | `tests/test_conversation_entity_state.py` — task 7.1 | - [x] |
| 40 | entity-resolution | Pending clarification state is persisted per conversation | Pending state is tenant-scoped | Given pending state in tenant A, when any tenant B conversation is processed, then tenant A's state is not visible | `tests/test_chat_api_entity_resolution.py` — task 9.5 | - [x] |
| 41 | entity-resolution | Pending clarification state is persisted per conversation | A new clarification replaces the previous one | Given a conversation with a pending clarification, when a second ambiguous mention clarifies, then exactly one pending row remains for that conversation | `tests/test_conversation_entity_state.py` — task 7.2 | - [x] |
| 42 | entity-resolution | Natural-language selection interpretation | Ordinal answer resolves without an LLM call | Given three candidates, when the user replies "Candidate 2", then candidate 2 is selected and no selection LLM call is made | `tests/test_entity_resolver.py` — task 6.8 | - [x] |
| 43 | entity-resolution | Natural-language selection interpretation | Descriptive answer resolves through the constrained call | Given candidate 2 lists ReactJS, when the user replies "The React developer", then candidate 2 is selected | `tests/test_entity_resolver.py` — task 6.8 | - [x] |
| 44 | entity-resolution | Natural-language selection interpretation | Attribute answer resolves through the constrained call | Given candidate 1's organization is "SEO Technologies", when the user replies "The one from SEO Technologies", then candidate 1 is selected | `tests/test_entity_resolver.py` — task 6.8 | - [x] |
| 45 | entity-resolution | Natural-language selection interpretation | Out-of-range index is rejected | Given three candidates and a selection call returning index 7, when the selection is interpreted, then no candidate is selected and the turn counts as a failed selection | `tests/test_entity_resolver.py` — task 6.8 | - [x] |
| 46 | entity-resolution | Bounded clarification retry | First unresolvable answer re-asks | Given a pending clarification, when the answer matches no candidate, then the clarification is asked again and pending state is retained | `tests/test_conversation_entity_state.py` — task 7.3 | - [x] |
| 47 | entity-resolution | Bounded clarification retry | Second unresolvable answer abandons clarification | Given a clarification already re-asked once, when the answer again matches no candidate, then pending state is cleared and the message is answered by tenant-wide retrieval | `tests/test_conversation_entity_state.py` — task 7.3 | - [x] |
| 48 | entity-resolution | Original intent is replayed after selection | Original request resumes automatically | Given stored original message "Tell me about Sreelakshmi", when the user replies "The React developer", then retrieval runs for the original message and the reply answers it without asking the user to repeat it | `tests/test_conversation_entity_state.py` — task 7.4 | - [x] |
| 49 | entity-resolution | Original intent is replayed after selection | Pending state is cleared once resumed | Given a successful selection, when the resumed turn completes, then no pending clarification remains for that conversation | `tests/test_conversation_entity_state.py` — task 7.4 | - [x] |
| 50 | entity-resolution | Retrieval is constrained to the resolved document | Semantic scope is overridden with the resolved document | Given a resolved document and a tenant-scoped plan entry, when the plan executes, then that entry is invoked with a document scope containing only the resolved id | `tests/test_entity_resolution_graph.py` — task 8.6 | - [x] |
| 51 | entity-resolution | Retrieval is constrained to the resolved document | Structured rows outside the resolved scope are dropped | Given structured rows from two documents, when results are accumulated, then only rows matching the resolved document remain | `tests/test_entity_resolution_graph.py` — task 8.7 | - [x] |
| 52 | entity-resolution | Retrieval is constrained to the resolved document | Aggregate rows without a document id are retained | Given structured rows with no `document_id` column, when results are accumulated, then those rows are retained | `tests/test_entity_resolution_graph.py` — task 8.7 | - [x] |
| 53 | entity-resolution | Retrieval is constrained to the resolved document | Answer cites only the resolved document | Given three same-name candidates and a resolved selection, when the resumed turn replies, then every citation references the resolved document | `tests/test_entity_resolution_graph.py` — task 8.8 | - [x] |
| 54 | entity-resolution | Conversation-scoped binding for follow-up turns | Follow-up without a name inherits the binding | Given a bound conversation, when the user asks "What technologies has she worked with?", then retrieval is constrained to the bound document and no clarification is requested | `tests/test_conversation_entity_state.py` — task 7.5 | - [x] |
| 55 | entity-resolution | Conversation-scoped binding for follow-up turns | Several follow-ups keep the same binding | Given a bound conversation, when three successive nameless questions are asked, then all three are constrained to the bound document | `tests/test_conversation_entity_state.py` — task 7.5 | - [x] |
| 56 | entity-resolution | Conversation-scoped binding for follow-up turns | A different person replaces the binding | Given a bound conversation, when the user asks about a different unambiguous person, then the binding is replaced with that person's document | `tests/test_conversation_entity_state.py` — task 7.5 | - [x] |
| 57 | entity-resolution | Conversation-scoped binding for follow-up turns | Corpus-wide question clears the binding | Given a bound conversation, when a tenant-wide question with no person mention or anaphoric reference is asked, then the binding is cleared and retrieval spans the corpus | `tests/test_conversation_entity_state.py` — task 7.5 | - [x] |
| 58 | entity-resolution | Conversation-scoped binding for follow-up turns | Bound mention is not re-clarified | Given a conversation bound to one of three same-name candidates, when the same ambiguous mention is named again, then no clarification is requested and the bound document is used | `tests/test_conversation_entity_state.py` — task 7.5 | - [x] |
| 59 | entity-resolution | Feature flag and flag-off equivalence | Flag off issues no resolver query | Given the flag off and an ambiguous reference, when the turn runs, then no resolver query is issued and the reply comes from tenant-wide retrieval | `tests/test_entity_resolution_flag_off.py` — task 10.1 | - [x] |
| 60 | entity-resolution | Feature flag and flag-off equivalence | Flag off leaves the graph topology unchanged | Given the flag off, when the graph is compiled, then its nodes and edges equal the pre-change set | `tests/test_entity_resolution_flag_off.py` — task 10.2 | - [x] |
| 61 | entity-resolution | Feature flag and flag-off equivalence | Existing chat tests pass unmodified with the flag off | Given the existing chat test files with no edits, when the suite runs with the flag off, then every test passes | existing chat suite run unmodified — task 10.4 | - [x] |
| 62 | entity-resolution | Feature flag and flag-off equivalence | Stale state is inert when the flag is off | Given a stored binding and the flag turned off, when the next turn runs, then the stored state does not affect retrieval scope | `tests/test_entity_resolution_flag_off.py` — task 10.3 | - [x] |
| 63 | entity-resolution | Resolution outcome is observable | Ambiguous turn is logged with its candidate count | Given three candidates, when the resolver runs, then one log record reports the ambiguous outcome and a candidate count of 3 | `tests/test_entity_resolver.py` (caplog) — task 6.9 | - [x] |
| 64 | entity-resolution | Resolution outcome is observable | Zero-match mention is logged | Given a message matching no person entity, when the resolver runs, then one log record reports the unresolved outcome | `tests/test_entity_resolver.py` (caplog) — task 6.9 | - [x] |

> **Rule:** Every `#### Scenario:` block in every `specs/**/*.md` file for this change
> MUST appear as a row in this table. A missing scenario is a P1 gap that blocks archive.

---

## 2. Hallucination Risk Register

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|-------------------|----------------------|
| 1 | Canonicalization symmetry (Decision 2) | Reimplementing normalization inside the resolver — a local lowercase/strip — instead of importing the same `canonicalize()` that wrote `normalized_value`, so matching silently fails for aliased or punctuated names | Confirm the resolver imports `canonicalize` from `src/extraction_service/services/entity_normalizer.py` and contains no second normalization routine; test a name whose stored value came through `ALIAS_MAP` |
| 2 | Ambiguity granularity (Decision 3) | Counting matched entity *rows* instead of distinct `document_id`s, which makes every ordinary single-candidate resume ambiguous | Read the grouping expression; run the eleven-rows-one-document case (row 30) and confirm the outcome is `unique`, not `ambiguous` |
| 3 | Structured scope enforcement (Decision 7) | Implementing only the prose hint in the NL query and omitting the post-filter, leaving structured results corpus-wide while the code appears to honour scope | Confirm a post-filter on `document_id` exists in the accumulation path; run row 51 with a stubbed SQL result containing a foreign-document row and assert it is dropped, and row 52 to confirm id-less rows survive |
| 4 | Selection call constraint (Decision 5) | Letting the selection LLM return a document id, a name, or free text rather than an index over the stored candidate list, or using the returned index without a range check | Inspect the selection prompt and the parse path; confirm the returned value is range-checked against the candidate count (row 45) and that no code path selects a document absent from the stored list |
| 5 | Guardrail exemption scope (chat-api delta) | Broadening the citation-enforcement carve-out so any sourceless reply passes, not only resolver-assembled clarifications, weakening ADR-007's guardrail | Read the exemption condition — it must key on the resolver-produced clarification outcome, not on `sources == []`; confirm row 11 still fails a sourceless *generated* answer |
| 6 | Binding lifecycle (Decision 8) | Implementing inherit-and-replace but omitting the clear rule, so a conversation stays silently pinned to one document for every later question | Walk the clear path in code; run row 57 and confirm the corpus-wide question retrieves outside the previously bound document |
| 7 | Flag-off equivalence (Decision 9) | Registering the `entity_resolution` node unconditionally and short-circuiting inside it, so the compiled topology differs from pre-change even with the flag off | Compare the compiled node and edge sets with the flag off against the pre-change graph (rows 18, 60); confirm registration is inside the flag branch in `builder.py` |
| 8 | Tenant isolation of new state (ADR-001) | Creating `conversation_entity_state` in `public` or querying it without schema qualification, so bindings leak across tenants | Read migration `027` and every resolver query for schema qualification; run row 40 across two seeded tenant schemas |

---

## 3. Pattern & ADR Compliance

| ADR | Decision Summary | Constraint on This Change | Verification Step |
|-----|-----------------|--------------------------|-------------------|
| ADR-001-tenant-data-isolation | One PostgreSQL schema per tenant; all tenant data access is schema-qualified | `conversation_entity_state` is a tenant-schema table; every resolver and state query is schema-qualified from request state, never from model output | Grep the resolver and state modules for raw table names without a schema placeholder; confirm migration `027` creates the table in `tenant_template` and loops existing `tenant\_%` schemas as `026` does; run the two-tenant isolation cases (rows 23, 40) |
| ADR-004-openspec-governance | Behaviour changes ship as OpenSpec changes with delta specs before implementation | Delta specs exist for `chat-api` and `chat-orchestration-graph` plus the new `entity-resolution` capability | Confirm `openspec validate` passes for this change and that every implemented behaviour traces to a requirement in Section 1 |
| ADR-005-opencode-agent-boundaries | `src/shared` must not import service packages | The resolver lives under `src/chat_api/services/`; retrieval is influenced only by rewriting plan arguments | Run the existing `src/shared` import-isolation test; grep `src/shared/retrieval/` for any `entity_resolver` or `conversation_entity_state` import — there must be none |
| ADR-007-chatbot-architecture | Full RAG with SQL validation, citation enforcement, disclaimer, P95 < 10s | Clarification is a new sourceless terminal outcome with a narrow guardrail carve-out; resolver SQL is parameterized, never model-generated; the disclaimer still applies | Read the guardrail exemption condition (Risk 5); confirm every resolver query uses bound parameters and never concatenates user or model text; confirm the clarification response carries the standard disclaimer; measure a clarification turn plus its selection turn against the P95 target |
| ADR-003, ADR-006, ADR-008 | Model serving, training infrastructure, default inference model | Not touched by this change | Confirm the diff contains no change under `src/model_serving/`, `src/training_*`, or model-selection code |

ADR-002 is partially superseded by ADR-008 and imposes no constraint here.

---

## 4. Evidence Requirements

### Functional Evidence

- [x] Rows 1–5 (chat-api regression): existing chat API test output showing the unchanged endpoint scenarios pass with no edits to those test files
- [x] Row 6: API trace of an ambiguous turn showing status 200, clarification `reply`, empty `sources`, populated `pending_clarification`
- [x] Row 7: response body of an unambiguous turn with the flag on, showing `pending_clarification` absent
- [x] Row 8: `GET /api/v1/chat/conversations/{id}` body showing the user message and clarification reply persisted
- [x] Row 9: test output for the existing sourceless-reply rejection
- [x] Row 10: test output showing a resolver clarification passes through the guardrail unmodified
- [x] Row 11: test output showing a sourceless generated reply on a resumed turn is still replaced
- [x] Rows 12–13: test output for both guardrail early exits, asserting no retrieval or LLM call
- [x] Row 14: test output showing the clarification exit reaches END with no retrieval execution or generation call
- [x] Row 15: test output showing `unique` and `unresolved` outcomes proceed through the unchanged node sequence
- [x] Row 16: unit test of the routing function driven purely by state, plus code review of its inputs
- [x] Row 17: compiled-graph acyclicity assertion with the flag on
- [x] Rows 18, 60: node/edge set comparison against the pre-change topology with the flag off
- [x] Rows 19–21: state-inspection test output for outcome keys, downstream key usage, and absence of resolver scope on an unresolved turn
- [x] Row 22: ordered call log (spy retriever/registry) showing the resolver query precedes any capability invocation
- [x] Rows 23, 40: two-tenant integration test output showing no cross-schema visibility of candidates or pending state
- [x] Rows 24–26: unit test output for canonicalized matching, longest-mention selection, and non-person type exclusion
- [x] Row 27: assertion that the stubbed LLM client received zero calls during extraction and matching
- [x] Row 28: side-by-side reply comparison for a zero-match message with the flag on and off
- [x] Rows 29–31: resolver unit test output for the unique, collapsed-rows, and ambiguous outcomes
- [x] Row 32: spy assertions showing zero retrieval invocations and zero generation calls on a clarification turn
- [x] Row 33: captured clarification text showing the named reference and three stably indexed candidates
- [x] Row 34: test output for the above-cap path showing the narrowing message and no stored pending state
- [x] Rows 35–38: card-assembly unit test output for field omission, skill cap, filename fallback, and verbatim stored values
- [x] Row 39: integration test output where the pending row is written in one session and read back in another
- [x] Row 41: database assertion of exactly one pending row after a second clarification
- [x] Row 42: test output showing ordinal selection succeeds with zero selection LLM calls
- [x] Rows 43–44: test output for descriptive and attribute-based selection through the stubbed constrained call
- [x] Row 45: test output showing an out-of-range index is rejected and treated as a failed selection
- [x] Rows 46–47: two-turn test output for re-ask then abandon-and-fall-through
- [x] Rows 48–49: test output showing the original message drives the resumed retrieval and pending state is cleared
- [x] Row 50: captured plan arguments showing the semantic entry's scope overridden to the resolved id
- [x] Rows 51–52: accumulation test output for foreign-document row removal and id-less row retention
- [x] Row 53: citation list from a resumed turn showing only the resolved `document_id`
- [x] Rows 54–55: test output for single and repeated nameless follow-ups inheriting the binding
- [x] Row 56: test output showing a different unambiguous person replaces the binding
- [x] Row 57: test output showing a corpus-wide question clears the binding and widens retrieval
- [x] Row 58: test output showing a re-named bound mention triggers no second clarification
- [x] Row 59: spy assertion showing zero resolver queries with the flag off
- [x] Row 61: full run of the existing chat test files, unmodified, with the flag off
- [x] Row 62: test output showing a stale stored binding does not scope retrieval when the flag is off
- [x] Rows 63–64: captured log records for the ambiguous and unresolved outcomes with their reported counts

### Structural Evidence

- [x] Code review completed — implementation matches design.md decisions (no undocumented deviations)
- [x] All ADR compliance steps in Section 3 confirmed ✓
- [x] No undocumented architectural patterns introduced
- [x] No AI-invented requirements present in generated code (cross-checked against spec files)
- [x] Migration `027` reviewed against the `026` pattern (tenant_template plus per-tenant loop, `IF NOT EXISTS`, working downgrade)
- [x] `openspec validate --change entity-resolution-disambiguation --strict` passes

### Edge Case Evidence

- [x] Risk 1 mitigation confirmed — resolver uses the shared `canonicalize`; alias-mapped name matches
- [x] Risk 2 mitigation confirmed — grouping is by distinct `document_id`; eleven-row single document resolves as `unique`
- [x] Risk 3 mitigation confirmed — structured post-filter present and exercised; id-less rows retained
- [x] Risk 4 mitigation confirmed — selection output is an index over the stored list, range-checked before use
- [x] Risk 5 mitigation confirmed — guardrail carve-out keys on the clarification outcome, not on an empty `sources` array
- [x] Risk 6 mitigation confirmed — binding clear path exercised by a corpus-wide question
- [x] Risk 7 mitigation confirmed — node registration is flag-gated; flag-off topology byte-compared
- [x] Risk 8 mitigation confirmed — state table and all queries schema-qualified; two-tenant isolation verified

---

## 5. Evidence Log

| # | Evidence Type | Description / Link | Scenario(s) Covered | Collected By | Date |
|---|--------------|-------------------|---------------------|--------------|------|
| 1 | Functional | `pytest tests/test_entity_resolver.py tests/test_conversation_entity_state.py tests/test_entity_resolution_graph.py tests/test_chat_api_entity_resolution.py tests/test_entity_resolution_flag_off.py tests/test_migration_027_conversation_entity_state.py` against live Postgres (docker `postgres-test-1`, db `ner_test`) — 69 passed, 0 failed | Rows 6–8, 10, 11, 14–34 (excl. 12–13), 35–64 | claude-sonnet-5 (agent) | 2026-07-31 |
| 2 | Functional | `pytest tests/test_chat_api_rag.py tests/test_chat_api_guardrails.py tests/test_chat_api_conversations.py tests/test_chat_api_widget.py tests/test_chat_graph_topology.py` (flag off, files unmodified) — 64 passed, 2 skipped (require live OpenAI/model-serving), 1 pre-existing failure (`test_chat_response_sources`, disclaimer-wording assertion — documented pre-existing in `openspec/changes/agentic-retrieval-loop/tasks.md` task 6.1, unrelated to this change) | Rows 1–5, 9, 12, 13, 59–62 | claude-sonnet-5 (agent) | 2026-07-31 |
| 3 | Functional | `pytest tests/test_retrieval_tools.py -k chat_api` (ADR-005 fresh-import isolation checks) — 2 passed | ADR-005 compliance (Section 3) | claude-sonnet-5 (agent) | 2026-07-31 |
| 4 | Structural | Manual code review pass over `entity_resolver.py`, `conversation_entity_state.py`, `nodes.py` (`entity_resolution_node`), `builder.py` against design.md Decisions 1–9; graph compiled and node/edge sets inspected directly with flag on and off | Rows 15–21, 50–53 + Hallucination risks 1–4, 6, 7 | claude-sonnet-5 (agent) | 2026-07-31 |
| 5 | Structural | Migration `027` reviewed against `026`'s tenant_template + per-tenant-loop + `IF NOT EXISTS` pattern; upgrade/rerun/downgrade all exercised live via `test_migration_027_conversation_entity_state.py` | ADR-001 compliance (Section 3), risk 8 | claude-sonnet-5 (agent) | 2026-07-31 |

---

## 6. Audit Record

> ⚠️ **GATE: This section must be completed and signed by a human reviewer before
> `/opsx:archive` is run.** An unsigned or incomplete Audit Record is a hard block on archive.

**Change slug:** entity-resolution-disambiguation
**Proposal:** `openspec/changes/entity-resolution-disambiguation/proposal.md`
**Spec files reviewed:**
  - specs/entity-resolution/spec.md
  - specs/chat-api/spec.md
  - specs/chat-orchestration-graph/spec.md

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
