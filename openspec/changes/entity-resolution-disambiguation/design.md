## Context

Today a chat turn runs `guardrail -> orchestrator -> retrieval_execution -> source_assembly -> prompt_assembly -> generation` (`src/chat_api/graph/builder.py:12`). The `orchestrator` node makes one planning LLM call producing a `RetrievalPlan` of `semantic_retrieval` / `structured_retrieval` entries; `retrieval_execution` runs them concurrently and merges the evidence. Nothing in that path asks *which* entity the user means. When a name maps to several documents, `_accumulate` (`src/shared/retrieval/orchestrator.py:170`) ranks chunks from all of them together and generation answers from the top-scoring ones — a correct-looking answer about the wrong person.

Two existing pieces make disambiguation cheap. `document_entities` (migration `026`) stores one row per reconstructed logical entity with `document_id`, `entity_type`, `entity_value`, and an indexed `normalized_value`, so "which documents contain a person named X" is an index lookup. And `semantic_retrieval` already accepts `scope: {"type": "document", "document_ids": [...]}` (`src/shared/retrieval/tools/document_tools.py:70`), so constraining retrieval to a resolved document needs no new tool argument — the same mechanism `candidate_document_filtering_enabled` already uses inside `execute_plan`.

The binding constraint is statelessness: `chat_api` reconstructs conversation context per request purely from `chat_messages` (`src/chat_api/api/v1/chat.py:84`). A clarification that spans two HTTP requests therefore needs durable, tenant-scoped state.

## Goals / Non-Goals

**Goals:**

- Detect that a person reference in a question maps to more than one document *before* retrieval runs.
- Ask one clarification question with enough distinguishing metadata for the user to choose, and accept a natural-language answer.
- Resume the original request after selection without the user restating it.
- Constrain both semantic and structured retrieval to the resolved document for the resolved turn and for follow-ups in the same conversation.
- Leave the unambiguous path byte-for-byte as it is today, and leave the whole pipeline unchanged when the flag is off.

**Non-Goals:**

- Deciding whether two documents describe the same real person (cross-document entity resolution / identity matching).
- Fuzzy or phonetic name matching. Matching is exact on the canonicalized form.
- Any change to embeddings, chunking, the HNSW index, the reranker, or `SQLGenerator`'s whitelist and validation.
- Disambiguating non-person entities (organizations, skills) in this change.
- A portal UI for candidate selection. The API carries structured candidates; rendering them is a separate change.

## Currently-In-Force ADRs

| ADR | Decision Summary | Constraint on This Design |
|-----|-----------------|--------------------------|
| ADR-001-tenant-data-isolation | One PostgreSQL schema per tenant; all tenant data access is schema-qualified | `conversation_entity_state` is a tenant-schema table created for `tenant_template` and every existing tenant schema; every resolver query is schema-qualified from request state, never from LLM output |
| ADR-004-openspec-governance | Behaviour changes ship as OpenSpec changes with delta specs before implementation | This change carries delta specs for `chat-api` and `chat-orchestration-graph` alongside the new `entity-resolution` capability |
| ADR-005-opencode-agent-boundaries | `src/shared` must not import service packages | The resolver lives in `src/chat_api/services/`, not `src/shared/retrieval/`; it reaches retrieval only by rewriting plan arguments |
| ADR-007-chatbot-architecture | Full RAG with SQL validation, citation enforcement, disclaimer, P95 < 10s | The clarification turn is a new sourceless terminal outcome, so the citation-enforcement rule needs an explicit carve-out; resolver SQL is parameterized and never LLM-generated, so it sits outside the `SQLGenerator` validation path by construction |
| ADR-003, ADR-006, ADR-008 | Model serving, training infrastructure, default inference model | Not touched by this change |

ADR-002 is partially superseded by ADR-008 and is historical context only here.

## Decisions

### Decision 1: Resolve after planning, as a node between `orchestrator` and `retrieval_execution`

**Choice:** `entity_resolution` runs after `orchestrator` and before `retrieval_execution`. It reads `state["retrieval_plan"]`, and on a unique or already-bound resolution rewrites that plan's entries in place with a document scope; on ambiguity it returns a terminal reply and the graph routes to `END`.

