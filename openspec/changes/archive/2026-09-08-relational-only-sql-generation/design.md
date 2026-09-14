## Context

Text-to-SQL runs inside the `structured_retrieval` tool, not as a graph node: `retrieval_execution_node` builds a `ToolContext` carrying `sql_search = RAGOrchestrator._sql_source`, `execute_plan` invokes the tool, and the tool calls `SQLGenerator.generate_and_execute`. Everything specific to SQL — prompt, validation, scoping, execution, retry — lives in `src/chat_api/services/sql_generator.py`. Nothing downstream of `generate_and_execute` knows the row shape: `context_assembler.py`, the guardrails, source assembly and the graph all treat results as opaque dicts, and none of them mentions `document_entities`. The blast radius of changing the query model is therefore genuinely small.

`generate_and_execute` today does three things before its attempt loop: it fetches an `EntityProfile` from `document_entities` (a `SELECT DISTINCT entity_type` plus a frequency-ranked `normalized_value` sample), it resolves the tenant's generated tables via `resolve_generated_tables`, and it enters the loop. The resolved generated tables reach `validate_sql` and stop there. `generate_sql` renders the static `WHITELISTED_TABLES` constant and an EAV data-model prompt of roughly 150 lines. So the model is told to query a table it is being steered away from, and cannot name the tables it is actually permitted to read.

The relational surface it should be querying already exists and is already populated. `entity-relational-projection` made `subject` and `e_<slug>` physical tables written inside the extraction worker's per-document transaction. `src/shared/entity_views.py` owns the surface rules: `expected_table_names` (`subject` plus each active `multi` definition's table) doubles as `generated_table_names`, `subject_columns` decides the `subject` layout from active `single` definitions, and `entity_type_literals` folds `base_label_mapping` in so base-model tenants resolve identically to fine-tuned ones. `resolve_generated_tables` already feeds both the execution role's grants and `validate_sql` from one call — the single-source discipline this change must not break.

Three constraints shape the work. First, the surface is per-tenant and mutable at runtime: definitions are added, deactivated, reactivated, and flipped between cardinalities, and nothing may be hard-coded. Second, deactivation and cardinality flips retain tables on disk that must stay off the query surface — a retained table answers every question with zero rows, which is the silent-wrong-answer failure the whole layer exists to avoid. Third, relational tables are populated only for documents extracted since the projection shipped, so a tenant can have full EAV data and an empty `subject`.

## Goals / Non-Goals

**Goals:**

- One canonical query model for SQL generation: the tenant's generated relational surface.
- The actual per-tenant relations, their columns, and their semantic meaning reach the generator.
- Exactly one authoritative mechanism decides which relations the generator may describe, the validator may accept, and the execution role may read.
- Document scoping works on `subject` and on generated child tables, and cannot silently degrade into a tenant-wide query.
- The bounded retry loop keeps its useful behaviour, with defect detection adapted to relational SQL.
- A tenant whose relational surface is unpopulated fails loudly rather than answering "nothing found".

**Non-Goals:**

- Any dual EAV/relational routing strategy for the generator.
- An EAV-to-relational backfill.
- Changes to extraction, `entity_postprocessor.py`, `relational_projection.py`, the EAV persistence architecture, or `document_entities` itself.
- Migrating other `document_entities` readers — `entity_resolver.py`, document detail, and the extraction-side modules are untouched.
- Redesigning the graph, the planner, context assembly, citations, or the HTTP contract.
- Prescribing exact prompt wording beyond the architectural requirements.

## Currently-In-Force ADRs

| ADR | Decision Summary | Constraint on This Design |
|-----|-----------------|--------------------------|
| ADR-001-tenant-data-isolation | Separate PostgreSQL schema per tenant; `SET search_path TO tenant_<id>` scopes every query | The surface must be resolved per schema, from the schema bound out of authenticated request context. No cross-schema resolution may leak one tenant's relations into another's prompt, whitelist, or grants. |
| ADR-007-chatbot-architecture | Full RAG with structured SQL + semantic search + NER; SQL must pass a validation layer and execute read-only with a timeout; every response carries citations | Validation, the read-only transaction, the 10s timeout, and the least-privilege execution role stay exactly as they are. Relational SQL is validated by the same layer, not by a bypass. Results must still carry enough to cite. |
| ADR-008-base-model-as-default | The shared base model is the default; `entity_type` holds CoNLL labels (`PER`, `ORG`, …) rather than tenant entity names until a tenant fine-tunes | Every association between stored entity data and a relation must go through `base_label_mapping` via `entity_type_literals`. Name equality would make every base-model tenant silently empty. |
| ADR-002 (as amended by 008), ADR-003, ADR-004, ADR-005, ADR-006 (as amended by 009/010), ADR-009, ADR-010 | Model strategy, serving topology, governance, agent boundaries, training infrastructure | No constraint on this design. |

