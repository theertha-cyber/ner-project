## Why

`entity-relational-projection` shipped a populated physical query surface per tenant — `subject` (one row per extracted document, one typed column per active `single` definition, `filename` denormalized) plus one `e_<slug>` child table per active `multi` definition — but the Text-to-SQL path never learned it exists. `generate_and_execute` resolves the tenant's generated tables and passes them to `validate_sql` only; `generate_sql` is still handed the static EAV whitelist and a ~150-line prompt that teaches the model to self-join `document_entities` on `entity_type`. The LLM therefore cannot name a relation it is permitted to read, and every question is answered by reconstructing a subject out of EAV rows.

That costs correctness, not just tokens. The EAV model requires the model to guess how a concept is spelled and which of a fragmented label vocabulary holds it, which is why two of the three retry defect classes exist at all. And the document-scope rewriter's table map (`_DOCUMENT_SCOPE_COLUMNS`) knows only the five static tables: the moment the model does target `subject`, a document-scoped question silently becomes a tenant-wide one.

## What Changes

- **BREAKING (query model)** — The SQL generator's canonical query model becomes the generated relational surface. The prompt's EAV data model, the `entity_type` filtering vocabulary, the one-fact-per-row reasoning, and the "join `document_entities` a second time for the subject's name" directive are removed. No dual EAV/relational routing is introduced.

- **One authoritative query-surface resolver.** `resolve_generated_tables` is promoted to `resolve_query_surface(session, schemas) -> dict[schema, QuerySurface]` in `src/shared/entity_views.py`, built from the existing `expected_table_names` / `subject_columns` / `entity_type_literals` machinery. It carries, per tenant: `subject`'s column layout with declared types, each active child table with the fixed `_CHILD_TABLE_COLUMNS` shape, and the definition metadata behind each (`name`, `description`, `examples`, `value_kind`, `value_unit`). `resolve_generated_tables` survives as a thin `{k: v.table_names}` wrapper so `build_role_statements` and `validate_sql` keep resolving from exactly one call. **No second whitelist is introduced.** `_QUERY_SURFACE_QUERY` gains `value_kind`, `description`, and `examples` — it selects none of them today, so `subject_columns()` derived from it currently reports every column as `TEXT`.

- **Generated schema reaches the model.** `generate_sql` receives the tenant's `QuerySurface` and renders it as the available tables and columns. Tenant-specific by construction, correct for base-model tenants (`base_label_mapping` is already folded in by `entity_type_literals`), and automatically excludes inactive definitions and child tables retained from a `multi` era — because it delegates to the same resolver that decides grants.

