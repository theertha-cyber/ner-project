# Design — Harden chat pipeline correctness

## Context

The chat pipeline is a LangGraph DAG: `guardrail → orchestrator → entity_resolution → retrieval_execution → source_assembly → prompt_assembly → generation`. Routing at both conditional edges is a pure function of state, never a model choice. Two retrieval capabilities exist: `structured_retrieval` (natural language → validated SQL over `document_entities`) and `semantic_retrieval` (hybrid dense + sparse with RRF fusion, then cross-encoder reranking). Planning is single-shot: one LLM call chooses capabilities and arguments, and never sees results.

A read-only forensic investigation traced ten representative questions end to end against the live development tenant (8 processed resumes, 24 chunks, 335 entities across 11 entity types). Every trace produced a defective answer, and in none of them was the generation model the earliest failure. The stages themselves are largely correct; the **contracts between them** lose information.

Three concrete losses drive nearly all observed behaviour:

1. **Resolution narrows to one document.** `resolve_entity` selects the first n-gram that matches any person row, builds its document set from that mention alone, and returns `UNIQUE` when the set has one member. `_rewrite_plan_for_resolution` then overwrites every plan entry with that single `document_id`. `"Compare Hannah and Girish."` yields a prompt containing only Girish.
2. **Errors are written and never read.** `ChatState.sql_error`, `retrieval_error`, `orchestration_degraded`, `orchestration_stop_reason`, and `plan_trace` have zero read sites outside the node that writes them. `_accumulate` sets an error only when *every* invocation of a kind failed, and replaces the specific message with a generic string. `ContextAssembler.assemble()` has no error parameter.
3. **Evidence is dropped after retrieval.** The `Entity data:` block is admitted all-or-nothing against the token budget — a 7,944-token result set was measured disappearing whole while its citation survived in `sources`. `source_assembly` independently caps chunks at 3 while `ContextAssembler` admits 5, so citations and evidence disagree in both directions.

A fourth, security-side loss: `validate_sql` resolves only the first identifier after each `FROM`/`JOIN`, so `SELECT d.filename FROM documents d, public.users u ...` passes. `public` holds `tenants`, `tenant_users`, `widget_api_keys`, `entity_definitions`, and `audit_events`.

Constraints shaping this design: the retrieval deadline is 8 seconds and the invocation cap is 3; every LLM role (guardrail, planner, SQL generation, generation) runs on one `gpt-4o-mini` deployment; the portal and the embeddable widget both consume `ChatResponse`; the widget path calls `execute()` with a service token and no conversation context.

## Goals / Non-Goals

**Goals:**

- Close the cross-tenant table-reference gap in SQL validation, and place a privilege boundary behind it.
- Make retrieval outcome a first-class, propagated value that reaches the answer model, the guardrail, and the response payload.
- Stop multi-subject questions collapsing to one document.
- Spend the already-funded SQL retry budget on the defect class it currently cannot see.
- Give a structured-only plan one bounded semantic recovery when it legitimately finds nothing.
- Ensure evidence admitted into the prompt and evidence cited to the user are the same set.
- Make the eval harness capable of failing.

**Non-Goals:**

- No graph rewrite. Node set is unchanged; one edge pair is reordered (Decision 7) and nothing else in the topology moves.
- No agentic loop. Recovery is one fixed invocation, not an observe/re-plan cycle.
- No NER, training, annotation, chunking, OCR, or normalization work. The investigation found real data defects (3 of 8 documents have no `NAME` entity; `"JavaScript,"` retains a trailing comma; `"2 years of experience,"` has a `NULL` `value_number`). All out of scope here.
- No schema migration, no table added or altered, no data backfill.
- No new runtime dependency.
- `candidate_document_filtering_enabled` is neither enabled nor removed.

## Currently-In-Force ADRs

