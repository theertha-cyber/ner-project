## 1. Baseline

- [x] 1.1 Confirm Docker Postgres is reachable on host port **55432** (not 5432 — a native PostgreSQL 18 service occupies 5432 and returns a misleading auth failure). Record the connection string used.
- [ ] 1.2 Run the full pytest suite on unmodified `main` and save the summary line plus the sorted list of failing/erroring test ids to a scratch file. This is the baseline; the suite is expected red (~89 failed / 31 errors). Do not chase pre-existing failures.
- [x] 1.3 Confirm the current alembic head is `036` (`alembic current` / `alembic heads`).

## 2. Identifier slugging (everything depends on this)

- [x] 2.1 Create `src/shared/entity_views.py` with a module docstring that states: why the view layer exists (EAV write model, normalized read model), the `LEFT JOIN`-from-`documents` rationale, the `MAX()` tie-break and what breaks when a `multi` entity is wrongly marked `single`, the two-column typed/text projection rationale, the `subject` DROP+CREATE rationale, the case-insensitive + `base_label_mapping` predicate rationale, and the **step-3 prerequisite**: `TenantService.create_tenant()` clones via `pg_tables` + `CREATE TABLE … (LIKE …)`, which excludes views, so a newly provisioned tenant gets zero entity views until the reconciler is wired in.
- [x] 2.2 Implement `to_sql_identifier(name: str, taken: set[str]) -> str`: lowercase, non-alphanumerics to `_`, collapse `_` runs, strip leading/trailing `_`, prefix `e_`, truncate to 63 **before** appending any collision suffix, deterministic numeric suffix (`_2`, `_3`, …) against `taken`, fallback base `e_unnamed` for degenerate input, never raises. Docstring must state the fallback and why the function is total.
- [x] 2.3 Add `_checked_identifier`-style validation for the `schema` argument, mirroring `src/chat_api/services/sql_execution_role.py:41-45`. Do **not** import from that module (it pulls `sql_generator` and the whole chat stack into `gateway`); duplicate the four lines with a comment naming the original.
- [x] 2.4 Define the `EntityDefinitionSpec` dataclass: `name`, `sql_identifier`, `cardinality`, `value_kind`, `is_active`, `base_label_mapping`.
- [x] 2.5 Write `tests/test_entity_views_generator.py::TestToSqlIdentifier` covering scenarios 1–7: `"Skills & Tools"` → `e_skills_tools`; `"select"` → `e_select`; `"2024 Revenue"` matches the pattern; 200-char name with a pre-taken slug stays ≤63 and avoids `taken`; `"Vendor Name"` / `"vendor-name"` collide-and-differ deterministically; `""` / `"---"` / pure-Unicode names return valid identifiers without raising; `"; DROP TABLE documents; --"` produces an inert identifier. No database.

## 3. Migration 037

