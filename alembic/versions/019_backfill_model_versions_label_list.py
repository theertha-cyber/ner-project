"""backfill label_list in model_versions.metrics for existing completed/promoted versions

Revision ID: 019
Revises: 018
Create Date: 2026-07-09
"""
from alembic import op

revision = "019"
down_revision = "018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        DO $$
        DECLARE
            schema_name TEXT;
            mv RECORD;
            computed_labels TEXT[];
        BEGIN
            FOR schema_name IN
                SELECT nspname FROM pg_namespace
                WHERE nspname LIKE 'tenant\\_%' AND nspname != 'tenant_template'
            LOOP
                FOR mv IN
                    EXECUTE format(
                        'SELECT id, tenant_id, metrics FROM %I.model_versions WHERE status IN (''completed'', ''promoted'')',
                        schema_name
                    )
                LOOP
                    IF mv.metrics IS NOT NULL AND mv.metrics ? 'label_list' THEN
                        CONTINUE;
                    END IF;

                    SELECT array_agg(tag ORDER BY tag) INTO computed_labels
                    FROM (
                        SELECT 'B-' || name AS tag FROM public.entity_definitions
                        WHERE tenant_id = mv.tenant_id AND is_active = true
                        UNION ALL
                        SELECT 'I-' || name FROM public.entity_definitions
                        WHERE tenant_id = mv.tenant_id AND is_active = true
                    ) t;

                    IF computed_labels IS NULL THEN
                        CONTINUE;
                    END IF;

                    EXECUTE format(
                        'UPDATE %I.model_versions SET metrics = COALESCE(metrics, ''{}''::jsonb) || jsonb_build_object(''label_list'', %L::jsonb) WHERE id = %L',
                        schema_name,
                        to_jsonb(array_prepend('O', computed_labels)),
                        mv.id
                    );
                END LOOP;
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
                SELECT nspname FROM pg_namespace
                WHERE nspname LIKE 'tenant\\_%' AND nspname != 'tenant_template'
            LOOP
                EXECUTE format(
                    'UPDATE %I.model_versions SET metrics = metrics - ''label_list'' WHERE metrics ? ''label_list''',
                    schema_name
                );
            END LOOP;
        END $$;
    """)
