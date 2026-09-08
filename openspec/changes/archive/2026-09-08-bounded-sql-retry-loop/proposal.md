## Why

Structured retrieval gets exactly one attempt per invocation. `SQLGenerator.generate_and_execute` (`src/chat_api/services/sql_generator.py:293`) makes one LLM call, validates once, executes once, and wraps the whole thing in a bare `except Exception: return None`. Every distinct outcome — a whitelist rejection, a Postgres `UndefinedColumn`, a 10-second timeout, and a query that ran perfectly and matched nothing — collapses into the same value. `StructuredRetrievalTool` then maps `None` to `[]` with `error=None` (`src/shared/retrieval/tools/entity_tools.py:31`), so a failed query is indistinguishable from a legitimately empty one for the rest of the pipeline: `sql_error` stays `None`, `_accumulate` reports no failure, and the answer model is told "No relevant data found."

The generator also has almost nothing to aim at. Its only tenant grounding is a bare list of `entity_type` names from `_fetch_known_entity_types` (`sql_generator.py:279`) — it never sees how a concept is actually spelled in this tenant's rows, so it guesses literals against a dataset we already know is polluted (punctuation, fragmentation, NULL `normalized_value`). One guess, no second look.

## What Changes

- **Bounded retry inside `SQLGenerator.generate_and_execute`.** Generate → validate → execute becomes an attempt loop capped by `settings.sql_max_attempts` (default 3), with attempt 1 unchanged in cost and shape. A successful attempt returns immediately — no extra LLM call is ever made on the happy path.
- **Explicit outcome classification** replacing the catch-all `except`. Each attempt yields one of: `success`, `validation_error`, `execution_error`, `generation_error`, or `empty_unexplained` / `empty_with_defect`. Only the failure classes are retried.
- **Conservative empty-result policy.** A zero-row result is retried *only* when a deterministic defect explains it — today, exactly one signal: the generated SQL compares `entity_type` against a literal that is not among the tenant's actual entity types. An unexplained empty result is treated as a real answer and is **not** retried. Rationale is recorded in design.md; the architecture cannot currently distinguish "no matching records" from "bad query" without either an extra LLM judgement or unbounded data probing, and forcing a looser query risks returning confidently wrong rows.
- **Attempt feedback into the generator prompt.** Retries receive a bounded "previous attempts" block: the prior SQL, its outcome, a sanitized error line (SQLAlchemy statement/parameter echo stripped), and a corrective instruction naming what to reconsider. Never surfaced to end users.
- **Bounded tenant entity profile in the prompt.** `_fetch_known_entity_types` is extended into an entity *profile*: the complete type list (as today) plus the top-N most frequent `normalized_value` samples per type, capped per type and in total, and value-length-truncated. Two bounded queries, run under the same server-selected `search_path`.
- **Failure is propagated, not swallowed.** When every attempt fails, `generate_and_execute` raises instead of returning `None`. `run_tool` converts that into `ToolResult.error`, which flows through the existing `_accumulate` into `ChatState["sql_error"]`, so a failed SQL path is no longer laundered into a successful empty one. The user-facing outcome remains the existing `FALLBACK_REPLY` via `enforce_sources` — no new user-visible surface, no fabricated answer.
- **Per-attempt observability.** Each attempt logs a structured line (attempt index, cap, outcome, row count, sanitized error, SQL) and is appended to a caller-supplied `attempt_sink`, mirroring the existing `degraded_sink` pattern in `RerankingRetriever`. The sink is carried into the existing `plan_trace` in `ChatState` — internal state only, never in the HTTP response.
- **Security model unchanged.** The loop is inside the function that already owns `session` and `schema`; every attempt re-enters the same `validate_sql` and `execute_sql`. `schema` is bound once from `ToolContext` (authenticated request state) before the loop and is never re-read from LLM output.
- **No graph topology change.** The retry lives below the LangGraph node boundary, so `build_chat_graph` stays an acyclic DAG with non-model-decided routing.
- No migration. No new dependency. No request/response schema change. No change to answer generation, citations, reranking, or vector retrieval.

## Capabilities

### New Capabilities

- `sql-query-recovery`: the bounded generate/validate/execute/inspect loop — attempt cap and configuration, outcome classification, the conservative empty-result policy, feedback construction and error sanitization, the bounded tenant entity profile, per-attempt trace and logging, failure propagation to the tool boundary, and the tenant-isolation invariants that hold across retries.

### Modified Capabilities

- `chat-api`: the *SQL query generation and validation* requirement currently describes a single generate→validate→execute pass whose failure mode is "skip the SQL source for this turn". It gains the bounded retry, the requirement that failures be distinguishable from empty results at the tool boundary, and the requirement that generation context include bounded tenant-specific entity values. Validation, whitelist, read-only execution, and timeout semantics are unchanged.

## Impact

**Code**
- `src/chat_api/services/sql_generator.py` — the attempt loop, outcome classification, feedback rendering, error sanitization, entity-type-literal defect check, and the extended entity profile. Bulk of the change.
- `src/shared/config.py` — `sql_max_attempts`, `sql_entity_sample_values_per_type`, `sql_entity_sample_max_values`.
- `src/shared/retrieval/tools/base.py` — `SqlSearch` gains an optional attempt-sink parameter; `PlanTraceEntry`-bound diagnostics field for the trace.
- `src/shared/retrieval/tools/entity_tools.py` — passes the sink, attaches diagnostics to `ToolResult`, and no longer masks a raised SQL failure as an empty result.
- `src/chat_api/services/rag_orchestrator.py` — `_sql_source` forwards the sink.
- `src/shared/retrieval/orchestrator.py` — carries per-entry diagnostics into `PlanTraceEntry` (additive).

**Untouched by design**: `graph/builder.py` topology, `graph/nodes.py` node set, `ContextAssembler`, `GuardrailService`, citation enrichment, retriever/reranker, all HTTP schemas.

**Cost/latency**: unchanged on success. A fully failing structured invocation costs at most `sql_max_attempts` generation calls and executions, and is additionally bounded by the existing `retrieval_deadline_seconds` (8.0s) already carried on `ToolContext.deadline`.

**Tests**: new `tests/test_chat_api_sql_retry.py`; existing `tests/test_chat_api_sql.py`, `test_chat_api_structured_value_sql.py`, `test_sql_generator_document_name_fix.py`, `test_retrieval_tools.py`, `test_retrieval_orchestrator.py`, `test_chat_api_rag.py` must stay green.

## Open Questions

- **Timeout retry.** A 10s `asyncio.timeout` failure is classified retryable, but the existing 8s `ToolContext.deadline` will normally have expired by then, so in practice a timeout terminates the loop. Assumption: that is the desired behaviour and no special-casing is needed. Needs confirmation that `deadline` is reliably populated on every structured invocation path.
- **Value-existence probing.** A stronger empty-result signal — probing whether an equality literal exists at all for its entity type — is deliberately deferred; it needs literal extraction from generated SQL and one extra bounded query per attempt. Assumption: the entity-type signal alone is enough to make retry worthwhile without over-triggering.
- **Sample selection.** Top-N by frequency is assumed to be the most useful representative sample given the known data pollution. Frequency ranking may over-represent extraction noise; an alternative (most recent, or longest-distinct) is not evaluated here.
- **Sink plumbing depth.** Carrying the attempt trace all the way into `ChatState["plan_trace"]` touches four files for observability alone. If that proves noisy in review, logs alone satisfy the observability requirement and the sink can stop at `ToolResult`.
