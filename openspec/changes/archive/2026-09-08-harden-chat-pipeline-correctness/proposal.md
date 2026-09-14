# Harden chat pipeline correctness

## Why

A forensic read-only investigation of the chat/RAG pipeline traced ten representative queries end to end against the live development tenant. **All ten produced a defective answer, and in none of them was the generation model the earliest failure.** In every bad trace the evidence was already wrong, missing, or truncated before the answer model saw it.

The investigation attributed the earliest divergence as follows: orchestration/query planning 2, SQL generation 3, entity-resolution architecture 2, model/data quality amplified by a missing recovery path 2, context assembly 1. Semantic retrieval recall was never the earliest failure — when semantic retrieval ran, the correct chunk was retrieved at rank 1 every time.

Three defects are severe enough to make whole query classes unanswerable today:

- **Multi-subject collapse.** `"Compare Hannah and Girish."` resolves to `unique(Girish)` and rewrites *both* capability arguments to Girish's `document_id`. Hannah's document — 79 entities, 3 chunks — is never retrieved. The final prompt contains zero Hannah evidence, and the system prompt then instructs the model to state that no evidence exists. Deterministic. Which subject survives is decided by n-gram length ordering, not by the user.
- **Every error channel is a dead end.** `sql_error`, `retrieval_error`, `orchestration_degraded`, `orchestration_stop_reason`, and `plan_trace` are written into `ChatState` and read by nothing. `ContextAssembler.assemble()` does not accept an error parameter. A failed SQL query and a legitimately empty one produce byte-identical prompts, and `enforce_sources` then collapses six distinct upstream conditions into one sentence.
- **A whitelist bypass reaching cross-tenant tables.** `validate_sql` captures only the first identifier after `FROM`, so `SELECT d.filename FROM documents d, public.users u ...` passes validation. `public` holds `tenants`, `tenant_users`, `widget_api_keys`, `entity_definitions`, and `audit_events`.

The architecture is sound. Its correctness boundaries are not. This change repairs the contracts *between* existing stages without redesigning any of them.

## What Changes

Five focused, dependent repair groups. Each depends on the one before it for the state and contracts it needs.

### A. Security (blocking, lands first)

- `validate_sql` SHALL resolve **every** table reference — comma-joined lists, schema-qualified names, aliases, `CROSS JOIN`, and subquery `FROM` clauses — against the whitelist, not just the first identifier after each `FROM`/`JOIN` keyword. **BREAKING** for any generated SQL that relied on the gap (none is legitimate).
- Generated SQL SHALL execute under a dedicated least-privilege database role with no grants on `public.*`, so a future parser gap cannot become a cross-tenant disclosure. Defence in depth behind the parser fix, not a replacement for it.

### B. Error and status contracts

- `ToolResult` outcomes SHALL be preserved **per capability invocation** as a structured retrieval status, replacing the two collapsed booleans that only fire when *every* invocation of a kind fails. Downstream stages SHALL be able to distinguish `not_attempted`, `ok`, `empty`, and `failed`, and the underlying error text SHALL survive the accumulation boundary.
- `ContextAssembler` SHALL accept that status and render a `Retrieval status:` block, so the answer model can say "the database query failed" instead of "no data exists".
- `ChatResponse` SHALL gain an additive `retrieval_status` field. Existing clients that ignore it are unaffected.
- The empty-sources guardrail SHALL distinguish "retrieval succeeded and found nothing" from "retrieval failed", and reply accordingly, instead of returning one `FALLBACK_REPLY` for both.

### C. Correctness and recovery

- Entity resolution SHALL resolve **all** distinct mentions that match, scoping the plan to the union of their documents (`document_ids: [a, b, …]`) rather than the first n-gram to match. Above `entity_resolution_max_candidates`, the existing narrowing reply still applies. **BREAKING** change to `_rewrite_plan_for_resolution`'s single-document signature.
- The SQL recovery loop SHALL detect a **new defect class**: a zero-row result whose queried literal exists in the tenant's data under a *different* `entity_type`. Today `_entity_type_defect` only flags a type that does not exist at all, so `entity_type = 'PROGRAMMING_LANGUAGE' AND normalized_value = 'aws'` returns zero rows, is classified `SUCCESS`, and leaves two retry attempts unspent — while the prompt had already shown the model `aws` under `TOOL_FRAMEWORK`.
- When a plan contains no semantic entry and structured retrieval returns zero rows, the system SHALL perform **one** bounded semantic recovery call on the original question, within the existing retrieval deadline. Not a new planning round and not an agentic loop — a single fixed fallback invocation.
- Document scope for structured retrieval SHALL be enforced structurally rather than as an appended natural-language sentence, and the resolved-document filter SHALL be applied before the row limit truncates the result set.

