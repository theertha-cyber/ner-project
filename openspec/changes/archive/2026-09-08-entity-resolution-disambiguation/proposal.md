## Why

The retrieval pipeline assumes an entity reference in a question identifies exactly one document. It does not. When a tenant holds three resumes for candidates named "Sreelakshmi", `plan_retrieval` (`src/shared/retrieval/orchestrator.py:112`) plans a tenant-wide `semantic_retrieval`, `_accumulate` ranks chunks from all three resumes by similarity, and `generation_node` answers from whichever chunks ranked highest. The answer is grounded in retrieved context and still about the wrong person, with citations that make it look correct. Ranking cannot recover intent the user never expressed; the ambiguity has to be detected and resolved with the user before retrieval runs.

The prerequisite is already in place: `normalized-entity-store` shipped `document_entities` (`alembic/versions/026_document_entities.py`), one row per reconstructed logical entity with `document_id`, `entity_type`, `entity_value`, and an indexed `normalized_value`. That table makes "which documents contain a person named X" an indexed lookup rather than an inference.

## What Changes

- Add an **entity resolution** stage as a new LangGraph node (`entity_resolution`) between `orchestrator` and `retrieval_execution`. It runs after planning so the plan is already in state and can be rewritten with a resolved scope.
- **Mention extraction is deterministic, not a new LLM call.** The resolver generates 1–3 word n-grams from the user message, canonicalizes them with the existing `canonicalize()` (`src/extraction_service/services/entity_normalizer.py:63`), and matches them against `document_entities.normalized_value` restricted to person-typed entities. Zero added planning latency, no extra token cost.
- **Three resolution outcomes**, matching the number of distinct `document_id`s a matched mention maps to:
  - *zero* — state untouched, the existing tenant-wide plan executes exactly as today;
  - *one* — the resolved `document_id` is injected as a `scope` into the plan's `semantic_retrieval` entries and as a document constraint on `structured_retrieval`, then retrieval proceeds normally in the same turn;
  - *many* — retrieval is skipped, the turn terminates with a deterministically formatted clarification question listing the candidates, and the pending state is persisted.
- **Candidate cards** are assembled from `document_entities` rows of each candidate document plus `documents.filename`: name, current organization, years of experience, and up to three distinguishing skills, with fields omitted when absent and `filename` as the last-resort discriminator.
- **Selection is interpreted on the next turn.** An ordinal ("2", "candidate 2") is parsed deterministically; anything else ("the React developer", "the one from SEO Technologies") is resolved by one constrained LLM call that may only return a candidate index or "none". An unresolvable answer re-asks once, then abandons the clarification and falls through to ordinary retrieval.
- **The original intent is replayed, not re-typed.** The pending turn stores the original user message; on successful selection the resolver restores it as the message that retrieval and generation operate on.
- **The binding is sticky for the conversation.** Follow-ups with no person mention of their own ("what technologies has she worked with?") inherit the resolved document scope. A mention that resolves elsewhere replaces the binding; an explicitly tenant-wide question clears it.
- **New per-conversation state table** `conversation_entity_state` (tenant-schema, migration `027`) holding at most one row per conversation: the pending original message, the candidate list, and the resolved document binding. Required because the chat API is stateless between requests and today reconstructs context only from `chat_messages`.
- **Additive API field** `pending_clarification` on `ChatResponse`, carrying the structured candidate list so the portal can render selectable cards. The `reply` string already contains the same question in prose, so existing clients are unaffected. Not breaking.
- **Feature-flagged**: `entity_resolution_enabled` (default `false`). With the flag off the compiled graph and every response are identical to today's.

## Capabilities

### New Capabilities

- `entity-resolution`: mention extraction and matching against `document_entities`; the zero/one/many resolution contract; candidate card assembly and minimal distinguishing-field selection; the clarification turn and its short-circuit of retrieval and generation; selection interpretation (ordinal and natural-language) with its bounded retry; original-intent replay; conversation-scoped binding lifecycle (set, inherit, replace, clear); scope injection into the retrieval plan; tenant isolation and flag-off equivalence.