**Rationale:** The plan is what retrieval actually executes. Rewriting it is the only injection point that constrains *both* capabilities without a second planning call, and it reuses the exact argument shape `execute_plan` already applies for candidate filtering. Running after the planner also means the planner's own view of the question is untouched, so no prompt regression is possible.

**Alternatives considered:**
- Resolve before `orchestrator` and rewrite the user message ("Sreelakshmi" → "Sreelakshmi R, document abc") — ruled out: it corrupts the message that later feeds `prompt_assembly` and generation, and leaks internal ids into prose the LLM may echo.
- Resolve inside `retrieval_execution` — ruled out: buries a user-facing interaction (asking a question) inside an execution step that has no path to a terminal reply, and the node already owns concurrency and budgets.
- Make it a tool the planner may call — ruled out: clarification is not evidence gathering; the planner cannot pause a turn, and leaving the decision to the LLM reintroduces the non-determinism this change exists to remove.

### Decision 2: Deterministic n-gram mention extraction, not an LLM extraction call

**Choice:** Generate 1–3 word n-grams from the user message, canonicalize each with the existing `canonicalize()` (`src/extraction_service/services/entity_normalizer.py:63`), and look them up against `document_entities.normalized_value` in one parameterized `IN` query restricted to person-typed entities. The longest matching n-gram wins when several overlap ("Sreelakshmi R" beats "Sreelakshmi").

**Rationale:** Adds no LLM call and no measurable latency to the common unambiguous turn — one indexed lookup against an index that already exists. It reuses the *same* canonicalization the ingestion path used to write `normalized_value`, so matching is symmetric by construction rather than by prompt luck. And it cannot hallucinate a name that is not in the store.

**Alternatives considered:**
- A dedicated LLM extraction call — ruled out: an extra round-trip on every turn (including the overwhelming majority with no ambiguity), plus a new failure mode where the model invents or reformats a name.
- Reusing the NER model on the question text — ruled out: adds a model-serving hop into the chat critical path, and questions are not the text distribution the model was trained on.
- Trigram / `pg_trgm` fuzzy matching — ruled out: explicitly out of scope, and it converts a precision problem into a recall problem that produces spurious clarification prompts.

### Decision 3: Ambiguity is counted over distinct `document_id`s

**Choice:** Group matched entity rows by `document_id`. Zero documents → no resolution. One document → unique. Two or more → ambiguous. Multiple rows for the same name within one document collapse into one candidate.

**Rationale:** The unit the user is choosing between is a document (one resume = one person here), and the unit retrieval is scoped to is `document_id`. A resume mentions its own candidate's name many times; counting rows would report every single-candidate resume as ambiguous, making the feature fire constantly on the one case it should stay silent for.

**Alternatives considered:**
- Per-entity-row candidates — ruled out for the reason above.
- Clustering rows into person identities across documents — ruled out: that is cross-document entity resolution, explicitly out of scope.

### Decision 4: Candidate cards assembled from `document_entities`, with a fixed field priority and empty-field omission

**Choice:** For each candidate document, select its entity rows and build a card from, in order: name (the matched `entity_value` in its document surface form), current organization, years of experience, up to three skills. Fields with no backing row are omitted. If two rendered cards are identical, `documents.filename` is appended to every card in the set.

**Rationale:** The available schema is generic (`entity_type` / `entity_value`), so the card cannot assume resume-specific columns — it can only project whatever types the tenant extracts. The fixed priority keeps the list scannable, and omission avoids printing empty labels. Filenames are the only guaranteed-unique discriminator, so they are the fallback rather than the default (they are noisy and may encode internal naming).

**Alternatives considered:**
- Always show all six proposed fields — ruled out: produces mostly-blank cards for sparse tenants and buries the discriminating field.
- Let an LLM write the cards — ruled out: it would be free to paraphrase or invent details about a person, which is exactly the failure mode this change targets.

### Decision 5: Ordinal parsing first, one constrained LLM call as fallback for natural-language selection

**Choice:** When a pending clarification exists, the next turn is interpreted as a selection. A leading ordinal or bare index ("2", "candidate 2", "the second one") is parsed with a regex. Otherwise one LLM call receives only the candidate cards and the user's answer, and must return a candidate index or `none`; the return value is validated against the candidate count before use. `none`, or an out-of-range index, re-asks once; a second failure abandons the clarification, clears the pending state, and runs the original message through ordinary tenant-wide retrieval.

