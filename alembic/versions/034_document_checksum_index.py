"""index documents.checksum so the upload duplicate lookup stays cheap

The `checksum` column itself has existed since migration 002; this only adds the
index it never got. Non-unique on purpose — byte-identical uploads are identified
and linked, never rejected, so duplicate checksum values are expected.

Revision ID: 034
Revises: 033
Create Date: 2026-08-10
"""
from alembic import op

revision = "034"
down_revision = "033"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_documents_checksum "
        "ON tenant_template.documents (checksum)"
    )

    # Already-provisioned tenant schemas were copied from tenant_template before
    # this index existed, so they need it applied directly. New tenants inherit it
    # via `LIKE tenant_template.documents INCLUDING INDEXES` in tenant_service.py.
    op.execute("""
        DO $$
        DECLARE
            schema_name TEXT;
        BEGIN
            FOR schema_name IN
                SELECT nspname FROM pg_namespace
                WHERE nspname LIKE 'tenant\\_%' AND nspname != 'tenant_template'
            LOOP
                IF to_regclass(format('%I.documents', schema_name)) IS NOT NULL THEN
                    EXECUTE format(
                        'CREATE INDEX IF NOT EXISTS ix_documents_checksum ON %I.documents (checksum)',
                        schema_name
                    );
                END IF;
            END LOOP;
        END $$;
    """)


def downgrade() -> None:
    op.execute("""
        DO $$
        DECLARE
            schema_name TEXT;
        BEGIN
            FOR schema_name IN
                SELECT nspname FROM pg_namespace WHERE nspname LIKE 'tenant\\_%'
            LOOP
                EXECUTE format('DROP INDEX IF EXISTS %I.ix_documents_checksum', schema_name);
            END LOOP;
        END $$;
    """)
