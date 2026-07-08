## Context

The analytics dashboard queries four materialized views per tenant schema (`mv_entity_coverage`, `mv_confidence_distribution`, `mv_extraction_volume`, `mv_document_entity_counts`). Migration `011` created these in `tenant_template` and looped over existing `tenant_*` schemas at the time it ran. Any tenant schema created later (via seed or admin provisioning) has regular tables but no materialized views. The dashboard endpoint silently returns empty arrays because `fetch_widget_data` catches the missing-relation exception.

There are three tenant-provisioning paths today:

- **Seed script** (`src/gateway/seed.py`): Creates `tenant_demo_tenant` schema with tables but no MVs.
- **Alembic migration**: Runs once; only catches schemas that exist at migration time.
- **Admin console "Create Tenant"** (future): Not yet implemented, but the provisioning logic will need to handle MVs.

## Goals / Non-Goals

**Goals:**

- Every existing tenant schema that lacks the four materialized views gets them created and populated.
- New tenants (seed or admin-provisioned) automatically get the MVs at schema-creation time.
- Zero code changes to the analytics service — it already queries the correct view names.
- Existing data in `extracted_entities`, `documents`, and `extraction_runs` is immediately reflected after MV refresh.

**Non-Goals:**

- Changing the MV query logic or schema — the existing definitions from migration `011` are correct.
- Adding new analytics widgets or data sources.
- Improving MV refresh performance (concurrent refresh already exists).

## Currently-In-Force ADRs

| ADR | Decision Summary | Constraint on This Design |
|-----|-----------------|--------------------------|
| ADR-001 | Tenant data isolation via separate PostgreSQL schemas with `search_path` enforcement | Materialized views must be created per tenant schema, not shared. The existing `tenant_<id>` naming convention must be preserved. |

## Decisions

### Decision 1: Backfill via new Alembic migration

**Choice:** Create migration `015` that iterates over all `tenant_*` schemas, creates any missing materialized views using `CREATE MATERIALIZED VIEW IF NOT EXISTS`, and refreshes them with data.

**Rationale:** Alembic is the established migration tool. Running a PL/pgSQL block mirrors migration `011`'s approach and is idempotent. This catches any tenant schema that was missed.

**Alternatives considered:**
- **On-query creation in analytics service**: Adds complexity and latency to dashboard requests. Violates separation of concerns (schema management belongs in migrations/provisioning).
- **Single script outside Alembic**: Fragile — no version tracking, easy to forget.

### Decision 2: Update seed script to create MVs

**Choice:** After creating tenant tables in `seed.py`, execute the same `CREATE MATERIALIZED VIEW` statements used in migration `011`.

**Rationale:** The seed script is the canonical place for demo/local-dev data setup. If it creates tables, it should also create the MVs those tables support, otherwise the analytics page is permanently empty in dev.

**Alternatives considered:**
- **Run migrations after seed**: Migrations run before seed. Changing the order would break other assumptions.
- **Call a shared function**: Both migration `011` and seed define their own SQL strings. A shared utility would be cleaner but requires a refactor that's out of scope.

### Decision 3: Refresh MVs immediately after creation

**Choice:** After creating the MVs (in both migration and seed), run `REFRESH MATERIALIZED VIEW` to populate them from existing data.

**Rationale:** Users should see their existing extraction data in the dashboard immediately, not after the next extraction event triggers a refresh.

## Risks / Trade-offs

- [**Large tenants** — REFRESH MATERIALIZED VIEW locks the view for reads until complete] → Use `REFRESH MATERIALIZED VIEW CONCURRENTLY` (requires a unique index, which migration `011` already creates). The backfill migration uses `CONCURRENTLY` to avoid blocking dashboard reads.
- [**Seed script duplicates SQL strings from migration `011`** — drift risk if MV definitions change] → Acceptable trade-off for now. If MVs are modified in a future migration, the seed script must be updated in the same change.

## Migration Plan

1. Create Alembic migration `015` that:
   - Iterates all `tenant_*` schemas (excluding `tenant_template`)
   - For each, creates any of the four MVs that are missing using `CREATE MATERIALIZED VIEW IF NOT EXISTS`
   - Creates unique indexes if missing
   - Refreshes all four MVs with `REFRESH MATERIALIZED VIEW CONCURRENTLY`
2. Update `src/gateway/seed.py` to create and refresh MVs after creating tenant tables.
3. Run `alembic upgrade head` (part of normal `db-init`).
4. Verify analytics dashboard shows populated widgets.

**Rollback:** Downgrade migration `015` drops the MVs it created. Seed changes are reverted by reverting the seed.py edit.

## Open Questions

- None.