**Rationale:** The proposal requires free-form answers ("the React developer"), which regexes cannot cover. Constraining the model's output to an index over a closed list means the LLM chooses among options the resolver produced — it cannot introduce a document. The bounded retry prevents a conversation from getting stuck in a clarification loop.

**Alternatives considered:**
- Ordinals only — ruled out: fails the stated requirement.
- Keyword-overlap scoring against card fields — ruled out: brittle for "the React developer" when the card says `ReactJS`, and it silently mis-picks rather than saying `none`.
- Unbounded re-asking — ruled out: a user who cannot see the difference is trapped; falling through to normal retrieval is strictly better than a dead end.

### Decision 6: Persist conversation state in a tenant-schema table, one row per conversation

**Choice:** New table `{tenant_schema}.conversation_entity_state` with `conversation_id` as primary key, holding the pending original message, the candidate list as `JSONB`, the resolved `document_id`, the resolved display name, and `updated_at`. Written and cleared by the resolver within the request's existing session and commit.

**Rationale:** The API is stateless between requests and today rebuilds context only from `chat_messages`; a clarification necessarily spans two requests. One row per conversation makes "is there a pending clarification?" and "is there a binding?" single primary-key reads, and makes clearing idempotent. Tenant-schema placement inherits ADR-001 isolation with no extra predicate to forget.

**Alternatives considered:**
- Re-derive state by parsing the last assistant message from `chat_messages` — ruled out: parsing prose to recover machine state is fragile, and it breaks the moment the clarification wording changes.
- In-process memory or Redis — ruled out: the service runs multiple replicas (no sticky sessions), and a new infrastructure dependency is disproportionate for one row per conversation.
- Extra columns on `conversations` — ruled out: mixes a transient, frequently-cleared concern into a long-lived record, and every conversation would carry mostly-null columns.

### Decision 7: Semantic scope by argument, structured scope by argument *and* post-filter

**Choice:** For `semantic_retrieval` entries, set `scope = {"type": "document", "document_ids": [resolved]}`, overriding any scope the planner chose. For `structured_retrieval`, append an explicit document constraint to the natural-language `query` argument *and* drop any returned row whose `document_id` is present and not the resolved one.

**Rationale:** Semantic scope is enforced structurally by the retriever's metadata filter, so the argument is sufficient. Structured retrieval goes through LLM-generated SQL, which may ignore an instruction embedded in prose — the post-filter is the actual guarantee, and the prompt hint merely improves the SQL the model writes. Rows without a `document_id` column (aggregates, counts) are kept, since dropping them would silently empty legitimate results.

**Alternatives considered:**
- Prompt hint only — ruled out: unenforced; the entire point is to stop relying on a model's judgement for scoping.
- A new `document_ids` argument on `structured_retrieval` — ruled out: changes the tool contract specified in `retrieval-tools-and-eval` and pushes scope enforcement into `SQLGenerator`, a larger blast radius than post-filtering.
- Post-filter only — ruled out: the model would still generate corpus-wide SQL and we would discard most of a 100-row result, wasting the query budget on rows we drop.

### Decision 8: Sticky binding with explicit replace and clear rules

**Choice:** Once resolved, the binding applies to every later turn in the conversation whose message contains no person mention of its own. A turn whose mention resolves to a different document replaces the binding. A turn the planner scopes tenant-wide *and* that contains no person mention and no anaphoric reference clears it. Ambiguity is not re-checked while a binding is active for the same mention.

**Rationale:** The proposal's follow-up examples ("what technologies has she worked with?") carry no name at all, so inheritance is what makes them work. Explicit replace-on-different-mention keeps the user from having to say "forget that person", and skipping re-checks means the user is asked at most once per person per conversation.

**Alternatives considered:**
- Bind only for the immediately following turn — ruled out: the stated requirement is that a series of follow-ups keeps referring to the same candidate.
- Never clear — ruled out: a conversation that moves to a corpus-wide question would silently return answers from one document only, a new and subtler version of the bug being fixed.

### Decision 9: Feature flag, default off

**Choice:** `entity_resolution_enabled: bool = False`. With the flag off, `entity_resolution` is not registered as a node and the compiled topology is identical to today's; `pending_clarification` is always absent from responses. The migration runs regardless — the table is created but unused.