| ADR | Decision Summary | Constraint on This Design |
|-----|-----------------|--------------------------|
| ADR-001-tenant-data-isolation | Tenant data isolated via separate database schemas | The privilege boundary in Decision 2 must reinforce schema isolation, never bypass or replace it. `schema` stays bound from authenticated request context and is never derived from generated SQL. |
| ADR-003-model-serving-topology | Per-tenant model serving | Unchanged. The reranker keeps calling model-serving over HTTP with the caller's token; no serving-topology change. |
| ADR-004-openspec-governance | Spec-driven development governance | Every behavioural change here lands as a delta spec with scenarios, and verification.md gates archive. |
| ADR-007-chatbot-architecture | Full RAG with SQL validation, citation enforcement, tenant scoping, disclaimer, rate limiting, P95 < 10s | SQL validation, citation enforcement, and tenant scoping are strengthened, not relaxed. The P95 budget constrains Decision 5 (recovery must fit the existing deadline). ADR-007's live-NER source and complexity-limit guardrail were already contradicted by `redesign-retrieval-orchestration`; see Open Questions. |

## Decisions

### Decision 1: Resolve every table reference with a hardened clause parser, no dependency

**Choice:** Replace the two `re.findall(r'\bFROM\s+(\w+)')` / `\bJOIN\s+(\w+)` scans with a routine that extracts the full `FROM` clause of every `SELECT` in the statement, splits its comma-separated table list, strips aliases and `AS`, and resolves each reference. A reference is admitted only when it is a bare identifier present in `WHITELISTED_TABLES`; any schema-qualified name, any function-call source, and any identifier not in the whitelist is rejected. `SET ROLE` and `SET SESSION AUTHORIZATION` join the disallowed-keyword list.

**Rationale:** The current gap is precisely that only the first identifier after each keyword is captured. Extracting the clause and splitting it closes that specific hole with no new package. The generated statement space is narrow — the generator prompt constrains shape heavily and `MAX_SQL_LENGTH` is 2000 — so exhaustive general SQL parsing is not required for the fix to be effective, and the privilege boundary in Decision 2 covers what a regex cannot.

**Alternatives considered:**

- Add `sqlglot` and walk the AST — genuinely complete, but the proposal excludes new runtime dependencies, and a parser large enough to be correct is also large enough to disagree with Postgres on dialect edge cases. Reconsider if Decision 2's role ever has to be relaxed.
- Ban comma joins outright — simpler, but rejects the legitimate `FROM document_entities e, documents d` shape the generator sometimes produces, converting a security fix into a recall regression.
- Rely on the privilege boundary alone — rejected: a validator that admits a statement it should reject is a defect regardless of whether the database then refuses it, and the resulting permission error is a worse diagnostic than a clean rejection.

### Decision 2: Least-privilege role for generated-SQL execution

**Choice:** Introduce a dedicated database role for generated-SQL execution with `SELECT` on the whitelisted tables in tenant schemas and **no** grants on any `public` relation. `execute_sql` applies it per statement via `SET LOCAL ROLE` inside the existing read-only transaction, so it cannot leak across the connection or outlive the statement. The role is chosen by server configuration only; it is never derivable from any tool argument, from the question, or from the generated SQL. This is the sole infrastructure-adjacent item in the change and exists only to bound the security fix.

**Rationale:** Defence in depth for a control whose primary layer is a regex. A future gap degrades into a permission error — recorded as a structured retrieval failure by Decision 3 — instead of a cross-tenant disclosure. `SET LOCAL` scopes to the transaction, so the existing `BEGIN READ ONLY` boundary is also the privilege boundary.

**Alternatives considered:**

- A separate connection pool under the restricted role — cleaner isolation, but doubles pool configuration and complicates the per-invocation session factory the orchestrator already relies on.
- Postgres row-level security — orthogonal; the exposure is whole-relation, and schema separation already provides the tenant boundary ADR-001 mandates.
- No role change — rejected by the choice recorded during proposal review.

### Decision 3: `RetrievalStatus` replaces the two collapsed error booleans

**Choice:** Introduce a `RetrievalStatus` value carrying one entry per plan entry: `capability_name`, `outcome` ∈ {`not_attempted`, `ok`, `empty`, `failed`, `skipped`}, `error` (the specific text, not a generic summary), `result_count`, and the per-attempt diagnostics the SQL loop already produces. Plus a turn-level `planning_degraded` flag and `stop_reason`. `_accumulate` populates it; `ChatState` carries it in place of `sql_error` and `retrieval_error`; `ContextAssembler`, `GuardrailService.enforce_sources`, and `ChatResponse` all read it.

