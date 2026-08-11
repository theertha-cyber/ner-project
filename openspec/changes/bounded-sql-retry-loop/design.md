## Context

### The pipeline as it exists today

A chat turn travels this path. Every stage below was read directly from the current source.

| Stage | File / function |
|---|---|
| HTTP entry | `src/chat_api/api/v1/chat.py` → `RAGOrchestrator.execute_with_clarification[_stream]` (`src/chat_api/services/rag_orchestrator.py:51,71`) |
| Graph invoke | `RAGOrchestrator._run_graph` (`rag_orchestrator.py:129`) → `build_chat_graph` (`src/chat_api/graph/builder.py:19`) |
| Guardrails | `guardrail_node` (`src/chat_api/graph/nodes.py:118`) — blocked types, domain classifier |
| **Query planning** | `orchestrator_node` (`nodes.py:141`) → `plan_retrieval` (`src/shared/retrieval/orchestrator.py:112`) — **one** LLM tool-calling call emitting `PlanEntry` items for `semantic_retrieval` / `structured_retrieval` |
| Entity resolution | `entity_resolution_node` (`nodes.py:171`), flag-gated |
| Plan execution | `retrieval_execution_node` (`nodes.py:283`) → `execute_plan` (`orchestrator.py:211`), concurrent, one `AsyncSession` per invocation |
| Structured capability | `StructuredRetrievalTool.call` (`src/shared/retrieval/tools/entity_tools.py:27`) → `run_tool` (`tools/base.py:127`) → `context.sql_search` |
| `sql_search` binding | `RAGOrchestrator._sql_source` (`rag_orchestrator.py:147`) |
| **SQL generation** | `SQLGenerator.generate_sql` (`src/chat_api/services/sql_generator.py:90`) — one LLM call, prompt built inline |
| Prompt grounding | `SQLGenerator._fetch_known_entity_types` (`sql_generator.py:279`) — `SELECT DISTINCT entity_type` |
| **SQL validation** | `SQLGenerator.validate_sql` (`sql_generator.py:220`) — whitelist, SELECT-only, LIMIT, UNION/subquery checks; raises `SQLValidationError`; also runs the deterministic repairs `_fix_document_name_reference` and `_force_nulls_last_on_desc` |
| **SQL execution** | `SQLGenerator.execute_sql` (`sql_generator.py:261`) — `SET search_path TO {schema}`, `BEGIN READ ONLY`, `asyncio.timeout(10)` |
| **Result handling** | `SQLGenerator.generate_and_execute` (`sql_generator.py:293`) — `try/except → return None` |
| Result accumulation | `_accumulate` (`orchestrator.py:170`) — sets `sql_error` only when *all* structured invocations reported `ToolResult.error` |
| Source assembly | `source_assembly_node` (`nodes.py:328`) — `Source(source_type="sql", …)` + top-3 chunks, then `_enrich_citations` |
| Prompt assembly | `prompt_assembly_node` (`nodes.py:366`) → `ContextAssembler.assemble` (`services/context_assembler.py:82`) |
| **Answer generation** | `generation_node` (`nodes.py:379`) → `GuardrailService.enforce_sources` (`services/guardrails.py:97`), `FALLBACK_REPLY` when sources are empty |

### The defect

Two facts, taken together, are the whole problem.

1. `generate_and_execute` ends in `except Exception: return None`. A whitelist rejection, an `UndefinedColumn` error, a query timeout, and a perfectly correct query that matched nothing all produce the identical return value.
2. `StructuredRetrievalTool`'s executor does `return (rows or []), False` — so `None` becomes an empty, **successful** `ToolResult`. `result.error` stays `None`, `_accumulate` sets no `sql_error`, and the failure is gone from the system by the time state is written.

There is therefore no place downstream that *could* trigger a retry even if it wanted to, and the generator gets exactly one shot with only a bare list of entity type names as grounding against a dataset we already know is polluted.

### Constraints shaping this design