- [x] 3.1 Write `alembic/versions/037_entity_definitions_view_metadata.py` with `revision = "037"`, `down_revision = "036"`, and a docstring in the style of `035`/`036` — explain *why* each column exists and what the `multi` default means for pre-existing rows, not just what it does.
- [x] 3.2 `upgrade()`: `ALTER TABLE public.entity_definitions ADD COLUMN IF NOT EXISTS cardinality VARCHAR(16) NOT NULL DEFAULT 'multi'` and `ADD COLUMN IF NOT EXISTS sql_identifier VARCHAR(63)`. No `tenant_%` loop — `entity_definitions` is a shared `public` table.
- [x] 3.3 Add `ck_entity_definitions_cardinality CHECK (cardinality IN ('single','multi'))`. VARCHAR + CHECK rather than an ENUM, matching `036`'s `processing_mode`.
- [x] 3.4 Backfill `sql_identifier` in Python inside `upgrade()`: select `id, tenant_id, name` ordered by `(tenant_id, created_at, id)`, feed a per-tenant `taken` set through the **imported** `to_sql_identifier` from `src/shared/entity_views.py`, and `UPDATE` each row. Do not reimplement the slug rule in SQL — a second implementation will drift and orphan views.
- [x] 3.5 Add `CREATE UNIQUE INDEX IF NOT EXISTS uq_entity_definitions_tenant_sql_identifier ON public.entity_definitions (tenant_id, sql_identifier) WHERE sql_identifier IS NOT NULL`. Partial, because `entity_service` does not assign the identifier yet (step 3) and new rows will legitimately carry NULL.
- [x] 3.6 `downgrade()`: drop the index, the CHECK constraint, and both columns.
- [x] 3.7 Add `cardinality` and `sql_identifier` to `EntityDefinition` in `src/gateway/models/__init__.py:73`, matching the column types and the `multi` default.
- [x] 3.8 Confirm `src/gateway/verify_schema.py` needs no edit — it derives expectations reflectively at line 40 (`declared[table.name] = {c.name for c in table.columns}`). Record the confirmation; do not add a hardcoded list.
- [x] 3.9 Write `tests/test_migration_037_entity_view_metadata.py` covering scenarios 34–36: a pre-existing row gains `cardinality='multi'` and a valid `sql_identifier`; `cardinality='many'` is rejected by the CHECK; two tenants may share an identifier while a duplicate within one tenant is rejected. Follow the `importlib.util.spec_from_file_location` + `MigrationContext`/`Operations` pattern in `tests/test_tenant_schema_reconciliation.py:1-30`.
- [x] 3.10 Add a test asserting the migration's backfilled identifiers equal what `to_sql_identifier` produces for the same ordered inputs — the anti-drift guard for task 3.4.
- [x] 3.11 Apply `037` against the dev database on port 55432, then `alembic downgrade 036`, then re-apply. Confirm the shape returns to its `036` state on downgrade.

## 4. DDL generators (pure functions, no DB)

- [x] 4.1 Implement the predicate builder: `upper(<alias>entity_type) IN ('<UPPER(NAME)>', <uppercased base_label_mapping keys>)`. Every literal must come from a slugged/escaped source — never a raw tenant name. A definition with NULL or empty `base_label_mapping` emits the name literal alone.
- [x] 4.2 Implement the child-view builder: `CREATE OR REPLACE VIEW <schema>.<sql_identifier> WITH (security_barrier) AS SELECT document_id, entity_value AS value, normalized_value, value_number, value_number_high, value_date, value_date_high, value_unit, confidence, page_number, occurrence_count FROM <schema>.document_entities WHERE <predicate>`. `CREATE OR REPLACE` — the column list is fixed, so the OID and any future grants survive.
- [x] 4.3 Implement the `subject` builder: `DROP VIEW IF EXISTS <schema>.subject CASCADE` followed by `CREATE VIEW <schema>.subject WITH (security_barrier) AS SELECT d.id AS document_id, d.filename, <pivots> FROM <schema>.documents d LEFT JOIN <schema>.document_entities e ON e.document_id = d.id GROUP BY d.id, d.filename`. Zero `single` definitions must still emit valid SQL (identity + filename only).
- [x] 4.4 Implement pivot column naming: `sql_identifier` minus the `e_` prefix, collision-checked against `{document_id, filename}` plus every name already projected and every `_text` variant, resolved with the same deterministic numeric suffix.
- [x] 4.5 Implement typed projection: a non-text `value_kind` emits both `MAX(e.value_number|e.value_date) FILTER (…) AS <col>` and `MAX(e.entity_value) FILTER (…) AS <col>_text`; a text kind emits one column. No `COALESCE`, no `::text` cast.
- [x] 4.6 Implement `build_entity_view_statements(schema, definitions) -> list[str]` assembling the above. Returns statements, executes nothing, deterministic ordering (sort definitions by `sql_identifier`) so repeated calls are byte-identical.
- [x] 4.7 Implement the drop companion (`build_drop_view_statements` or a documented flag): `DROP VIEW IF EXISTS <schema>.<sql_identifier>` for inactive/absent definitions. Assert by construction that the module emits no `DROP TABLE`, `DELETE`, or `TRUNCATE`.
- [x] 4.8 Extend `tests/test_entity_views_generator.py` for scenarios 8–12, 14–15, 16–17, 19–21, 24: no-database generation, idempotency (two calls equal), invalid schema raises, one and three child views, predicate with and without base labels, `subject` with zero/one/typed/identity-colliding `single` specs, drop-before-create ordering, inactive definition yields a drop and no create.
- [x] 4.9 Add an injection test asserting the DDL generated from a definition named `"; DROP TABLE documents; --"` contains no `DROP TABLE` and no unescaped quote (pairs with scenario 7).