`sql_error` and `retrieval_error` are removed from `ChatState` rather than kept alongside — two error channels is how the current one became unread.

**Rationale:** Every downstream defect in the investigation traces to one of three erasures at this boundary: partial failure erased by the all-or-nothing condition, specific error text erased by the generic string, and the whole signal erased by having no reader. One structured value with named consumers fixes all three. `PlanTraceEntry` already carries most of these fields — this promotes an internal diagnostic into a contract rather than inventing a new concept.

**Alternatives considered:**

- Keep the booleans and add readers — rejected: the booleans cannot express partial failure at all, so the readers would still be wrong.
- Reuse `plan_trace` directly as the contract — rejected: `plan_trace` is a positional list keyed to plan indices, including rejected entries, and its `asdict()` shape is not something the HTTP schema should inherit.
- Raise on any retrieval failure — rejected: a turn where one of two sources failed is still answerable from the other, and failing the turn discards good evidence.

### Decision 4: Multi-document resolution, with a minimum-mention-length gate

**Choice:** `ResolutionResult` gains `resolved_document_ids: list[str]` and a per-mention breakdown. `resolve_entity` evaluates every distinct mention that matched, not only the first in longest-first order, and returns the union. `UNIQUE` becomes "resolved to a non-empty document set". `AMBIGUOUS` retains its current meaning — *one* mention matching several people — and still short-circuits to the clarification reply. `OVER_CAP` fires on the union size. `_rewrite_plan_for_resolution` takes `document_ids: list[str]` and applies the whole set to every affected entry. Mentions of a single character do not contribute to the union.

**Rationale:** The collapse is caused by two independent choices — first-match-wins on `winning`, and a single-`document_id` rewrite signature. Both must change or the defect survives. The length gate addresses the observed hazard that a stored name (`"zanith kumar r"`) contributes a single-letter token to the word-overlap match, which any message containing a standalone `r` would hit; widening scope on that basis is worse than not resolving.

**Alternatives considered:**

- Fall back to `UNRESOLVED` on any multi-subject match — safe and simple, but discards the precision benefit for exactly the comparison questions this change exists to fix.
- Score mentions and pick the strongest — still narrows to one subject; wrong for a question about two.
- Resolve to the union but keep the single-document rewrite for the "one mention" case — rejected: two code paths for one concept is how the current bug is shaped.

### Decision 5: One fixed semantic recovery invocation, gated on remaining budget

**Choice:** After the dispatched entries complete, if the plan contained no `semantic_retrieval` entry and every `structured_retrieval` entry reported `empty` or `failed`, `execute_plan` issues exactly one `semantic_retrieval` call with the turn's original question. It is gated on at least `retrieval_recovery_min_budget_seconds` (default 2.0) remaining before the deadline, and it counts against `orchestrator_max_invocations`. A skip is recorded as `skipped` in `RetrievalStatus`, never as an empty result.

**Rationale:** `"What is Mahalakshmi's email address?"` produced a structurally correct SQL statement that returned zero rows only because the anchor `NAME` entity is missing — while the `EMAIL` row and the chunk text both hold the answer. One unconditional fallback recovers that class without re-planning. The budget gate exists because the planner call already consumes 1.0–3.0 s and each structured attempt 1.7–2.8 s of the 8-second window; recovery must never be the reason a turn misses the P95 target ADR-007 sets.

**Alternatives considered:**

- Feed the empty result back to the planner for a second planning round — this is the "plan + one refine" remedy `redesign-retrieval-orchestration` pre-identified. Deferred: it adds a full planning call to the critical path, and the fixed fallback covers the observed class at a fraction of the cost. Revisit if the query-class eval shows the fixed fallback missing cases.
- Always add a semantic entry to every plan — rejected: doubles embedding and rerank load on every turn, including the many where structured retrieval answers completely.
- Retry the structured query with relaxed filters — explicitly rejected by the existing `SQLAttemptOutcome` design note: retrying on row count alone pushes the model to loosen filters until something comes back.

### Decision 6: Normalise chunk scores to rank-based fusion before cross-invocation merge