- Tenant isolation is structural: `schema` reaches SQL only via `ToolContext`, built from authenticated request state in `retrieval_execution_node`'s `context_factory` (`nodes.py:294`). `FORBIDDEN_ARG_KEYS` (`tools/base.py:10`) forbids any tool from even declaring a tenancy argument. Nothing here may weaken that.
- The graph is specified as a fixed DAG whose routing is a pure function of state, never an LLM's choice (`builder.py:19` docstring; `redesign-retrieval-orchestration`'s *Plan-then-execute with no re-planning cycle* requirement). A LangGraph cycle would violate that requirement.
- `structured_retrieval` may legitimately be invoked more than once per plan (`orchestrator.py` supports multiple entries per capability), so "retries per turn" is not a meaningful unit — retries belong per invocation.
- The 8s `retrieval_deadline_seconds` budget and `ToolContext.deadline` already exist and are enforced by `run_tool` before dispatch.

## Goals / Non-Goals

**Goals:**

- Turn one-shot SQL into a bounded generate → validate → execute → inspect loop, capped at a configured number of attempts, that exits the instant an attempt succeeds.
- Classify each attempt's outcome explicitly, so an execution failure is never laundered into a legitimate empty result.
- Feed the previous attempt's SQL and a sanitized outcome back into the generator so a retry can reason differently rather than re-emit the same query.
- Ground generation in bounded, representative, tenant-scoped entity values in addition to type names.
- Make every attempt observable in logs and internal trace state.
- Preserve the security model, the graph topology, and the entire answer-generation pipeline byte-for-byte.

**Non-Goals:**

- Cleaning, normalizing, backfilling, deduplicating, or canonicalizing the existing polluted entity data. This change makes the query engine robust *despite* that data.
- Tenant-owned aliases, vocabulary clustering, extraction quality gates, cardinality rules, document hashing.
- Replacing free-form generated SQL with a constrained structured query representation and deterministic SQL construction. That is the plausible long-term direction; it is not this change.
- Any change to answer generation, citations, vector retrieval, reranking, response schema, or chat UX.
- Guaranteeing that a retried query is *better* than the first. The loop bounds cost and surfaces failure honestly; it does not promise recovery.

## Currently-In-Force ADRs

Supersession graph: ADR-008 partially supersedes ADR-002; ADR-009 partially supersedes ADR-006. Neither touches this area. ADR-010 has no `Supersedes` field. All ten ADRs are otherwise in force; only the following constrain this design.

| ADR | Decision Summary | Constraint on This Design |
|-----|-----------------|--------------------------|
| ADR-001 Tenant Data Isolation via Separate Database Schemas | Per-tenant Postgres schemas; no cross-tenant leakage of documents, extracted data, or indexes | The schema for every attempt — including the entity-profile queries — must come from authenticated request state, never from generated SQL or the user's question. `search_path` is set server-side per execution, exactly as today. |
| ADR-007 Chatbot Architecture with Full RAG and Guardrails | Three-source RAG; SQL validation layer mandatory; read-only transactions with timeouts; citation enforcement; graceful degradation when a source is unavailable; P95 < 10s | Every retry must re-enter `validate_sql` and `execute_sql` — no attempt may bypass validation. Exhausted retries must degrade gracefully via the existing fallback rather than fabricate an answer. The attempt cap and the existing 8s deadline together protect the P95 target. |
| ADR-004 OpenSpec Governance | Spec-driven traceability for every change | Behaviour lands as spec requirements with scenarios before implementation; verification maps scenarios to tests. |

## Decisions

### Decision 1: The loop lives inside `SQLGenerator.generate_and_execute`, not in the graph

**Choice:** Implement the attempt loop as a `for` loop inside `generate_and_execute`. The LangGraph topology in `builder.py` is not touched.

**Rationale:** `generate_and_execute` is already the single funnel through which every structured retrieval passes, and it already holds the three things a retry needs — `session`, the server-selected `schema`, and both the validate and execute calls. Keeping the loop there means "every retry uses the same validation and execution path as the first attempt" is true by construction rather than by discipline. It also keeps retries scoped per *invocation*, which is the correct unit: a plan may contain several `structured_retrieval` entries, executed concurrently, each answering a different sub-question.

