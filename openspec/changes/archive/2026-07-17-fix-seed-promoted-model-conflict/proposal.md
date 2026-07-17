## Why

The `gateway/seed.py` script fails on re-run when it tries to insert a promoted model version for `demo-tenant` because a unique partial index (`idx_model_versions_tenant_promoted`) enforces at most one row with `status = 'promoted'` per tenant. This causes `db-init` to exit 1, which blocks the `extraction_service` container from starting (its `depends_on` requires `db-init: service_completed_successfully`).

## What Changes

- Add an existence check in `seed.py` before inserting the promoted model version for `demo-tenant`. If a promoted model already exists, skip the insert.

## Capabilities

### New Capabilities

_(none — this is a bug fix)_

### Modified Capabilities

_(none — the seed script is a development/infrastructure concern, not a spec-level capability)_

## Impact

- **`src/gateway/seed.py`** (~line 297): Add a `SELECT` check before the promoted model `INSERT`.
- **Downstream**: `db-init` completes successfully on re-run, which unblocks `extraction_service` (and any other service that depends on `db-init`).

## Open Questions

None.
