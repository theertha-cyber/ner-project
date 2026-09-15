# Alembic migrations

Standard Alembic setup (`env.py`, `script_location = alembic`). Revisions are linear,
numbered `NNN_description.py`; `sqlalchemy.url` is overridden at runtime from
`NER_DATABASE_URL_SYNC` (falling back to `NER_DATABASE_URL` with `+asyncpg` stripped) so
the same migrations run unchanged in Compose and CI.

## Tenant-scoped migrations also touch the tenant-store baseline (ADR-017)

Since migration 043, every migration that changes a tenant-scoped table (anything under
`tenant_template`, applied to every `tenant_<id>` schema via the `pg_namespace` loop in
`tenant_schema_ddl.apply_to_all_tenant_schemas`) must **also** ship a matching revision
in `src/shared/tenant_store/revisions/NNNN_<name>.py`.

Why: a `tenant_owned` tenant's schema does not live on the platform database, so this
migration's `ALTER TABLE ... tenant_<id>` loop never reaches it. The only thing that
does is the deploy-time `src/shared/tenant_store/migrate.py` step, which applies pending
revisions per tenant store. `tests/test_tenant_store_parity.py` fails the build — naming
the differing table and column — when `tenant_template` at head and
`src/shared/tenant_store/baseline.py` + every revision disagree.

A tenant-store revision module exposes:

```python
REVISION = <int>  # unique, strictly increasing across all revision modules

def statements(schema: str) -> list[str]:
    """Idempotent DDL — IF NOT EXISTS, or a pg_constraint guard for ADD CONSTRAINT."""
```

Write the DDL once as data (a template string keyed by `{schema}`) and call it from
both the Alembic migration's `tenant_schema_ddl` loop and the revision's `statements()`,
the way `alembic/versions/038_document_provenance_and_retention.py` builds its
`COLUMNS` list — never duplicate the column list by hand in two places.

`src/shared/tenant_store/baseline.py` itself only changes when the *baseline* revision
number changes (`src/shared/tenant_store/baseline.py::BASELINE_REVISION`), which should
not happen again — the baseline is the head-043 shape once, permanently; every
change after it ships as a numbered revision.