**Alternatives considered:**
- *A LangGraph cycle (`retrieval_execution` → conditional edge → back).* Ruled out: it violates the in-force "fixed topology, no re-planning cycle" requirement, would re-run semantic retrieval and reranking on every SQL retry, and cannot express per-invocation retry when a plan has multiple structured entries.
- *A retry wrapper in `_sql_source` or `StructuredRetrievalTool`.* Ruled out: those layers see only `rows | None`; to classify an outcome they would need the validation error, the DB error, and the generated SQL — i.e. exactly the information `generate_and_execute` already has and would have to re-export.

### Decision 2: Explicit outcome classification replaces the catch-all `except`

**Choice:** Each attempt produces an `SQLAttempt` record with an outcome drawn from a closed set:

| Outcome | Source | Retryable |
|---|---|---|
| `success` | ≥1 row, or 0 rows with no defect signal | — (terminal, returns rows) |
| `generation_error` | LLM call raised, or returned empty/unusable text | yes |
| `validation_error` | `validate_sql` raised `SQLValidationError` | yes |
| `execution_error` | `execute_sql` raised (Postgres error, or the timeout `SQLValidationError`) | yes |
| `empty_with_defect` | 0 rows **and** a deterministic defect explains it | yes |

`empty_unexplained` is not a separate outcome — it is `success`. That is deliberate and is the subject of Decision 3.

**Rationale:** Retry decisions must be made on evidence, not on a bare exception type. Naming the outcomes also gives logging, tracing, and tests a stable vocabulary.

**Alternatives considered:**
- *Retry on any exception.* Ruled out: it conflates a deterministic generation defect (worth another LLM call) with an infrastructure failure such as a dead connection (where a second identical attempt just burns the deadline).

### Decision 3: Zero rows is a legitimate answer unless a deterministic defect explains it

**Choice:** A zero-row result is retried **only** when the executed SQL compares `entity_type` against a string literal that is not among the tenant's actual entity types. Every other zero-row result is returned as a successful, genuinely empty answer.

**Rationale:** This is the design's most consequential judgement, so the reasoning is recorded in full.

The system has no ground truth about whether a question *should* have matched something. Nothing in the current architecture — not the plan, not the chunks, not the entity profile — can distinguish "no candidate knows Rust" from "the query looked for Rust in the wrong column." Inventing a proxy for that distinction would be inventing certainty we do not have, and the failure mode is asymmetric and bad: a retry prompted with "your query returned nothing, try again" pushes the model to loosen filters, and a loosened query returns rows that do not answer the question. The downstream model cannot see the SQL (`sql_generator.py:122`) and will faithfully narrate whatever rows it is handed. **A confidently wrong answer is worse than an honest empty one**, and the existing `FALLBACK_REPLY` path already handles honest empties acceptably.

The `entity_type` literal check is admitted because it is not a heuristic at all — it is a decidable contradiction. The generator prompt already states that a type not on the tenant's list "matches nothing at all, however natural its name sounds," and the tenant's complete type list is fetched before generation anyway (Decision 5). A query filtering on `entity_type = 'EMPLOYER'` when the tenant only has `ORG`, `PER`, `SKILL` is *proven* incapable of matching, independent of what data exists. Retrying that is recovery, not guessing.

**Alternatives considered:**
- *Retry on any zero-row result.* Ruled out for the asymmetry argument above; also the dominant cost driver, since genuine empties are common.
- *An LLM judge asked "does this empty result look wrong?"* Ruled out: it is an extra call on the slowest path, and it is the same model that wrote the query being asked to grade its own output — a weak signal at real cost.
- *Probing whether each equality literal exists for its entity type* (`SELECT 1 FROM document_entities WHERE entity_type = … AND normalized_value = … LIMIT 1`). This is genuinely deterministic and would be the natural second signal — a literal that exists nowhere explains the empty result exactly. Deferred, not rejected: it requires extracting literal/column/type triples from generated SQL, which needs real parsing to be safe, plus one bounded query per attempt. Recorded as the intended follow-up if the entity-type signal proves too narrow in practice.
- *Comparing row count against a prior successful attempt.* Ruled out: no such history exists per turn.

### Decision 4: Failures propagate as `ToolResult.error`; the sink carries the trace

