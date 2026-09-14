"""add provenance, retention and ingesting-actor columns to documents

Every column is additive and defaulted, so an older application version runs unchanged
against the new schema and existing rows stay readable. The defaults are the truth about
what already exists: everything in `documents` today arrived through platform upload and
had its original retained.

Two deliberate absences:

* No unique constraint on `external_id`. Nothing writes an external identity until pull
  sources exist, `documents` is soft-deleted (so a unique index would permanently block
  re-ingesting a re-appearing object), and content-addressed reuse makes the relationship
  many-to-one. The ledger that owns uniqueness arrives with `external-document-sources`.
* No new column for the storage reference. It continues to live in `blob_path`; renaming
  that column belongs to `document-metadata-column-reconciliation`.

Revision ID: 038
Revises: 037
Create Date: 2026-09-07
"""
from alembic import op

revision = "038"
down_revision = "037"
branch_labels = None
depends_on = None

# (column, type, default). Held as data so the template and the per-tenant loop apply the
# same list and cannot drift.
COLUMNS = [
    ("origin", "VARCHAR(32)", "'push'"),
    ("source_type", "VARCHAR(64)", "'platform_upload'"),
    ("source_id", "VARCHAR(128)", "'platform-upload'"),
    ("external_id", "VARCHAR(512)", None),
    ("source_version", "VARCHAR(256)", None),
    ("source_created_at", "TIMESTAMPTZ", None),
    ("source_modified_at", "TIMESTAMPTZ", None),
    ("origin_metadata", "JSONB", None),
    ("retention_mode", "VARCHAR(32)", "'platform_blob'"),
    ("ingested_by_kind", "VARCHAR(32)", "'human'"),
]

# The three declared retention modes and nothing else. A value outside the set is a bug in
# the ingestion operation, and the database is the last place it can be caught.
RETENTION_CHECK = "retention_mode IN ('platform_blob', 'ephemeral', 'source_only')"
RETENTION_CONSTRAINT = "documents_retention_mode_check"


def _add_clauses() -> str:
    clauses = []
    for name, sql_type, default in COLUMNS:
        clause = f"ADD COLUMN IF NOT EXISTS {name} {sql_type}"
        if default is not None:
            clause += f" NOT NULL DEFAULT {default}"
        clauses.append(clause)
    return ", ".join(clauses)


def _drop_clauses() -> str:
    return ", ".join(f"DROP COLUMN IF EXISTS {name}" for name, _, _ in COLUMNS)


def _for_each_tenant_schema(statement: str) -> str:
    """Apply one statement to every provisioned tenant schema, per the 030/034 pattern.

    `statement` is a `format()` template using `%I` for the schema; its own single quotes
    are doubled here because it is embedded in a PL/pgSQL string literal.
    """
    embedded = statement.replace("'", "''")
    return f"""
        DO $$
        DECLARE
            schema_name TEXT;
        BEGIN
            FOR schema_name IN
                SELECT nspname FROM pg_namespace
                WHERE nspname LIKE 'tenant\\_%' AND nspname != 'tenant_template'
            LOOP
                EXECUTE format('{embedded}', schema_name);
            END LOOP;
        END $$;
    """


def upgrade() -> None:
    op.execute(f"ALTER TABLE tenant_template.documents {_add_clauses()}")
    op.execute(
        f"ALTER TABLE tenant_template.documents "
        f"DROP CONSTRAINT IF EXISTS {RETENTION_CONSTRAINT}"
    )
    op.execute(
        f"ALTER TABLE tenant_template.documents "
        f"ADD CONSTRAINT {RETENTION_CONSTRAINT} CHECK ({RETENTION_CHECK})"
    )

    op.execute(
        _for_each_tenant_schema(f"ALTER TABLE IF EXISTS %I.documents {_add_clauses()}")
    )
    op.execute(
        _for_each_tenant_schema(
            f"ALTER TABLE IF EXISTS %I.documents "
            f"DROP CONSTRAINT IF EXISTS {RETENTION_CONSTRAINT}"
        )
    )
    op.execute(
        _for_each_tenant_schema(
            f"ALTER TABLE IF EXISTS %I.documents "
            f"ADD CONSTRAINT {RETENTION_CONSTRAINT} CHECK ({RETENTION_CHECK})"
        )
    )


def downgrade() -> None:
    op.execute(
        _for_each_tenant_schema(
            f"ALTER TABLE IF EXISTS %I.documents "
            f"DROP CONSTRAINT IF EXISTS {RETENTION_CONSTRAINT}"
        )
    )
    op.execute(
        _for_each_tenant_schema(f"ALTER TABLE IF EXISTS %I.documents {_drop_clauses()}")
    )
    op.execute(
        f"ALTER TABLE tenant_template.documents "
        f"DROP CONSTRAINT IF EXISTS {RETENTION_CONSTRAINT}"
    )
    op.execute(f"ALTER TABLE tenant_template.documents {_drop_clauses()}")
