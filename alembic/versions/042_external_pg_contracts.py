"""canonical external-postgresql schema contracts and tenant schema index (CAP-4)

ADR-013 keeps versioned canonical JSON contracts as tenant-bound, non-content
control-plane records in `public`, with a deterministic fingerprint and safe
validation/publish state. The tenant-isolated schema-index representation lives
beside the tenant documents it describes and is context only -- it never
authorizes access.

Additive: new tables, empty by definition, so no backfill and no existing row
changes meaning.

Revision ID: 042
Revises: 041
Create Date: 2026-09-10
"""
from alembic import op

revision = "042"
down_revision = "041"
branch_labels = None
depends_on = None


def _for_each_tenant_schema(statement: str) -> str:
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


PUBLIC_DDL = """
CREATE TABLE IF NOT EXISTS public.external_pg_contracts (
    id VARCHAR PRIMARY KEY,
    tenant_id VARCHAR(64) NOT NULL,
    connection_id VARCHAR NOT NULL,
    version INTEGER NOT NULL,
    canonical JSONB NOT NULL,
    fingerprint VARCHAR(64) NOT NULL,
    validation_state VARCHAR(32) NOT NULL DEFAULT 'draft',
    validation_reason VARCHAR(64) NOT NULL DEFAULT 'none',
    published BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    published_at TIMESTAMPTZ,
    UNIQUE (tenant_id, connection_id, version)
)
"""

PUBLIC_INDEX_DDL = """
CREATE INDEX IF NOT EXISTS ix_external_pg_contracts_lookup
    ON public.external_pg_contracts (tenant_id, connection_id, published, version DESC)
"""

TENANT_DDL = """
CREATE TABLE IF NOT EXISTS %I.external_pg_schema_index (
    connection_id VARCHAR NOT NULL,
    contract_version INTEGER NOT NULL,
    relation_name VARCHAR(256) NOT NULL,
    entry_text TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (connection_id, contract_version, relation_name)
)
"""


def upgrade() -> None:
    op.execute(PUBLIC_DDL)
    op.execute(PUBLIC_INDEX_DDL)
    op.execute(TENANT_DDL.replace("%I", "tenant_template"))
    op.execute(_for_each_tenant_schema(TENANT_DDL))


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS public.external_pg_contracts")
    op.execute("DROP TABLE IF EXISTS tenant_template.external_pg_schema_index")
    op.execute(_for_each_tenant_schema("DROP TABLE IF EXISTS %I.external_pg_schema_index"))