**Choice:** When every attempt fails, `generate_and_execute` raises `SQLGenerationFailed` (carrying the attempt trace) rather than returning `None`. `run_tool`'s existing `except Exception` converts it into `ToolResult(error=…)`, which flows through the untouched `_accumulate` into `ChatState["sql_error"]`. Separately, every attempt — success or failure — is appended to a caller-supplied `attempt_sink` list, mirroring the `degraded_sink` pattern already used by `RerankingRetriever.retrieve` (`tools/document_tools.py:39`).

**Rationale:** The existing machinery for "a structured invocation failed" is already built and currently never fires, because the failure is swallowed two layers below. Raising is the smallest change that makes `sql_error` mean what its name says, and it satisfies the requirement that a failed query never be reported as a successful empty result. Using the established sink pattern for the trace avoids widening the `SqlSearch` return type, which several call sites and tests depend on.

Note the deliberate asymmetry: a *successful* empty result still returns `[]` with no error, exactly as today. Only exhausted-retry failure raises.

**Alternatives considered:**
- *Return a rich result object from `generate_and_execute`.* Ruled out: `SqlSearch` is a typed protocol in `src/shared` (`tools/base.py:24`) consumed by the tool layer; changing its return type ripples into the tool, the orchestrator's accumulation, and the eval harness for no behavioural gain.
- *Logs only, no trace in state.* Rejected as the primary mechanism (the change must be debuggable from a captured turn, not only from a log aggregator), but retained as the fallback if sink plumbing proves too invasive in review.

### Decision 5: One bounded tenant entity profile, fetched once per invocation

**Choice:** Replace the single `SELECT DISTINCT entity_type` with an `EntityProfile` assembled from two bounded queries, fetched **once before the loop** and reused by every attempt:

1. The complete type list — the existing query, unchanged, so no type ever disappears from the prompt (types whose rows all have NULL `normalized_value` must still be listed; the dataset is known to contain those).
2. Top-N most frequent non-null `normalized_value` per type, via a `ROW_NUMBER() OVER (PARTITION BY entity_type ORDER BY COUNT(*) DESC)` window over a grouped scan, with three hard caps: `sql_entity_sample_values_per_type` (default 8), `sql_entity_sample_max_values` (default 120 across all types), and per-value character truncation.

Rendered into the prompt as a type-with-examples block. Both queries run after the same server-set `SET search_path TO {schema}`; neither takes any input derived from the user's question.

**Rationale:** The generator's hardest job on this dataset is guessing how a concept is spelled — the prompt itself already devotes a paragraph to the fact that narrative values need `ILIKE` while canonical ones take `=`. Showing eight real values per type replaces that guess with evidence, and it is the single highest-leverage input to first-attempt success. Fetching once and reusing keeps retries cheap and keeps the profile identical across attempts, so a retry differs only by the feedback block.

**Alternatives considered:**
- *Question-conditioned sampling* (fetch values similar to terms in the question). Ruled out on isolation grounds: it lets user input influence which rows are read, and the caps become harder to reason about.
- *Unbounded `DISTINCT normalized_value`.* Ruled out explicitly — unbounded tenant data in a prompt, and unbounded cost.
- *Caching the profile across turns.* Deferred: correct invalidation on ingest is a separate concern, and the queries are bounded and indexed-friendly.

### Decision 6: Feedback is bounded, sanitized, and corrective

**Choice:** Retry prompts receive an appended block containing, per prior attempt: the SQL (truncated at `MAX_SQL_LENGTH`), the outcome, a sanitized single-line reason, and a fixed corrective instruction naming what to reconsider (entity types, values, operators, joins, filters). Sanitization takes the exception class name plus the first line of its message, cuts everything from SQLAlchemy's `[SQL:` marker onward (which otherwise echoes the full statement and bound parameters), and truncates to a fixed budget.

**Rationale:** Without the previous SQL in the prompt at temperature 0, a retry regenerates the same query and wastes the budget. Without the error, it cannot know *what* to change. The `[SQL:` cut matters concretely: SQLAlchemy appends statement and parameters to `DBAPIError.__str__`, so an unsanitized error would round-trip tenant values through the prompt and the logs for no benefit.