- **Semantic grounding is rebuilt, not reused.** The EAV entity-profile block is replaced by per-relation/per-column semantics drawn from `entity_definitions` (`description`, `examples`, `value_kind`, `value_unit` — all already authored in the portal's define/edit slide-over). Real value samples continue to come from `document_entities`, frequency-ranked as today, but are **re-keyed from `entity_type` onto the relation or column that entity type routes to**, via `build_routing_index` / `entity_type_literals`. EAV stays a value and diagnostic oracle; it is never a query target.

- **Document scoping covers the relational surface.** `_DOCUMENT_SCOPE_COLUMNS` becomes a resolved map: the static tables as today, plus `document_id` for `subject` and for every child table on the surface (uniform — `subject.document_id` is the primary key and every child declares `document_id NOT NULL`). `apply_document_scope` takes the resolved map. **New invariant:** when a document scope is supplied and no table reference was rewritten, the attempt is a defect rather than a success — today that path silently widens to the whole tenant.

- **Retry/correction adapted, not removed.** The bounded loop, its budget, its deadline, its outcome set, and the "zero rows with no deterministic defect is a real answer" policy are unchanged. The three EAV defect detectors are replaced: unknown-`entity_type` becomes unknown relation/column against the resolved surface; wrong-`entity_type` becomes "this value lives in a different relation/column", resolved through the EAV oracle and reported in relational terms; the filename defect survives unmodified (its regex is already alias-agnostic, so `subject.filename` is covered). Retry feedback text is rewritten to speak relations and columns.

- **Column-level validation.** `validate_sql` gains a column check against the resolved surface. This is net-new — today `WHITELISTED_TABLES`' column sets are prompt text only and no code validates a column anywhere.

- **Projection-coverage safety.** No EAV→relational backfill. The existing migration path is re-extraction: `get_already_extracted` is scoped by `model_version`, so promoting a model version makes every document eligible and `run_batch_extraction` reconciles then re-projects. Until that happens a tenant can have a full `document_entities` and an empty `subject`, and a relational query over it returns zero rows — which the current policy classifies as a legitimate empty answer. One probe per question makes this explicit: relational surface empty (or, under document scope, no `subject` row for the scoped documents) while `document_entities` holds data means the structured source is reported unavailable, never as "nothing found".

- **Operational consistency.** `smoke_check_schema` extends from the static whitelist to the resolved surface, so a missing grant on a generated table surfaces during provisioning rather than as a user-visible retrieval failure.

- **Not changed:** `entity_postprocessor.py`, `entity_normalizer.py`, `relational_projection.py`, `worker.py`, the EAV persistence architecture, `document_entities` itself (it stays whitelisted and granted so the static-table questions and the grounding probes keep working), `entity_resolver.py`, the document-detail readers, `context_assembler.py`, the guardrails, and the LangGraph topology. No migration.

## Capabilities

### New Capabilities

- `relational-sql-generation`: The generated relational surface as the canonical Text-to-SQL query model — per-tenant surface resolution with columns and semantics, prompt grounding, single-valued facts on `subject` versus multi-valued child tables, base-model mapping, exclusion of inactive and off-surface relations, document scoping over generated relations, relational defect detection and correction, and the projection-coverage failure contract.

### Modified Capabilities

- `chat-api`: The "SQL query generation and validation" requirement's query model becomes the generated relational surface rather than `document_entities`, and validation gains a column check resolved from the same surface as the table whitelist and the execution-role grants.
- `sql-query-recovery`: "Bounded tenant entity profile in the generation context" is replaced by relational surface grounding, and "Attempt outcome classification" / "Previous-attempt feedback is supplied to the generator" stop depending on `entity_type` SQL patterns. The loop bounds, the zero-rows policy, the tenant-isolation invariants, and the observability requirement are unchanged. This capability's spec currently lives in the unarchived `bounded-sql-retry-loop` change.
- `entity-view-layer`: The query-surface resolver becomes the one authoritative description of what the SQL generator may read — table names as today, plus column layout and definition semantics — and provisioning's smoke check covers the generated relations. This capability's spec currently lives in the unarchived `entity-relational-projection` change.

## Impact

**Code — modify**

- `src/chat_api/services/sql_generator.py` — prompt data model and grounding block; `generate_sql` signature; `EntityProfile` replaced by a surface-aware grounding value object; `_DOCUMENT_SCOPE_COLUMNS` becomes a resolved map; `apply_document_scope` signature and the unscoped-statement invariant; `validate_sql` column check; the three defect detectors and `_render_attempt_feedback`; `_fix_document_name_reference` narrowed; the coverage probe in `generate_and_execute`.
- `src/shared/entity_views.py` — `resolve_query_surface` and `QuerySurface`; `_QUERY_SURFACE_QUERY` gains `value_kind`, `description`, `examples`; `resolve_generated_tables` kept as a wrapper.
- `src/chat_api/services/sql_execution_role.py` — consume the wrapper; extend `smoke_check_schema` to the generated surface.
- `src/shared/retrieval/tools/entity_tools.py` — the planner-facing tool description, which currently describes an EAV store.
- `scripts/provision_sql_execution_role.py` — follow any `smoke_check_schema` signature change.

**Tests — modify**

`tests/test_chat_api_sql.py` (`TestSQLPrompt` asserts on EAV prompt text), `tests/test_sql_generator_candidate_name.py` (the self-join name directive is replaced), `tests/test_sql_generator_document_name_fix.py` (the fix narrows), `tests/test_chat_api_sql_retry.py` (`TestWrongEntityTypeDefect`, `TestEntityProfile`), `tests/test_chat_api_structured_scope.py`, `tests/test_sql_table_whitelist.py`, `tests/test_sql_execution_privileges.py`.

**Behavioural**

Answers for tenants whose documents have been re-extracted under the current model version change shape (relational rows rather than EAV rows) but not meaning. Tenants whose relational tables are not yet populated move from a silent empty answer to an explicit "structured source unavailable" — a deliberate correctness trade.

**Not affected:** extraction, projection, EAV persistence, entity resolution, document detail, semantic retrieval, citations, the graph topology, and the HTTP contract.

## Open Questions

1. **Column validation strictness.** Rejecting an unknown column pre-execution is cheaper and produces better retry feedback than a Postgres `UndefinedColumn`, but it is new behaviour and a parser gap becomes a false rejection. Assumption for this change: validate columns, and treat a column reference the parser cannot attribute to a specific table as acceptable rather than rejected.
2. **`document_entities` remaining on the whitelist.** It stays granted and validated so existing static-table questions and the grounding probes keep working, while the prompt stops teaching it. A model could still name it unprompted. Assumption: acceptable — it returns correct data, just verbosely.
3. **Sample-budget split.** `sql_entity_sample_values_per_type` / `sql_entity_sample_max_values` are per-`entity_type` budgets. Re-keying onto relations changes what those numbers bound. Assumption: keep the settings and their defaults, reinterpret them per relation/column.
4. **Coverage-probe cost.** One `EXISTS`-shaped probe per question, inside the existing session. Assumed negligible; to be confirmed against the retrieval deadline budget.
5. **Answer-quality regression risk.** Only the golden-set eval (`src/shared/retrieval/eval`) can settle whether relational SQL beats EAV SQL end to end. Tracked as the primary risk in verification.
