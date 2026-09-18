"""durable azure blob sync ledger in every tenant schema (CAP-3)

ADR-012 keeps sync runs, the source object/version ledger, the durable lease,
and the retrieval-hiding list beside the tenant documents they describe. These
four tables carry opaque source identity, version tokens, finite outcome
classes, and document linkage only -- never bytes, credentials, endpoints, or
provider diagnostics.

Additive: new tables, empty by definition, so no backfill and no existing row
changes meaning.

Revision ID: 050
Revises: 049
Create Date: 2026-09-10

NOTE (renumbered 2026-09-16): originally revision "041" (down_revision "040"),
colliding with main's own "041". Renumbered to 050 — see 049's note.
"""
from alembic import op

revision = "050"
down_revision = "049"
branch_labels = None
depends_on = None


def _for_each_tenant_schema(statement: str) -> str:
    """Apply one statement to every provisioned tenant schema, per the 038 pattern.

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


TABLES = [
    """
    CREATE TABLE IF NOT EXISTS %I.azure_blob_sync_runs (
        id VARCHAR PRIMARY KEY,
        tenant_id VARCHAR(64) NOT NULL,
        connection_id VARCHAR NOT NULL,
        trigger VARCHAR(32) NOT NULL,
        outcome VARCHAR(32) NOT NULL DEFAULT 'started',
        reason VARCHAR(64) NOT NULL DEFAULT 'none',
        objects_seen INTEGER NOT NULL DEFAULT 0,
        objects_ingested INTEGER NOT NULL DEFAULT 0,
        objects_skipped INTEGER NOT NULL DEFAULT 0,
        objects_failed INTEGER NOT NULL DEFAULT 0,
        started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        completed_at TIMESTAMPTZ
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS %I.azure_blob_source_objects (
        connection_id VARCHAR NOT NULL,
        object_identity VARCHAR(1024) NOT NULL,
        source_version VARCHAR(256),
        document_id VARCHAR,
        missing_sightings INTEGER NOT NULL DEFAULT 0,
        confirmed_missing BOOLEAN NOT NULL DEFAULT FALSE,
        last_seen_at TIMESTAMPTZ,
        PRIMARY KEY (connection_id, object_identity)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS %I.azure_blob_sync_leases (
        connection_id VARCHAR PRIMARY KEY,
        run_id VARCHAR NOT NULL,
        acquired_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        expires_at TIMESTAMPTZ NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS %I.azure_blob_hidden_documents (
        document_id VARCHAR PRIMARY KEY,
        connection_id VARCHAR NOT NULL,
        cause VARCHAR(32) NOT NULL,
        hidden_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_blob_sync_runs_conn
        ON %I.azure_blob_sync_runs (connection_id, started_at DESC)
    """,
]


def upgrade() -> None:
    for ddl in TABLES:
        op.execute(ddl.replace("%I", "tenant_template"))
    for ddl in TABLES:
        op.execute(_for_each_tenant_schema(ddl))


def downgrade() -> None:
    for table in (
        "azure_blob_sync_runs",
        "azure_blob_source_objects",
        "azure_blob_sync_leases",
        "azure_blob_hidden_documents",
    ):
        op.execute(f"DROP TABLE IF EXISTS tenant_template.{table}")
        op.execute(_for_each_tenant_schema(f"DROP TABLE IF EXISTS %I.{table}"))