**Alternatives considered:**
- *Pass the raw exception string.* Ruled out for the parameter-echo problem above.
- *Summarize the error with an LLM call.* Ruled out: an extra call on the slow path to compress a string.

### Decision 7: `MAX_SQL_ATTEMPTS` is configuration, and the deadline still wins

**Choice:** `settings.sql_max_attempts: int = 3` in `src/shared/config.py`, alongside the existing `orchestrator_max_invocations` / `retrieval_deadline_seconds`. `SQLGenerator` reads it once at construction, clamped to `>= 1`, and the literal `3` appears nowhere else. A value of `1` restores exactly today's behaviour, which is also the rollback switch. The loop additionally stops early if the existing `ToolContext.deadline` has passed.

**Rationale:** The codebase already expresses every other budget this way. `1` as a config-only kill switch means rollback needs no deploy.

**Alternatives considered:**
- *A module constant only.* Ruled out: the change explicitly asks for configurability where the architecture supports it cleanly, and it does.
- *A separate feature flag plus a cap.* Ruled out as redundant — `sql_max_attempts = 1` is the flag.

## Risks / Trade-offs

- [A retry produces *different* wrong rows rather than none, and the answer model narrates them confidently] → The only empty-triggered retry is the decidable `entity_type` contradiction (Decision 3); a query that already returned rows is never retried at all.
- [Worst-case latency for a failing structured invocation roughly triples, threatening ADR-007's P95 < 10s] → Only failing invocations pay it; the existing 8s `ToolContext.deadline` bounds the whole plan regardless of the attempt cap; `sql_max_attempts = 1` is a config-only rollback.
- [LLM cost rises] → No additional call on success. Attempts 2 and 3 are reached only after a classified failure; per-attempt counts are logged so the real rate is measurable rather than assumed.
- [The entity-profile queries add per-invocation DB work] → Two bounded queries, fetched once per invocation rather than per attempt; the type query is the one already being run today.
- [Raising instead of returning `None` changes an established contract and could surface as a new user-visible error] → `run_tool` already converts every exception to `ToolResult.error`, and `_accumulate` already tolerates a failed structured entry; the user-facing terminal state is the unchanged `FALLBACK_REPLY`. Covered by an explicit regression test.
- [Sample values in the prompt are drawn from polluted data and may teach the model bad literals] → Frequency ranking surfaces the *dominant* spelling, which is the one worth matching; and showing real values is strictly more informative than the current alternative of showing none. Data cleanup remains a separate change.
- [Prompt growth from the profile plus feedback blocks pushes against the generator's token budget] → All three inputs are hard-capped (per-type count, total count, value length, feedback length, SQL truncation); `max_tokens=500` on the completion is unchanged.

## Migration Plan

1. Land config defaults with `sql_max_attempts = 3`; no migration, no schema change, no dependency.
2. Ship the loop, classification, feedback, and entity profile behind that single number. Deploy is a normal rolling deploy — no data backfill, no coordinated release.
3. Monitor the per-attempt log line for: rate of attempt ≥ 2, distribution of outcomes, rate of exhausted-retry failure, and structured-invocation latency.
4. **Rollback:** set `sql_max_attempts = 1`. The loop body executes exactly once, the failure classification collapses to the existing single-pass behaviour, and the only residual differences are the richer prompt grounding and the honest failure propagation. Full code rollback is a revert of a self-contained set of files with no persisted state to unwind.

## Open Questions

- Is `ToolContext.deadline` populated on every path that reaches `sql_search`? `retrieval_execution_node` sets it (`nodes.py:301`), but the eval harness builds its own contexts. If it can be `None`, the loop must not depend on it as its only latency bound — the attempt cap covers this, but the assumption should be confirmed.
- Should the exhausted-retry failure make the whole turn's `sql_error` visible to developers through an existing debug surface, or remain log/trace-only? This design assumes trace-only, since no user-facing debug surface exists today.
- Does the value-existence probe (Decision 3, deferred alternative) belong in a fast follow-up? That decision should be driven by the measured rate of unexplained empties from step 3 of the migration plan, not decided now.
- No in-force ADR needs revisiting. ADR-007 already mandates the validation layer, read-only execution, timeouts, and graceful degradation — this change strengthens compliance with it rather than departing from it.