**Rationale:** Matches the existing convention (`candidate_document_filtering_enabled`, `chat_agentic_retrieval`) and keeps a behaviour change that adds a user-visible interaction reversible without a deploy. Creating the table unconditionally keeps enabling the flag a pure configuration change.

**Alternatives considered:**
- Ship on by default — ruled out: a false-positive clarification is more disruptive than the bug it prevents, so it warrants a measured rollout.
- Gate the migration on the flag — ruled out: turning the flag on would then require a migration, defeating the purpose.

## Risks / Trade-offs

- [False-positive clarification: two documents mention the same person, but only one is *about* them (e.g. a referee named on someone else's resume), so the user is asked to choose between a real candidate and a bystander] → Candidate cards are built from each document's own entity rows, which makes the bystander card visibly thin; the cap plus the "abandon after two failed selections" rule bounds the damage; the flag allows measuring false-positive rate before enabling.
- [Extraction quality drives resolution quality: a name the extractor missed produces zero matches, and the turn silently reverts to today's ambiguous behaviour] → Zero matches is a specified, non-degraded outcome that preserves current behaviour exactly; the resolver logs zero-match mentions so recall gaps are visible.
- [Sparse `document_entities` for a tenant produces indistinguishable candidate cards] → Filename fallback (Decision 4), and an ambiguity that cannot be presented distinctly is still better surfaced than silently resolved by rank.
- [A user who ignores the clarification and asks something else entirely gets their new question interpreted as a selection] → The constrained selection call may return `none`, which routes the message back through ordinary retrieval rather than forcing a pick; pending state is cleared after the second failure.
- [Selection LLM call adds latency to the second turn] → It runs only when the answer is not an ordinal, replaces nothing else in that turn's budget, and the clarification turn it follows skipped retrieval and generation entirely — net latency across the two turns stays under the ADR-007 P95 target.
- [`normalized_value` matching is exact, so a mention with a typo resolves to nothing] → Accepted: fuzzy matching is out of scope, and a miss degrades to today's behaviour rather than to a wrong scope.
- [Stale binding after the user mentally switches candidates without saying so] → Replace-on-different-mention and clear-on-corpus-wide-question (Decision 8); the resolved candidate's name appears in the answer's citations, so a wrong binding is visible to the user.

## Migration Plan

1. Ship migration `027_conversation_entity_state.py` following the `026` pattern: create the table in `tenant_template`, then loop existing `tenant\_%` schemas. `IF NOT EXISTS` throughout; no backfill, no data migration, no lock on any hot table.
2. Deploy the code with `entity_resolution_enabled=false`. The graph, responses, and latency are unchanged; the new table stays empty. Existing chat tests pass unmodified as the flag-off proof.
3. Seed a staging tenant with two or more same-name resumes and enable the flag there. Verify: clarification fires, natural-language selection resolves, follow-ups inherit the binding, and unambiguous questions never clarify.
4. Enable per production tenant, watching the ratio of clarification turns to total turns. A rate materially above the seeded same-name rate indicates false positives (likely Decision 3 or the person-type set) and is the signal to turn the flag back off.

**Rollback:** set `entity_resolution_enabled=false` — no deploy, no data change. Rows in `conversation_entity_state` are inert when the flag is off; the next turn of any conversation proceeds as today whether or not a stale row exists. The `027` downgrade drops the table and is only needed for a full code revert.

## Open Questions

1. Person-typed entity set: raw `PER` / `PERSON` plus tenant types whose `entity_definitions.base_label_mapping` maps to `PER`. Needs confirmation against a live tenant's configured types before the resolver's default is fixed.
2. `entity_resolution_max_candidates` default of 5, and whether exceeding it should ask the user to narrow the question (assumed) or show the top five with a "showing 5 of N" note.
3. Whether appending `documents.filename` to indistinguishable cards is acceptable for tenants whose filenames encode internal identifiers.
4. Whether the binding should carry a TTL or turn count rather than living for the whole conversation.
5. No in-force ADR needs revisiting. ADR-007's citation-enforcement guardrail is *narrowed* — a clarification reply carries no sources — which is recorded as a delta on the `chat-api` spec rather than an ADR change. If review decides that narrowing is architecturally significant, the adr step should record it as a superseding ADR instead.
