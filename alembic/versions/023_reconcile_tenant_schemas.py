"""reconcile every existing tenant schema to the current tenant_template shape

Revision ID: 023
Revises: 022
Create Date: 2026-07-27
"""
from alembic import op

revision = "023"
down_revision = "022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        DO $$
        DECLARE
            schema_name TEXT;
            tmpl_table TEXT;
            missing_col RECORD;
            col_type TEXT;
            col_default TEXT;
            col_not_null BOOLEAN;
            add_clause TEXT;
        BEGIN
            FOR schema_name IN
                SELECT nspname FROM pg_namespace
                WHERE nspname LIKE 'tenant\\_%' AND nspname != 'tenant_template'
            LOOP
                FOR tmpl_table IN
                    SELECT tablename FROM pg_tables WHERE schemaname = 'tenant_template'
                LOOP
                    IF to_regclass(format('%I.%I', schema_name, tmpl_table)) IS NULL THEN
                        EXECUTE format(
                            'CREATE TABLE %I.%I (LIKE tenant_template.%I INCLUDING DEFAULTS INCLUDING CONSTRAINTS INCLUDING INDEXES)',
                            schema_name, tmpl_table, tmpl_table
                        );
                    ELSE
                        FOR missing_col IN
                            SELECT c.column_name
                            FROM information_schema.columns c
                            WHERE c.table_schema = 'tenant_template' AND c.table_name = tmpl_table
                              AND c.column_name NOT IN (
                                  SELECT column_name FROM information_schema.columns
                                  WHERE table_schema = schema_name AND table_name = tmpl_table
                              )
                        LOOP
                            SELECT
                                format_type(a.atttypid, a.atttypmod),
                                pg_get_expr(ad.adbin, ad.adrelid),
                                a.attnotnull
                            INTO col_type, col_default, col_not_null
                            FROM pg_attribute a
                            LEFT JOIN pg_attrdef ad ON ad.adrelid = a.attrelid AND ad.adnum = a.attnum
                            WHERE a.attrelid = format('tenant_template.%I', tmpl_table)::regclass
                              AND a.attname = missing_col.column_name
                              AND a.attnum > 0
                              AND NOT a.attisdropped;

                            add_clause := format('ADD COLUMN IF NOT EXISTS %I %s', missing_col.column_name, col_type);
                            IF col_default IS NOT NULL THEN
                                add_clause := add_clause || format(' DEFAULT %s', col_default);
                            END IF;
                            IF col_not_null AND col_default IS NOT NULL THEN
                                add_clause := add_clause || ' NOT NULL';
                            END IF;

                            EXECUTE format('ALTER TABLE %I.%I %s', schema_name, tmpl_table, add_clause);
                        END LOOP;
                    END IF;
                END LOOP;
            END LOOP;
        END $$;
    """)


def downgrade() -> None:
    # Reconciliation only ever adds tables/columns that tenant_template already
    # declares. There is nothing to safely reverse: dropping them again would
    # destroy tenant data that pre-023 schemas were simply missing.
    pass
