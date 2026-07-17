## Context

The `gateway/seed.py` script inserts a promoted model version for `demo-tenant` at line 297-308 using `ON CONFLICT (id) DO NOTHING`. However, the `model_versions` table has a partial unique index `idx_model_versions_tenant_promoted` on `(tenant_id) WHERE status = 'promoted'`. On re-run, a new UUID is generated, so there's no conflict on `id`, but the unique index rejects a second promoted row for the same tenant. This causes the `INSERT` to raise a `UniqueViolationError`, `db-init` exits 1, and the `extraction_service` (which depends on `db-init: service_completed_successfully`) stays in `Created` state.

## Goals / Non-Goals

**Goals:**
- Make `db-init` idempotent for the promoted model insert — skip if one already exists.

**Non-Goals:**
- No changes to the model_versions schema or unique index.
- No changes to any runtime service code.
- No changes to MLflow registration or model promotion flow.

## Currently-In-Force ADRs

None apply — this is an infrastructure/seed concern, not an architectural decision.

## Decisions

### Decision 1: Add existence check before insert

**Choice:** Add a `SELECT` query before the promoted model `INSERT` to check if a row with `status = 'promoted'` already exists for `demo-tenant`. If it does, skip the insert (and the "Seeded promoted model" print).

**Rationale:** The seed script already uses this pattern for other entities (users, documents, spans) — it checks `SELECT id FROM ... WHERE ...` and skips if found. This change makes the promoted model seed consistent with the rest of the script.

**Alternatives considered:**
- **Remove the seed insert entirely**: The promoted model row is helpful for end-to-end testing. Keeping it is worthwhile.
- **Use `ON CONFLICT (tenant_id) WHERE status = 'promoted' DO NOTHING`**: PostgreSQL supports `ON CONFLICT` with partial unique indexes, but this couples the insert to the exact index definition and is less readable than an explicit existence check.

## Risks / Trade-offs

- [If a future migration changes the unique index's WHERE clause, the SELECT check could become stale] → Mitigation: the check mirrors the index logic (`WHERE status = 'promoted'`), which is defined in the same migration. Both would need coordinated changes.

## Migration Plan

1. Add existence check before the promoted model INSERT in `seed.py`.
2. Run `docker-compose up -d --build db-init` to rebuild and execute the fixed seed.
3. The `extraction_service` (and other dependent services) will auto-start once `db-init` completes successfully.

Rollback: Revert the seed.py change and delete the downstream `model_versions` row if needed.

## Open Questions

None.