## 5. Reconciler

- [x] 5.1 Add a local `list_tenant_schemas(session)` helper (`SELECT nspname FROM pg_namespace WHERE nspname LIKE 'tenant\_%' ORDER BY nspname`), with a comment naming `sql_execution_role.list_tenant_schemas` as the original and stating why it is not imported.
- [x] 5.2 Implement `async def reconcile_entity_views(session, schema, definitions) -> list[str]`: guard on `IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = :schema AND table_name = 'document_entities')` — mirroring `029`/`035` — returning `[]` for a schema that lacks it rather than raising. Execute the generated statements in order via `text()`; return what was applied. Log at the same level and shape as `provision_role`.
- [x] 5.3 Skip definitions with a NULL `sql_identifier` rather than slugging at read time — a read-time slug is non-deterministic across processes and would create views the catalog does not know about.
- [x] 5.4 Write `tests/test_entity_views_reconciler.py` for scenarios 13, 18, 22–23, 25–31 against a real schema, following the fixture conventions in `tests/test_tenant_provisioning.py` and `tests/test_tenant_schema_reconciliation.py`: mixed-case rows returned by the child view; entity-less document still appears in `subject`; adding a `single` definition and reconciling gains the column with no `cannot change name of view column` error; re-running is a no-op; dropping a view leaves `document_entities` row count unchanged; missing view created; stale view repaired; orphaned view dropped; schema without `document_entities` skipped; empty definition list still yields `subject`; second identical run changes nothing.
- [x] 5.5 Confirm the reconciler runs inside the caller's transaction (no internal `commit`), so the `subject` drop/create window is never observable.

## 6. Scope guard

- [x] 6.1 `git diff --stat` must show no change to `src/chat_api/services/sql_generator.py`, `src/chat_api/services/sql_execution_role.py`, `src/gateway/services/entity_service.py`, or `src/gateway/services/tenant_service.py`. `WHITELISTED_TABLES`, the grant list, and the generator prompt are steps 4–6.
- [x] 6.2 Confirm no new dependency was added (`pyproject.toml` / `poetry.lock` unchanged).
- [x] 6.3 Confirm nothing in the running system calls `reconcile_entity_views` — grep for callers outside `tests/`; there must be none.

## 7. Verification & Evidence

- [ ] 7.1 Run all acceptance-criteria tests for every scenario in verification.md § Spec Alignment and confirm all pass.
- [ ] 7.2 Collect functional evidence (test output / query transcript / migration log) for each scenario — record one entry per row in verification.md § Evidence Log. Include the baseline-vs-post pytest diff from task 1.2 showing no newly failing test.
- [ ] 7.3 Confirm every Hallucination Risk mitigation step in verification.md § Hallucination Risk Register.
- [ ] 7.4 Confirm all ADR compliance steps in verification.md § Pattern & ADR Compliance.
- [ ] 7.5 Complete Audit Record sign-off in verification.md § Audit Record (human reviewer required — this task cannot be marked complete by an agent).
- [ ] 7.6 Run `openspec validate entity-view-layer-foundation --type change --strict` and confirm it exits clean before archive.
- [ ] 7.7 Write the summary the task asked for: every design decision made where the spec left a choice open, the `CREATE OR REPLACE` column-change strategy picked, the case-sensitivity finding for `entity_type` vs `entity_definitions.name`, and anything found that invalidates an assumption in the original brief.