## Decisions

### Decision 1: Promote `resolve_generated_tables` into a richer `resolve_query_surface`, keeping the old function as a wrapper

**Choice:** Add `QuerySurface` and `resolve_query_surface(session, schemas) -> dict[schema, QuerySurface]` to `src/shared/entity_views.py`. `QuerySurface` carries `table_names` (unchanged semantics), `subject_columns` (name → SQL type → owning definition), `child_tables` (identifier → owning definition, with the fixed `_CHILD_TABLE_COLUMNS` shape), and the definition metadata behind each. `resolve_generated_tables` becomes `{k: v.table_names for ...}` over the same call. Extend `_QUERY_SURFACE_QUERY` with `value_kind`, `description`, and `examples`.

**Rationale:** The single-source rule is already load-bearing — the module docstring in `sql_execution_role.py` spells out why a granted-but-not-whitelisted table and a whitelisted-but-not-granted table are both invisible failures. Adding a third consumer (the generator) makes it more load-bearing, not less. Deriving the richer object from `expected_table_names` and `subject_columns` rather than reimplementing means the described surface cannot diverge from the maintained one. The `_QUERY_SURFACE_QUERY` extension is not optional: it currently selects no `value_kind`, so `subject_columns()` built from its rows types every column `TEXT`.

**Alternatives considered:**
- A new resolver beside the existing one — rejected: that is precisely the second source of truth the change forbids, and the two would disagree within a release.
- Introspect `information_schema` for the live columns — rejected: it reports what exists, including retained off-surface tables and columns of deactivated definitions, and carries no semantics. The catalog is the authority on what *should* be readable; `pg_tables` already guards what physically exists at grant time.
- Change `resolve_generated_tables`' return type in place — rejected: `build_role_statements` and its tests consume `dict[str, set[str]]`, and churning them adds risk to a security-relevant path for no gain.

### Decision 2: Resolve the surface by schema, not by threading `tenant_id` through the tool boundary

**Choice:** `generate_and_execute` keeps its `(query, session, schema, ...)` signature and resolves the surface from `schema`, exactly as `_fetch_generated_tables` does today via `schema_for_tenant`.

**Rationale:** `ToolContext` has `tenant_id`, but `SqlSearch` — the injected callable that keeps `src/shared` from importing `src.chat_api` — does not pass it. Widening that protocol touches `base.py`, `entity_tools.py`, `rag_orchestrator.py`, and every test that builds a fake `sql_search`, to obtain a value the existing resolver already derives. Schema is also the value ADR-001 makes authoritative and the one already bound once from request context and never reassigned inside the loop.

**Alternatives considered:**
- Add `tenant_id` to `SqlSearch` — rejected: cross-package protocol churn for no capability.
- Derive `tenant_id` from `schema` — rejected: the mapping is documented as one-directional (`demo-tenant` and `demo_tenant` both give `tenant_demo_tenant`).

### Decision 3: Rebuild the grounding block around relations; keep `document_entities` as the value oracle

**Choice:** Replace `EntityProfile` with a surface-keyed grounding object. Structure per relation and per `subject` entity column: SQL identifier, declared type, the definition's display name, description, examples, value kind and unit, and a bounded sample of real values. Samples still come from the existing frequency-ranked query over `document_entities`, then are **re-keyed** from `entity_type` onto the relation or column that entity type projects into, using `build_routing_index` / `entity_type_literals`.

**Rationale:** Identifiers alone are not enough, and the codebase already holds the right material: `entity_definitions.description` and `.examples` are tenant-authored and exposed in the portal's define/edit slide-over, and `value_kind` / `value_unit` say what a typed column actually holds. Real values remain the highest-leverage input — the current prompt's own comment says so, and nothing in the relational move changes it. Re-keying rather than dropping the EAV read is what makes the samples usable: a base-model tenant's samples arrive labelled `PER`, and a prompt listing `PER` next to relations named `subject.name` teaches the wrong association. Routing them through the same index the projection uses guarantees the sample sits under the relation that actually holds it.

**Alternatives considered:**
- `SELECT DISTINCT` per generated relation — rejected: N queries instead of one, and it reports nothing for a tenant whose surface is unpopulated, which is exactly the case the coverage probe needs to distinguish.
- Drop value samples entirely — rejected: it removes the single strongest first-attempt signal and would trade a prompt-size win for a recall loss.
- Reuse the existing EAV profile text verbatim — rejected explicitly by the change's premise; it teaches `entity_type` as a filter vocabulary.

### Decision 4: Resolve the document-scope column map from the surface, and make an unscopeable statement a defect

