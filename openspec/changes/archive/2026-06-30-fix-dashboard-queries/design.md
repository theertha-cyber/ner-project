## Context

The gateway's `GET /api/v1/dashboard/summary` endpoint dispatches to role-specific handlers. Currently only `_system_admin_data` receives a database session and queries `public.tenants` for the tenant count. The other three handlers (`_tenant_admin_data`, `_annotator_data`, `_business_user_data`) accept no parameters and return hardcoded placeholder values (`null` / `"—"` / `"service unavailable"`).

The database has a full set of tenant-scoped tables (documents, annotation_tasks, spans, training_jobs, model_versions, extraction_runs, extracted_entities) created from the `tenant_template` schema. However, the gateway's `get_db` dependency does not set `search_path` — it returns a session pointed at the `public` schema. Additionally, the `training_jobs` and `model_versions` tables have a column drift between migration 002 (older column set) and migration 005 (newer column set including `metrics` JSONB), which must be reconciled before queries against `metrics` can work.

## Goals / Non-Goals

**Goals:**
- Wire real SQL queries for `_tenant_admin_data`, `_annotator_data`, and `_business_user_data`
- Pass `db` session and `tenant_id` to all role handlers
- Use schema-qualified table names (`tenant_{id}.table`) to avoid changing the gateway's `get_db` search_path behavior
- Wrap every query in independent try/catch with null-on-failure semantics
- Reconcile migration 002/005 column drift so `training_jobs.metrics` and `model_versions.metrics` exist as JSONB
- Add `"extraction"` to the `sources` map
- Seed realistic demo data so the dashboard displays non-zero values

**Non-Goals:**
- No frontend changes — the UI already renders `null` as `"—"` correctly
- No cross-service HTTP calls — all data comes from gateway's own DB session (MVP pragmatism)
- No materialized view refresh pipeline changes (analytics dashboard is separate)

## Currently-In-Force ADRs

| ADR | Decision Summary | Constraint on This Design |
|-----|-----------------|--------------------------|
| ADR-001 | Tenant data isolation via separate DB schemas | Tenant-scoped tables live in `tenant_{id}` schemas; queries must qualify schema |
| ADR-004 | OpenSpec spec-driven development governance | Evidence required for every AC; verification.md must exist before tasks |
| ADR-005 | OpenCode agent permissions | Atomic task descriptions needed for agent-safe implementation |

## Decisions

### Decision 1: Schema-qualified table names over search_path switching

**Choice:** Use explicit `tenant_{tenant_id}.table_name` in all SQL queries rather than modifying the gateway's `get_db` to set `search_path`.

**Rationale:** The gateway's `get_db` is also used for `public.*` queries (tenants, tenant_users, entity_definitions). Setting `search_path` per-request would require resetting it after or using a separate session factory. Explicit qualification is safer, more readable, and consistent with how the gateway service already works (see `tenant_service.py`, `user_service.py` which all use `public.*`).

**Alternatives considered:**
- Add a `get_tenant_db` dependency that sets `search_path` — ruled out because it introduces a parallel DB dependency that could diverge from `get_db`
- Use SQLAlchemy schema translation map — ruled out due to complexity with raw SQL queries via `text()`

### Decision 2: Gateway queries tenant schemas directly (no service calls)

**Choice:** The dashboard endpoint queries tenant-scoped tables directly from the gateway's DB connection instead of making HTTP calls to document-service, annotation-service, etc.

**Rationale:** For MVP, this avoids the latency and reliability complexity of inter-service HTTP calls for a read-only dashboard. All tenant data lives in the same PostgreSQL instance. If services later split to separate databases, the dashboard would switch to aggregator/event-sourced pattern.

**Alternatives considered:**
- HTTP calls to each service — ruled out for MVP due to N+1 request overhead and partial-failure complexity
- Materialized views aggregating across services — viable long-term but over-engineering for MVP

### Decision 3: Reconcile migration drift with a new migration

**Choice:** Add a new Alembic migration that alters the `tenant_template` schema to add the missing `metrics` JSONB column to `training_jobs` and `model_versions`, and refreshes existing tenant schemas with the same DDL.

**Rationale:** The drift between 002 and 005 means `training_jobs.metrics` (JSONB) and other 005 columns don't exist in tenant schemas created by migration 002. Dashboard queries for F1 scores depend on `model_versions.metrics->>'f1'`. Fixing the template and backfilling existing tenant schemas is the cleanest approach.

**Alternatives considered:**
- Query both column sets and coalesce — fragile, doesn't fix root cause
- Ignore drift and only query columns that exist in both — loses access to newer metrics data

## Risks / Trade-offs

- [Schema-qualified names introduce SQL injection surface] → Sanitize `tenant_id` by validating UUID format and replacing hyphens with underscores before interpolation; never use raw user input
- [Migration reconciliation may conflict with existing tenant data] → The new migration uses `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` so it's idempotent across all tenant schemas
- [Gateway coupling to tenant schema internals] → If a service changes its schema, the dashboard query breaks. Mitigated by keeping queries focused on stable table/column names and adding integration tests
- [Empty tables still show zeroes after wiring] → Demo seed script needed alongside query wiring to make the dashboard useful during development

## Migration Plan

1. Create Alembic migration `012_reconcile_training_jobs_columns.py` that adds missing columns to `tenant_template` and all existing `tenant_{id}` schemas
2. Wire `tenant_id` dependency into the dashboard route handler
3. Refactor `_tenant_admin_data` to accept `db` and `tenant_id`, write queries
4. Refactor `_annotator_data` to accept `db`, `tenant_id`, and `user_id`, write queries
5. Refactor `_business_user_data` to accept `db` and `tenant_id`, write queries
6. Add `"extraction"` to `_null_sources()` and `_ROLE_SERVICES`
7. Create seed script or extend existing seed to populate tenant schema tables
8. Update existing tests and add new tests for each role handler
9. Manual verification: log in as each role and confirm dashboard shows real data

Rollback: Revert the route dispatch change and handler signatures; all handlers fall back to placeholder-only return values.

## Open Questions

- Should the `annotator` handler filter tasks by `assignee` (JWT `user_id`) or by `annotator_user_id` in `annotation_tasks`? Need to verify the column name used in practice.
- What's the 500-span training threshold source of truth? Currently hardcoded as a constant — should it come from tenant settings?
- Seed data: what entity types and documents should the demo seed create to make the dashboard visually meaningful?
