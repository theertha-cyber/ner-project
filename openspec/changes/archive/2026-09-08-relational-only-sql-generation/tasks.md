## 1. Query-surface resolver (behaviour-preserving)

- [x] 1.1 Add `QuerySurface` to `src/shared/entity_views.py`: `table_names: set[str]`, `subject_columns: list[SubjectColumnSpec]` (column name, SQL type, owning `EntityDefinitionSpec`), `child_tables: dict[str, EntityDefinitionSpec]`, derived from `expected_table_names()` and `subject_columns()` — never from a restated list.
- [x] 1.2 Extend `EntityDefinitionSpec` with `description: str | None` and `examples: list | None`, defaulting to `None` so every existing construction site (migration `037`, the sync loader, the projection tests) still compiles.
- [x] 1.3 Extend `_QUERY_SURFACE_QUERY` with `value_kind`, `description`, `examples`, and extend `_spec_from_row` to read them. Without `value_kind` every `subject` column resolves as `TEXT`.
- [x] 1.4 Add `resolve_query_surface(session, schemas) -> dict[str, QuerySurface]`, applying the existing exclusions (inactive, no `sql_identifier`, active `single`'s retained child table) via `generated_table_names`.
- [x] 1.5 Reduce `resolve_generated_tables` to `{k: v.table_names for k, v in resolve_query_surface(...).items()}` and confirm `build_role_statements` and `sql_execution_role.provision_role` are unchanged.
- [x] 1.6 Tests in `tests/test_entity_views_generator.py`: resolver reports columns with declared types (verification rows 66, 68); carries description/examples (row 67); excludes inactive, identifier-less, and `single`-retained tables while listing the `single` column (row 69); two schemas in one call stay isolated and each carries at least `subject` (row 70); a `base_label_mapping`-only definition resolves under its own name (row 71).
- [x] 1.7 Confirm `tests/test_sql_execution_privileges.py::TestGeneratedTableSurface` still passes unchanged — the wrapper must be a pure refactor.

## 2. Validation: relations and columns from the surface

- [x] 2.1 Change `validate_sql(sql, generated_tables)` to `validate_sql(sql, surface)` and derive the accepted relation set from `surface.table_names` ∪ `WHITELISTED_TABLES`, preserving every existing rule (SELECT-only, keyword bans, `SET ROLE`, schema-qualified rejection, function-call rejection, length bound, LIMIT enforcement and 1000 cap, `UNION`).
- [x] 2.2 Build the accepted column map from one source: static tables keep their declared sets, `subject` contributes `SUBJECT_IDENTITY_COLUMNS` plus its resolved entity columns, each on-surface child table contributes `CHILD_VALUE_COLUMNS`.
- [x] 2.3 Implement the column check over the existing tokenizer: resolve `alias.column` and `table.column` against the statement's table references; accept any reference the parser cannot attribute to a specific relation (design Decision 6).
- [x] 2.4 Update `sql_execution_role.py` to consume the wrapper, and extend `smoke_check_schema` to read from every relation on the resolved surface, not only `WHITELISTED_TABLES`.
- [x] 2.5 Update `scripts/provision_sql_execution_role.py` for the `smoke_check_schema` signature.
- [x] 2.6 Tests in `tests/test_sql_table_whitelist.py`: off-surface relation rejected (row 22); undeclared column rejected with the column named (rows 23, 38); valid `e_skill`/`subject` join accepted (row 24); another tenant's relation rejected (row 25); alias, `USING`, and computed-expression columns accepted (Risk 5).
- [x] 2.7 Tests in `tests/test_sql_execution_privileges.py`: smoke check covers generated relations (row 72) and raises identifiably on a missing grant (row 73); grant/revoke/reactivation/`pg_tables`-skip behaviour unchanged (rows 40, 44, 45, 46).

## 3. Document scoping over the relational surface

- [x] 3.1 Replace the `_DOCUMENT_SCOPE_COLUMNS` constant with a function producing the static map plus `document_id` for `subject` and every child table in `surface.table_names`.
- [x] 3.2 Change `apply_document_scope(sql, scope_columns, param_name)` to take the resolved map and return `(rewritten_sql, rewritten_count)` so the caller can see whether anything was scoped.
- [x] 3.3 In `_run_attempt`, classify a supplied `document_ids` with `rewritten_count == 0` as `empty_with_defect` carrying a scope defect, before execution.
- [x] 3.4 Tests in `tests/test_chat_api_structured_scope.py`: `subject` constrained by a bound predicate with no literals (row 16); a child table joined to `subject` constrained on both (row 17); scope survives aggregation (row 18); scope precedes the row limit (row 19); an unscopeable scoped statement is a defect not a success (rows 20, 54); scope reapplied to every attempt (row 21); the existing static-table scope tests still pass.

## 4. Grounding: relational surface plus semantics plus samples

- [x] 4.1 Replace `EntityProfile` with a surface-keyed grounding value object holding, per relation and per `subject` entity column: identifier, declared type, definition name, description, examples, `value_kind`, `value_unit`, and a bounded sample list.
- [x] 4.2 Keep the existing frequency-ranked sample query over `document_entities`, then re-key its `entity_type` results onto relations/columns via `build_routing_index` / `entity_type_literals`. An entity type claimed by no active definition contributes no samples.
- [x] 4.3 Reinterpret `sql_entity_sample_values_per_type` and `sql_entity_sample_max_values` as per-relation and total caps; keep the per-value `MAX_SAMPLE_VALUE_CHARS` truncation.
- [x] 4.4 Fetch the surface and the samples once per invocation in `generate_and_execute`, resolving the surface from `schema` (design Decision 2 — no `tenant_id` plumbing).
- [x] 4.5 Tests in `tests/test_chat_api_sql_retry.py` (replacing `TestEntityProfile`): surface with columns and types in the prompt (rows 60, 9, 10); samples under their relation (row 61); both caps respected (row 62); a relation with no samples still listed (rows 12, 63); surface and samples fetched once across three attempts (rows 13, 64); one tenant's surface never in another's prompt (rows 65, 4).
- [x] 4.6 Test the base-model path with a `base_label_mapping`-only fixture: samples stored under `PER`/`ORG` land under the mapped relation (rows 11, 15, 14).

## 5. Prompt: relational-only query model

- [x] 5.1 Delete the EAV data-model section of the `generate_sql` prompt — one row per fact, `entity_type` as the filter vocabulary, `document_id`-as-subject-by-convention, the second `document_entities` join for the subject's name, and the EAV-specific filtering rules.
- [x] 5.2 Write the relational data model: `subject` is one row per extracted document keyed by `document_id` with `filename` denormalized and one typed column per single-valued fact; each `e_<slug>` holds many rows per document joined on `document_id`; a child-table query joins `subject` when it needs the filename or a single-valued fact.
- [x] 5.3 Preserve the reasoning guidance that is not EAV-specific: every condition is a real constraint, quantifiers as set operations (`EXISTS` / `NOT EXISTS`), grouping by the thing being ranked, value-precision guidance (`=` versus `ILIKE`), typed columns for quantitative comparisons, and projecting the evidence rather than bare identity.
- [x] 5.4 Render the resolved surface and its semantics into the prompt in place of `WHITELISTED_TABLES` and the old entity-profile block; keep the static tables listed for the questions that still need them.
- [x] 5.5 Require every result row to project `document_id` so the graph's secondary scope filter and citation assembly keep working.
- [x] 5.6 Change `generate_sql`'s signature to take the grounding object and the surface; keep `previous_attempts` and `conversation_context` unchanged.
- [x] 5.7 Narrow `_fix_document_name_reference` to its existing `document_entities` gate and confirm it does not fire on relational SQL (design Decision 8). Keep `_force_nulls_last_on_desc`.
- [x] 5.8 Rewrite `tests/test_chat_api_sql.py::TestSQLPrompt` and `tests/test_sql_generator_candidate_name.py` for the relational directives; keep `tests/test_sql_generator_document_name_fix.py` covering the narrowed static-table path.
- [x] 5.9 Tests: the prompt names `subject` and `e_skill` and contains no `document_entities` query instruction (row 1); a single-valued question targets the `subject` column (row 2); a multi-valued question targets the child table and joins `subject` (row 3); a full read of the rendered prompt confirms no EAV fragment survives (Risk 7).

## 6. Defect ladder and retry feedback

- [x] 6.1 Delete `_entity_type_defect`, `_entity_type_filter_literals`, `_ENTITY_TYPE_EQ_RE`, and `_ENTITY_TYPE_IN_RE`; the relation/column check in group 2 now covers this class pre-execution.
- [x] 6.2 Replace `_wrong_entity_type_defect` with a wrong-relation probe: for each positive `normalized_value = '…'` literal, find the value's `entity_type` in `document_entities`, map it through the routing index to a relation or column, and report a defect only when that relation or column is not one the statement queried. Never fire on an unavailable surface or a failed probe.
- [x] 6.3 Keep `_filename_defect` unchanged; confirm its alias-agnostic regex catches `subject.filename`.
- [x] 6.4 Add the scope defect from task 3.3 to the defect set.
- [x] 6.5 Rewrite `_render_attempt_feedback` for all four defect classes in relational terms; validation feedback restates the available relations and columns. No branch may emit `entity_type`.
- [x] 6.6 Keep `SQLAttemptOutcome`, `RETRYABLE_OUTCOMES`, `SQLAttempt`, the attempt cap, the deadline check, `_sanitize_error`, and the zero-rows-without-defect policy untouched.
- [x] 6.7 Tests in `tests/test_chat_api_sql_retry.py` (replacing `TestWrongEntityTypeDefect`): validation failure retried with the surface restated (rows 26, 47, 59); wrong-relation defect names the holding relation and omits `entity_type` (rows 27, 52, 58); value occurring nowhere is a genuine empty (row 53); unexplained empty is `success` (rows 28, 51); execution error retried with sanitized, parameter-stripped feedback (rows 29, 49, 56, 57); generation error retried (row 50); non-empty never retried (row 55); undeclared column classified `validation_error` (row 48); filename defect on `subject.filename` (row 30).
- [x] 6.8 Grep `src/chat_api/services/sql_generator.py` for `entity_type` and confirm every remaining hit is a grounding or oracle read, never defect detection or feedback text (Risk 4).

## 7. Projection-coverage safety

- [x] 7.1 Add a coverage probe run once per invocation before the attempt loop: does the relational surface hold data for the question's extent — tenant-wide, or the scoped `document_ids` when a scope is supplied.
- [x] 7.2 When the surface holds no data for that extent while `document_entities` does, raise `SQLGenerationFailed` with a coverage reason so `run_tool` reports the structured source as unavailable. Introduce no EAV fallback query.
- [x] 7.3 Confirm a probe failure is best-effort in the same sense as the other probes: a failed probe must not turn a working question into a 500.
- [x] 7.4 Tests: unprojected tenant produces a structured failure and an unavailable-source turn (row 31); unprojected scoped document does the same (row 32); a populated tenant with a genuinely non-matching question returns an empty success (row 33); no EAV fallback statement is executed (Risk 6).
- [x] 7.5 Integration evidence for the migration path in `tests/test_relational_projection_worker.py` or a manual run: promoting a model version and re-running batch extraction reconciles the schema, populates the surface, and lets the next question answer from it (row 34).

## 8. Tool boundary and end-to-end

- [x] 8.1 Reword `StructuredRetrievalTool.description` in `src/shared/retrieval/tools/entity_tools.py` so the planner-facing text describes structured facts about subjects rather than an EAV type/value store. Leave `args_schema` and `_scope_to_document_ids` unchanged.
- [x] 8.2 Confirm `tests/test_retrieval_tools.py`, `tests/test_retrieval_orchestrator.py`, and `tests/test_chat_graph_topology.py` still pass — the tool contract and graph topology are unchanged.
- [x] 8.3 End-to-end tests in `tests/test_chat_api_sql_retry_integration.py`: a valid relational SELECT executes read-only and reaches answer generation (row 35); a rejected `DROP TABLE` is logged and reported as an unavailable source (row 36); a non-whitelisted table is rejected (row 37); a timeout cancels and skips the source (row 39); diagnostics stay internal.
- [x] 8.4 Assert the prompt-named set, the validated set, and the granted set are equal from one resolver call (rows 8, 41) and that no generated relation or column name is hard-coded outside `src/shared/entity_views.py` (Risk 1).
- [x] 8.5 Assert the scope boundary: no diff in `entity_postprocessor.py`, `entity_normalizer.py`, `relational_projection.py`, `worker.py`, `entity_resolver.py`, the `document_entities` schema, or `alembic/`.

## 9. Rollout

- [ ] 9.1 Run `scripts/provision_sql_execution_role.py` in every environment where `sql_execution_role_enabled` is true, before the prompt change is live, so the role holds `SELECT` on every generated relation.
- [ ] 9.2 Run the golden-set eval (`src/shared/retrieval/eval`) and record `structured_query_success_rate` over `simple_structured`, `exact_entity_lookup`, and `attribute_filtering` against the pre-change baseline.
- [x] 9.3 Run the full suite and diff the failing-test set against the recorded baseline for this repo; no new failures attributable to this change.

## 10. Verification & Evidence

- [x] 10.1 Run all acceptance-criteria tests for every scenario in verification.md § Spec Alignment and confirm all pass.
- [x] 10.2 Collect functional evidence (test output / log excerpt / eval report) for each scenario — record one entry per row in verification.md § Evidence Log.
- [x] 10.3 Confirm every Hallucination Risk mitigation step in verification.md § Hallucination Risk Register.
- [x] 10.4 Confirm all ADR compliance steps in verification.md § Pattern & ADR Compliance.
- [ ] 10.5 Complete Audit Record sign-off in verification.md § Audit Record (human reviewer required — this task cannot be marked complete by an agent).
- [x] 10.6 Run `openspec validate relational-only-sql-generation --type change --strict` and confirm it exits clean before archive.