**Choice:** `_DOCUMENT_SCOPE_COLUMNS` becomes a function producing the static map plus `document_id` for `subject` and every child table on the resolved surface. `apply_document_scope` takes that map. When `document_ids` is supplied and the rewrite touched zero references, the attempt is classified `empty_with_defect` with a scope defect rather than executed as a tenant-wide query.

**Rationale:** The column is uniform — `subject.document_id` is the primary key and `_CHILD_TABLE_COLUMNS` declares `document_id VARCHAR NOT NULL` — so the map is mechanical. The inline-view rewrite already survives aggregation, grouping and `LIMIT`, and needs no change beyond knowing which tables to rewrite. The new invariant closes a real hole: `apply_document_scope` returns the statement untouched when it recognises nothing, and `retrieval_execution_node`'s secondary filter only drops rows that carry a `document_id` column — an aggregate carries none. Today a scoped question against `subject` would be answered tenant-wide, silently, with a plausible number.

**Alternatives considered:**
- Append the scope to the natural-language question — rejected: that was the previous mechanism, and the module docstring records why it was removed.
- Hard-fail an unscopeable statement — rejected as the first response: the retry budget is already funded and a regenerated statement usually can be scoped. Failing after the retries are exhausted is the right shape, and matches how every other defect behaves.

### Decision 5: Replace the defect ladder in place; keep the outcome set and the zero-rows policy

**Choice:** Keep `SQLAttemptOutcome`, `RETRYABLE_OUTCOMES`, the attempt/deadline bounds, and "zero rows with no deterministic defect is a real answer". Replace the detectors: `_entity_type_defect` gives way to surface-based relation and column validation (pre-execution, so it surfaces as `validation_error`); `_wrong_entity_type_defect` becomes a *wrong-relation* probe that finds the value in `document_entities`, maps its `entity_type` through the routing index to a relation or column, and reports that; `_filename_defect` is kept unchanged. Feedback text is rewritten to name relations and columns.

**Rationale:** The loop's structure was never EAV-specific — only its three detectors were. The wrong-relation probe is the direct analogue of the defect the current code calls the most common failure on this data, and the EAV table is the cheapest place to answer "where does this value actually live", since it is indexed and holds every value including those in relations the statement never touched. Keeping the zero-rows policy matters: retrying on row count alone pushes the model to loosen filters until something returns, which the existing design notes call out.

**Alternatives considered:**
- Drop defect detection and rely on execution errors — rejected: an empty result raises nothing, so the most common failure would become unretryable.
- Probe each generated relation for the value instead of using EAV — rejected: N queries per defect check versus one, and it cannot see values in relations that are off-surface or unpopulated.

### Decision 6: Add column validation, permissive on unattributable references

**Choice:** `validate_sql` gains a column check against the resolved surface. A column reference the parser cannot attribute to a specific relation is accepted, not rejected.

**Rationale:** For the first time there is an authoritative column list — `subject`'s layout from `subject_columns`, the fixed child shape, and the static tables' declared sets. Catching a bad column before execution yields far better retry feedback than a Postgres `UndefinedColumn` string, and it is the "wrong column" failure mode this change is asked to handle. Permissive-on-ambiguity is the safety valve: the tokenizer is a table-reference parser, not a full SQL parser, and a gap must degrade into a database error (retryable, already handled) rather than into rejecting a correct query.

**Alternatives considered:**
- Strict rejection on any unresolved reference — rejected: false rejections of correct queries, and the failure is invisible to the user as anything but "source unavailable".
- No column validation, rely on Postgres — rejected: it works, but the error text is poor retry feedback and the change is explicitly asked to detect wrong columns.

### Decision 7: Coverage probe instead of a backfill

**Choice:** Before the attempt loop, determine whether the relational surface holds data for the question's extent (tenant-wide, or the scoped documents). If it does not while `document_entities` does, raise `SQLGenerationFailed` with a coverage reason. No backfill, no per-document fallback to EAV.

**Rationale:** The projection is written only by the extraction worker, so relational data exists only for documents extracted since it shipped. A relational query over an empty `subject` returns zero rows, and the current policy — correctly, for its own assumptions — calls that a legitimate empty answer. Under relational-only that becomes a confident wrong answer for an entire class of tenants. The existing migration path is real and needs no new machinery: `get_already_extracted` is scoped by `model_version`, so promoting a version makes every document eligible, and `run_batch_extraction` reconciles the schema before the document loop. Failing explicitly turns a silent wrong answer into a visible "source unavailable", which the pipeline already renders correctly, and points the operator at re-extraction.

**Alternatives considered:**
- Fall back to EAV SQL when the surface is empty — rejected: it is the dual query model the change forbids, and it would keep the EAV prompt alive forever.
- Backfill EAV into the relational tables — rejected: out of scope by the change's own boundaries, and it would need value-kind parsing and single-value selection outside the transaction that owns them.
- Do nothing and accept empty answers — rejected: it is the exact failure shape (`"looks like no entities found"`) the projection layer's docstrings identify as the worst available.