**Choice:** `_accumulate` merges chunks from multiple `semantic_retrieval` invocations on a rank-derived score computed per invocation, not on the raw `similarity_score` the invocation happened to produce. The raw score is retained on the result for display, with its basis recorded, so a citation's `relevance_score` no longer silently means "RRF ≈ 0.016" in one turn and "cross-encoder logit" in the next. Single-invocation ordering is unchanged by construction.

**Rationale:** The reranker falls back to unranked RRF candidates on failure, so one plan can produce two invocations whose scores live on incomparable scales — RRF around 0.016 against cross-encoder logits that may be negative. Sorting them against each other is arbitrary. Rank position is the one basis both share.

**Alternatives considered:**

- Min-max normalise per invocation — sensitive to outliers and to invocations returning a single result.
- Re-rank the merged set in one additional cross-encoder call — most accurate, but adds a round trip inside the 8-second budget for a case that only arises on reranker failure.
- Never merge across invocations, keep per-invocation buckets — pushes the ordering problem into the assembler unchanged.

### Decision 7: Assemble the prompt first, then derive citations from what it admitted

**Choice:** Reorder two edges so the path is `retrieval_execution → prompt_assembly → source_assembly → generation`. `ContextAssembler.assemble()` returns the messages **and** the admitted evidence (which chunks, which rows, whether either was truncated). Document-name resolution moves into `prompt_assembly`, which already needs names for its chunk labels; `source_assembly` consumes `document_names` and `admitted_evidence` from state. The node set, the conditional edges, the routing predicates, and `generation_node`'s dependence on `sources` are all unchanged.

**Rationale:** Citations can only be honest about evidence if they are computed from it. Today the two stages independently guess — `[:3]` here, `[:5]` and a budget loop there — and disagree in both directions. Reordering is a two-line edge change that makes the dependency explicit; the alternative is duplicating the entire admission calculation in `source_assembly`, where it would drift.

**Alternatives considered:**

- Duplicate the budget calculation in `source_assembly` — rejected: two implementations of one rule, guaranteed to diverge.
- Merge both nodes into one — larger diff, loses the per-node tracing the `_traced` decorator provides, and removes a boundary the tests target.
- Keep the order and pass the caps through settings so both stages compute the same number — still two computations, and it cannot express "this chunk was skipped because it did not fit".

### Decision 8: Structured evidence truncates by whole rows, after duplicate collapse, with an explicit marker

**Choice:** The `Entity data:` block is built by admitting whole rows until the budget is exhausted, after collapsing exact duplicate rendered rows. The block carries an explicit statement of what was admitted and what the query matched — for example `showing 100 of 142 matched rows`. When either the query was truncated by its row limit or the assembler truncated the block, the system prompt's exhaustiveness instruction is replaced with a partial-listing instruction. Structured rows are admitted before chunks and are guaranteed at least one row.

**Rationale:** Three defects share one fix. The all-or-nothing admission drops the entire block above roughly 5,500 tokens. `DEFAULT_LIMIT = 100` truncates a 142-row result. And the system prompt asserts the block is exhaustive in both cases. Whole-row truncation keeps the JSON parseable; duplicate collapse buys back budget (the `"Who knows AWS?"` trace returned four identical rows); the explicit marker is what stops the model claiming completeness it does not have.

Collapse is keyed on the **full rendered row**, so the same value from two documents survives as two rows — provenance is exactly what makes those rows distinct.

**Alternatives considered:**

- Raise `DEFAULT_LIMIT` — trades one truncation point for a worse collision with the 6,000-token budget, and does not fix the exhaustiveness claim.
- Instruct the generator to emit `DISTINCT` — collapses in the database, before provenance is projected, and is a model instruction rather than a guarantee.
- Summarise oversized results with an LLM call — an extra call on the critical path to compress evidence the model is about to read anyway.

### Decision 9: Split the conflated chunk caps into four named settings

**Choice:** `retrieval_top_k` (per-invocation retrieval), `retrieval_merge_max_chunks` (retained after cross-invocation merge), `context_max_chunks` (admitted into the prompt), and `citation_max_chunks` (cited). `context_max_chunks` stops defaulting to `retrieval_top_k`; `source_assembly`'s literal `[:3]` becomes `citation_max_chunks`. Defaults are chosen so a deployment setting none of them keeps today's per-invocation retrieval depth while removing the accidental couplings: `retrieval_top_k = 5`, `retrieval_merge_max_chunks = 10`, `context_max_chunks = 8`, `citation_max_chunks = 8`.