### Modified Capabilities

- `chat-api`: the RAG chat endpoint gains a second terminal outcome — a clarification reply produced without retrieval, carrying no sources and an additive `pending_clarification` field — and the guardrail source-citation requirement must admit that reply as a legitimate sourceless response.
- `chat-orchestration-graph` (specified in the unarchived `langgraph-orchestration` change): the fixed topology gains one node and one conditional edge (`entity_resolution -> END` on clarification), and `ChatState` gains resolution keys. The graph stays acyclic and free of LLM-decided routing between retrieval stages.

## Impact

**Code**
- `src/chat_api/services/entity_resolver.py` (new) — mention extraction, candidate lookup, card assembly, selection interpretation.
- `src/chat_api/services/conversation_entity_state.py` (new) — read/write/clear of the per-conversation binding and pending clarification.
- `src/chat_api/graph/nodes.py` — new `entity_resolution_node`; existing nodes unchanged.
- `src/chat_api/graph/builder.py` — node registration and the clarification conditional edge, both flag-gated.
- `src/chat_api/graph/state.py` — additive keys: `conversation_id`, `resolved_document_ids`, `entity_resolution_outcome`, `pending_clarification`, `original_message`.
- `src/chat_api/api/v1/chat.py` — passes `conversation_id` into the graph and surfaces `pending_clarification`; persists the clarification turn as a normal assistant message.
- `src/chat_api/api/v1/schemas.py` — `CandidateEntity`, `PendingClarification`, additive `ChatResponse.pending_clarification`.
- `src/shared/config.py` — `entity_resolution_enabled`, `entity_resolution_max_candidates`, `entity_resolution_person_types`.
- `alembic/versions/027_conversation_entity_state.py` (new) — tenant-template and per-tenant table creation, matching the loop pattern used by `026`.

**Not touched**: embeddings, chunking, the vector index, `RerankingRetriever`/`CrossEncoderReranker`, `SQLGenerator`'s whitelist and validation, and the tool contract in `src/shared/retrieval/tools/`. The resolver constrains retrieval through the existing `scope` argument on `semantic_retrieval` — no new tool, no new tool argument.

**Operational**
- Unambiguous turns: +1 indexed SQL query (`normalized_value` index already exists), no added LLM call.
- Ambiguous turns: retrieval and generation are *skipped*, so the clarification turn is cheaper and faster than a normal turn.
- Selection turns: +1 short constrained LLM call, only when the answer is not an ordinal.

**Out of scope**: cross-document entity resolution, fuzzy identity matching between people, knowledge-graph construction, reranking changes, embedding changes, and vector database changes.

## Open Questions

1. **Which entity types are person-like.** Assumption: raw `entity_type` values `PER` and `PERSON`, plus any tenant type whose `entity_definitions.base_label_mapping` maps to `PER`. Confirm this covers tenant-defined resume schemas.
2. **Ambiguity granularity.** Assumption: ambiguity is counted over distinct `document_id`s, so two identically-named people in one document read as one candidate. Confirm — the alternative is per-entity-row candidates, which produces duplicate cards for the common single-resume case.
3. **Candidate cap.** Assumption: `entity_resolution_max_candidates = 5`; above that the resolver declines to clarify and asks the user to narrow the question instead of printing a long list. Confirm the cap value.
4. **Distinguishing fields when candidates are indistinguishable.** Assumption: when two candidate cards render identically, `documents.filename` is appended to both. Confirm that exposing filenames in chat is acceptable for this tenant.
5. **Binding lifetime.** Assumption: the binding lives for the conversation with no TTL, and is cleared by a mention resolving elsewhere or an explicitly corpus-wide question. Confirm no expiry is wanted.
6. **Ship state of the flag.** Assumption: `entity_resolution_enabled` ships `false` and is enabled per environment after the disambiguation tests pass against seeded same-name resumes.