### Decision 8: Narrow `_fix_document_name_reference` rather than delete it

**Choice:** Keep the deterministic repair, gated as it is today on the statement referencing `document_entities`. It will simply not fire on relational SQL, because `subject.filename` is denormalized and needs no join.

**Rationale:** Its whole reason to exist — the model selecting a bare `document_name` that only a `documents` join could resolve — disappears when the filename is a column on the relation being queried. Deleting it would break the static-table path it still guards for no benefit; leaving it in place costs one regex miss per statement.

**Alternatives considered:**
- Delete it — rejected: `document_entities` stays whitelisted and reachable, so the repair still has a live path.
- Extend it to `subject` — rejected: there is nothing to repair; `subject.filename` resolves on its own.

## Risks / Trade-offs

- [Relational SQL answers worse than EAV SQL on some question classes, and only end-to-end evaluation can show it] → Run the golden-set eval (`src/shared/retrieval/eval`, `structured_query_success_rate` over `simple_structured`, `exact_entity_lookup`, `attribute_filtering`) before and after, and treat a drop as blocking. `settings.sql_max_attempts = 1` remains the config-only rollback for the loop.
- [Tenants whose documents predate the projection lose structured answers they previously got] → Intentional and made explicit by the coverage probe: an unavailable source is a truthful answer where a confident empty one is not. Semantic retrieval still answers those turns. The remedy is documented — promote a model version and re-run batch extraction.
- [Column validation falsely rejects a correct query because the reference parser cannot attribute a column] → Permissive-on-ambiguity by design; unattributable references fall through to the database, whose error is already retryable.
- [The grounding block grows with the number of definitions and crowds the prompt] → The existing per-key and total sample caps still apply, reinterpreted per relation; the prompt's EAV data-model section (~150 lines) is removed, which more than pays for the schema listing.
- [A tenant with many definitions makes the surface resolution query heavier] → It is one query against `public.entity_definitions`, already run once per question today for the whitelist; this change adds columns to it, not calls.
- [`subject` and child tables are physical tables written by extraction, so a partially-run extraction shows partial data] → Unchanged property of the projection: writes are inside the per-document transaction, so a document is present or absent, never half-projected.
- [Three unarchived changes now touch the same capabilities (`chat-api`, `sql-query-recovery`, `entity-view-layer`)] → The delta specs here are written on top of `entity-relational-projection`'s and `bounded-sql-retry-loop`'s versions, restating the full requirement text, so archive order does not lose detail.

## Migration Plan

1. Land the resolver first (`resolve_query_surface`, extended `_QUERY_SURFACE_QUERY`, `resolve_generated_tables` wrapper) with its own tests. No behaviour change: the wrapper returns what the old function returned.
2. Land validation and scoping (surface-derived column check, resolved scope map, unscopeable-statement defect). Still no prompt change, so existing EAV SQL keeps passing.
3. Land the grounding rebuild and the prompt swap together — the two are meaningless apart.
4. Land the defect ladder replacement and the feedback rewrite.
5. Land the coverage probe.
6. Extend `smoke_check_schema` and re-run `scripts/provision_sql_execution_role.py`, so the execution role holds `SELECT` on every generated relation before the generator starts naming them.
7. Run the golden-set eval and compare structured-query success against the pre-change baseline.

**Rollback:** the change is a single deploy of one service. Steps 1–2 are behaviour-preserving and safe to leave in place. If the prompt swap regresses answer quality, revert steps 3–5 as a unit; the resolver, the column check and the scope map stand on their own. `sql_max_attempts = 1` remains available as a config-only narrowing of the loop.

**Ordering note:** step 6 must precede step 3 in any environment where the execution role is enabled (`sql_execution_role_enabled`), or the first relational statement a tenant generates will be refused by the database.

## Open Questions

1. Should `document_entities` be removed from `WHITELISTED_TABLES` in a later change once relational coverage is universal? Keeping it is right now — the grounding and defect probes read it, and the static-table questions still work — but it leaves a query model on the surface that the prompt no longer teaches.
2. Do the sample budgets (`sql_entity_sample_values_per_type`, `sql_entity_sample_max_values`) need new defaults once they bound relations rather than entity types? The counts are similar in practice; confirm against a real tenant catalog before changing defaults.
3. Should the coverage probe distinguish "never extracted" from "extracted before the projection shipped"? Both currently yield the same unavailable-source outcome. A finer signal would make a better operator message but needs a per-document check rather than a per-extent one.
4. No in-force ADR appears to need revisiting. ADR-007 describes structured retrieval as "SQL queries over extracted entities", which the relational surface satisfies as written; if a future reader disagrees that the projected surface is "extracted entities", that is an ADR clarification rather than a change to this design.