**Rationale:** One value currently governs three unrelated decisions and a fourth is hardcoded, so a plan with three semantic invocations retrieves up to 15 unique chunks and discards two thirds before the prompt. Naming each cap makes the loss visible and tunable.

**Alternatives considered:**

- One cap for everything — the current state; it is what makes multi-invocation plans lose evidence silently.
- Budget-only admission with no chunk cap — unbounded prompt growth on a wide corpus, and no way to bound rerank cost.

### Decision 10: Structured document scope is applied as a bound parameter, not appended prose

**Choice:** The resolved document set is carried on the structured invocation as a first-class argument and applied as a bound `document_id = ANY(:ids)` predicate wrapping the validated statement, rather than by appending `(restrict results to document_id = '…')` to the natural-language query. The existing post-execution row filter is retained as a belt-and-braces check but is no longer the enforcement mechanism, so it can no longer turn a limit-truncated result into an empty one.

**Rationale:** The current mechanism asks a second LLM to honour an instruction in prose, and the post-filter that backstops it runs *after* `LIMIT 100` — so a tenant-wide query whose first 100 rows exclude the resolved document post-filters to zero. Enforcement belongs in the statement.

**Alternatives considered:**

- Keep the prose hint and only fix the filter ordering — leaves enforcement dependent on model compliance.
- Have the generator emit the predicate itself under instruction — same dependency, one layer down.

### Decision 11: Guardrail differentiates empty from failed

**Choice:** `enforce_sources` takes the turn's `RetrievalStatus`. With no sources and every attempted capability `ok` or `empty`, it returns a "found nothing in your data" reply. With no sources and any capability `failed` or `skipped`, it returns a "a retrieval source failed, this result is incomplete" reply that does not assert absence. The clarification exemption is unchanged — clarifications never reach `generation_node`.

**Rationale:** Six distinct upstream conditions currently collapse into one sentence, which is both the reason failures are invisible in production and the reason users cannot tell a real negative from a broken turn.

**Alternatives considered:**

- Let the model phrase it — the model already gets the status block under Decision 3, but `enforce_sources` discards the reply when sources are empty, so the guardrail must carry the distinction itself.
- Return an HTTP error on retrieval failure — breaks the conversation and discards partial evidence.

### Decision 12: Planning contract changes are prompt-and-verify, not a new planner

**Choice:** The conjunctive and multi-source requirements are met by amending `ORCHESTRATION_SYSTEM_PROMPT` and by asserting on plan **shape** in the query-class eval, not by adding a validation layer that rewrites plans. Plan shape is already recorded in `plan_trace`; the eval reads it.

**Rationale:** Planning is a single LLM call by deliberate design. Adding a deterministic plan-rewriter re-introduces routing logic outside the planner — the mistake `redesign-retrieval-orchestration` explicitly removed. Making the contract explicit and measurable is the proportionate repair; if the eval shows the prompt cannot hold the contract, that is evidence for the deferred refine round, not for a rewriter.

**Alternatives considered:**

- Deterministically merge sibling `structured_retrieval` entries — plausible, but merging two natural-language queries into one is itself a language task.
- Reject conjunction-split plans and fall back — turns a degraded plan into no plan.

## Risks / Trade-offs

