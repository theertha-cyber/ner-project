## Why

The analytics dashboard (`/analytics`) always shows empty widgets because the materialized views it queries (`mv_entity_coverage`, `mv_confidence_distribution`, `mv_extraction_volume`, `mv_document_entity_counts`) are never created for tenants. Migration `011` created them only in schemas that existed at migration time. The seed script and tenant provisioning flow create tables but skip the materialized views. The `fetch_widget_data` function silently catches the "relation does not exist" error and returns `[]`, so no error surfaces — just permanently empty charts.

## What Changes

- Create a new Alembic migration that backfills missing materialized views into any tenant schema that lacks them
- Update the seed script (`src/gateway/seed.py`) to create materialized views after creating tenant tables
- Update the admin tenant-provisioning flow (if it creates schemas directly) to also create MVs
- Add a one-time refresh of the newly created MVs so existing data is immediately visible

## Capabilities

### New Capabilities

- `analytics-materialized-views`: Create and backfill the four materialized views (`mv_entity_coverage`, `mv_confidence_distribution`, `mv_extraction_volume`, `mv_document_entity_counts`) in all tenant schemas that lack them, covering seed-created, migration-created, and admin-provisioned tenants.

### Modified Capabilities

- *(none — no existing spec's requirements change)*

## Impact

- **Database**: Four new materialized views per tenant schema (if absent), with unique indexes. Existing data in `extracted_entities`, `documents`, and `extraction_runs` tables is immediately reflected after refresh.
- **Analytics service**: No code changes needed — the dashboard endpoint already queries the correct view names. Views will return populated data instead of silently empty arrays.
- **Seed script**: Adding MV creation after table creation.
- **Alembic**: One new migration (revises current head `014`).
- **Performance**: Materialized views are refreshed on extraction events (existing `REFRESH MATERIALIZED VIEW CONCURRENTLY` in query.py line 167-170) and on demand via the refresh endpoint. Initial backfill may be heavy for tenants with large datasets.

## Open Questions

- Should the MVs be refreshed automatically after creation, or should the first extraction event or manual refresh trigger it? (Preference: refresh immediately after creation so the dashboard shows data without waiting for the next extraction event.)
- Are there any tenant schemas with corrupted or inconsistent data that might cause the MV creation queries to fail? (The `IF NOT EXISTS` guard in migration 011 handles idempotency.)