### D. Retrieval and context assembly

- The `Entity data:` block SHALL degrade by truncation with an explicit marker rather than being dropped whole. Measured today: a 7,944-token result set silently disappears while its citation survives in `sources`.
- Citations SHALL be derived from the evidence **actually admitted** into the prompt. Today `source_assembly` keeps three chunks and `json.dumps(sql_results[:5])`, while prompt assembly independently admits five chunks and every row — so citations both under-report and outlive their evidence.
- The four independent chunk caps (`retrieval_top_k` as retrieval cap, merge cap, prompt cap via `context_max_chunks=None`, and `source_assembly`'s hardcoded `[:3]`) SHALL be decoupled into named settings.
- Structured retrieval SHALL report total-matched versus returned row counts; the assembler SHALL render truncation explicitly; and the system prompt SHALL stop asserting exhaustiveness when the result was truncated. Exact duplicate values SHALL be collapsed before rendering so the row budget carries more distinct information.
- Chunk `similarity_score` SHALL carry consistent semantics across capability invocations, so merged results from a reranked call and an RRF-fallback call are not sorted against each other on incomparable scales.

### E. Orchestration and evaluation

- The orchestration prompt contract SHALL require that a conjunctive question be expressed as **one** structured invocation whose conditions compose, rather than split across independent invocations whose intersection nothing computes.
- The orchestration prompt contract SHALL require a semantic invocation alongside a structured one for enumeration and identity questions, closing the single-source pattern observed in 8 of 10 traces.
- The eval runner SHALL score degraded and failed queries as **zero** instead of marking them `skipped` and excluding them from the aggregate mean — the current behaviour makes failures raise the reported score.
- The eval suite SHALL add an answer-level correctness harness and a query-class harness covering the eight investigated query categories, and SHALL run against the tenant corpus rather than only the synthetic fictional shipping fixture whose thirty template queries cannot fail.

### Explicitly not changing

NER model quality, `NAME` entity recall, value normalization punctuation, chunking or OCR layout handling, database migrations, model training, and the graph topology itself. The retired agentic loop is **not** revived.

## Capabilities

### New Capabilities

- `sql-execution-privileges`: least-privilege database role for generated-SQL execution, and the requirement that generated SQL never executes with grants on cross-tenant relations.

### Modified Capabilities

- `chat-api`: SQL validation must resolve every table reference including comma-joined and schema-qualified ones; `ChatResponse` gains additive `retrieval_status`; the source-citation guardrail differentiates retrieval failure from a legitimate empty result.
- `retrieval-orchestration`: per-invocation retrieval status replaces collapsed error booleans; bounded structured→semantic recovery; conjunctive and multi-source planning contract; consistent cross-invocation score semantics; structural document-scope enforcement.
- `entity-resolution`: multi-subject resolution scoping the plan to the union of matched documents instead of the first matching mention.
- `sql-query-recovery`: new `EMPTY_WITH_DEFECT` sub-class for a literal that exists under a different entity type; total-matched row reporting.
- `context-assembly`: evidence-preserving truncation instead of all-or-nothing admission; citations derived from admitted evidence; decoupled chunk caps; truncation-aware exhaustiveness contract; duplicate-value collapse; retrieval-status rendering.
- `retrieval-eval`: degraded and failed queries score zero; answer-level and query-class harnesses; tenant-corpus evaluation.

Note on capability naming: `retrieval-orchestration`, `entity-resolution`, `sql-query-recovery`, `context-assembly`, and `retrieval-eval` currently exist only as delta specs inside unarchived changes (`redesign-retrieval-orchestration`, `entity-resolution-disambiguation`, `bounded-sql-retry-loop`, `context-assembly-pipeline`, `retrieval-tools-and-eval`). These deltas deliberately reuse those exact names so they merge coherently once those changes archive. Only `chat-api` exists in `openspec/specs/` today.

## Impact

**Code**

- `src/chat_api/services/sql_generator.py` — `validate_sql` table resolution, new defect class, total-matched reporting
- `src/chat_api/services/entity_resolver.py` — multi-mention resolution result shape
- `src/chat_api/graph/nodes.py` — `_rewrite_plan_for_resolution` multi-document signature, retrieval-status propagation, source assembly from admitted evidence
- `src/chat_api/graph/state.py` — `ChatState` status fields replacing `sql_error` / `retrieval_error`
- `src/chat_api/services/context_assembler.py` — truncation, status rendering, duplicate collapse, admitted-evidence return
- `src/chat_api/services/guardrails.py` — differentiated empty-sources replies
- `src/chat_api/api/v1/schemas.py`, `src/chat_api/api/v1/chat.py` — additive `retrieval_status`
- `src/shared/retrieval/orchestrator.py` — per-invocation status, bounded semantic recovery, score normalization, planning prompt
- `src/shared/retrieval/tools/entity_tools.py` — status and completeness surfacing
- `src/shared/retrieval/eval/runner.py`, `metrics.py`, `gate.py` — zero-scoring, new harnesses
- `src/shared/config.py` — decoupled chunk-cap settings, recovery toggle

**APIs**

- `ChatResponse.retrieval_status` — additive, optional. Portal and widget renderers may ignore it; no existing field changes shape.

**Database**

- One least-privilege role for generated-SQL execution and its grants. No schema change, no data migration, no table added or altered. This is the single infrastructure-adjacent item in the change and is scoped strictly to the security fix.

**Dependencies**

- None added. The table-reference fix is implemented without a SQL parser dependency.

**Downstream**

- Answer-quality behaviour changes for comparison, conjunctive, enumeration, and failed-retrieval turns. Existing eval baselines will move; `baseline.json` must be regenerated as part of this change because zero-scoring degraded queries legitimately lowers the aggregate.

## Open Questions

1. **Scope-widening risk from multi-subject resolution.** Scoping to the union of matched documents means a stray n-gram that happens to match a person's name widens the scope rather than narrowing it wrongly. The investigation found `"zanith kumar r"` produces a single-letter token `r` that any message containing a standalone `r` would match. Should a minimum mention length or a word-boundary confidence rule gate which mentions contribute to the union? Assumed for now: mentions of one character do not contribute.
2. **Recovery call budget.** The bounded structured→semantic recovery adds one embedding call plus one rerank round trip inside the existing 8-second `retrieval_deadline_seconds`. Observed structured latency is 1.7–2.8 s per attempt and planner latency 1.0–3.0 s. Whether the deadline needs raising, or whether recovery should be skipped when remaining budget is below a threshold, is unresolved. Assumed for now: skip recovery when the remaining budget is under 2 seconds, and record that as a status rather than a silent omission.
3. **Duplicate-value collapse placement.** Collapsing exact duplicates could occur in SQL generation (a `DISTINCT` instruction), in the tool layer, or in the assembler. Collapsing too early loses per-document provenance — the `"Who knows AWS?"` trace returned four identical Hannah rows that legitimately represent four occurrences. Assumed for now: collapse in the assembler, keyed on the full rendered row, so provenance-bearing duplicates across documents survive.
4. **`candidate_document_filtering_enabled` remains `False`.** The investigation could not observe its behaviour and flagged it as a suspected amplifier: it pins semantic scope to whatever documents structured retrieval returned, including wrong ones. This change neither enables nor removes it. Whether it should be deleted or fixed is deferred.
5. **ADR-007 supersession.** ADR-007 mandates a three-source RAG pipeline including live NER and query-complexity guardrails. `redesign-retrieval-orchestration` already contradicts it on both points and flagged the supersession as unresolved. This change adds further divergence in the guardrail contract. Whether the superseding ADR is recorded here or in that change needs a decision.