- [Hardened table resolution rejects a legitimate statement shape the generator produces today, causing a recall regression] → The validation-error path is already retryable, so a false rejection costs an attempt rather than the turn. The query-class eval and the existing SQL test suite run before and after; any newly-rejected shape must be shown to be non-whitelisted.
- [The restricted role lacks a grant some legitimate query needs, breaking structured retrieval in production] → Grants are derived directly from `WHITELISTED_TABLES`; the migration plan stages the role behind a config toggle so it can be reverted without a redeploy, and a smoke query per tenant schema runs before the toggle flips.
- [Multi-document scoping widens rather than narrows, pulling in unrelated documents when a stray n-gram matches a person's name] → The single-character gate covers the observed hazard; the union is bounded by `entity_resolution_max_candidates`; and the comparison eval cases assert the resolved set, not just the answer.
- [The extra recovery invocation pushes P95 past the ADR-007 10-second target] → Recovery is gated on remaining budget, counts against the invocation cap, and only fires when the plan had no semantic entry at all — the cheapest turns. Latency is measured per query class in the eval report.
- [Reordering `prompt_assembly` before `source_assembly` breaks a test or consumer that assumed the old order] → The node set and both routing predicates are unchanged; `generation_node` still reads `sources` written by `source_assembly`, which still precedes it. Existing topology tests are updated as part of the same task, not after.
- [Removing `sql_error`/`retrieval_error` from `ChatState` breaks a consumer] → The investigation established there are none outside the writing node and the eval runner. The eval runner is updated in the same change.
- [Zero-scoring degraded eval queries makes the gate fail immediately against the stored baseline] → The baseline is regenerated under the new rule as an explicit migration step, and the regenerated baseline records the scoring rule it was produced under.
- [`retrieval_status` is additive but a strict client rejects unknown fields] → The portal and widget both deserialize into permissive models; the additive-field scenario is verified explicitly before merge.
- [Exact row counts for completeness reporting add a second query per structured invocation] → Truncation is detected cheaply by fetching one row beyond the limit; the exact matched total is computed only when truncated, inside the existing read-only transaction and its 10-second timeout, and reported as unknown if that count fails.

## Migration Plan

Ordered so each step is independently revertable and no step depends on a later one.

1. **Security first.** Land the hardened table resolution with its rejection tests. It is behaviour-preserving for every legitimate statement and can ship alone.
2. **Provision the restricted role** and its grants, behind a configuration toggle that selects between the current connection role and the restricted one. Run a per-tenant-schema smoke query under the restricted role before flipping the toggle. Rollback is the toggle.
3. **Introduce `RetrievalStatus`** and its readers in one step — producer, `ChatState` field, assembler rendering, guardrail branch, and response field — because a producer with no reader is exactly the defect being fixed. Remove `sql_error` and `retrieval_error` in the same step.
4. **Land the correctness repairs** that depend on status: multi-document resolution, the wrong-entity-type defect, bounded recovery, structural scope enforcement.
5. **Reorder the assembly edges** and land the assembler changes: truncation, duplicate collapse, completeness marker, admitted-evidence return, and the split caps with their defaults.
6. **Amend the orchestration prompt** for the conjunctive and multi-source contract.
7. **Land the eval work** and **regenerate `baseline.json`** under the new zero-scoring rule, recording the scoring rule and the corpus in its metadata. The regression gate is meaningless until this step completes.

Rollback: steps 1 and 3–6 are code-only and revert by deploy. Step 2 reverts by configuration toggle without touching the role. Step 7 reverts by restoring the prior baseline file.

## Open Questions

1. **ADR-007 supersession.** ADR-007 mandates a three-source RAG pipeline including live NER inference and query-complexity guardrails. `redesign-retrieval-orchestration` already removed both and left the supersession unresolved. This change adds further divergence: the source-citation guardrail now branches on retrieval status. Whether the superseding ADR is recorded by this change or by `redesign-retrieval-orchestration` needs a decision before either archives. This design assumes the latter and does not record a new ADR.
2. **Whether the least-privilege role warrants its own ADR.** It establishes a durable boundary that future changes must respect and it touches ADR-001's territory. Not recorded here because the `adr` artifact is already satisfied and the proposal did not request new ADRs; flagged so a reviewer can decide.
3. **Recovery budget threshold.** `retrieval_recovery_min_budget_seconds = 2.0` is inferred from observed latencies (planner 1.0–3.0 s, structured attempt 1.7–2.8 s), not measured against a P95 distribution. The eval latency report should confirm or move it.
4. **`candidate_document_filtering_enabled`.** Still `False`, still unobserved. Reading the code, it pins semantic scope to whatever documents structured retrieval returned — including wrong ones — which would amplify Decisions 4 and 10 rather than complement them. Whether to fix or delete it is deferred to a separate change.
5. **Whether the deferred refine round is needed.** Decision 12 bets that an amended prompt can hold the conjunctive contract. If the query-class eval shows it cannot, the pre-identified "plan + one refine" remedy becomes the next change — explicitly not this one.
