"""create analytics materialized views

Revision ID: 011
Revises: 010
Create Date: 2026-06-24
"""
from alembic import op

revision = "011"
down_revision = "010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE MATERIALIZED VIEW IF NOT EXISTS tenant_template.mv_entity_coverage AS
        SELECT
            e.entity_id AS entity_type,
            COUNT(DISTINCT e.document_id)::float / NULLIF(COUNT(DISTINCT d.id), 0) * 100 AS coverage_pct
        FROM tenant_template.extracted_entities e
        CROSS JOIN tenant_template.documents d
        GROUP BY e.entity_id
        WITH DATA
    """)

    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_entity_coverage_type
        ON tenant_template.mv_entity_coverage (entity_type)
    """)

    op.execute("""
        CREATE MATERIALIZED VIEW IF NOT EXISTS tenant_template.mv_confidence_distribution AS
        SELECT
            CASE
                WHEN confidence >= 0.0 AND confidence < 0.2 THEN '0.0-0.2'
                WHEN confidence >= 0.2 AND confidence < 0.4 THEN '0.2-0.4'
                WHEN confidence >= 0.4 AND confidence < 0.6 THEN '0.4-0.6'
                WHEN confidence >= 0.6 AND confidence < 0.8 THEN '0.6-0.8'
                WHEN confidence >= 0.8 AND confidence <= 1.0 THEN '0.8-1.0'
            END AS bucket,
            COUNT(*) AS count
        FROM tenant_template.extracted_entities
        GROUP BY bucket
        ORDER BY bucket
        WITH DATA
    """)

    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_confidence_distribution_bucket
        ON tenant_template.mv_confidence_distribution (bucket)
    """)

    op.execute("""
        CREATE MATERIALIZED VIEW IF NOT EXISTS tenant_template.mv_extraction_volume AS
        SELECT
            DATE(r.started_at) AS extraction_date,
            COUNT(*) AS count
        FROM tenant_template.extracted_entities e
        JOIN tenant_template.extraction_runs r ON r.id = e.run_id
        WHERE r.started_at >= NOW() - INTERVAL '30 days'
        GROUP BY DATE(r.started_at)
        ORDER BY extraction_date
        WITH DATA
    """)

    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_extraction_volume_date
        ON tenant_template.mv_extraction_volume (extraction_date)
    """)

    op.execute("""
        CREATE MATERIALIZED VIEW IF NOT EXISTS tenant_template.mv_document_entity_counts AS
        SELECT
            e.entity_id AS entity_type,
            AVG(entity_count)::float AS avg_per_document
        FROM (
            SELECT entity_id, document_id, COUNT(*) AS entity_count
            FROM tenant_template.extracted_entities
            GROUP BY entity_id, document_id
        ) e
        GROUP BY e.entity_id
        WITH DATA
    """)

    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_document_entity_counts_type
        ON tenant_template.mv_document_entity_counts (entity_type)
    """)

    op.execute("""
        DO $$
        DECLARE
            schema_name TEXT;
        BEGIN
            FOR schema_name IN
                SELECT nspname FROM pg_namespace
                WHERE nspname LIKE 'tenant\_%' AND nspname != 'tenant_template'
            LOOP
                EXECUTE format('
                    CREATE MATERIALIZED VIEW IF NOT EXISTS %I.mv_entity_coverage AS
                    SELECT
                        e.entity_id AS entity_type,
                        COUNT(DISTINCT e.document_id)::float / NULLIF(COUNT(DISTINCT d.id), 0) * 100 AS coverage_pct
                    FROM %I.extracted_entities e
                    CROSS JOIN %I.documents d
                    GROUP BY e.entity_id
                    WITH DATA
                ', schema_name, schema_name, schema_name);

                EXECUTE format('
                    CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_entity_coverage_type
                    ON %I.mv_entity_coverage (entity_type)
                ', schema_name);

                EXECUTE format('
                    CREATE MATERIALIZED VIEW IF NOT EXISTS %I.mv_confidence_distribution AS
                    SELECT
                        CASE
                            WHEN confidence >= 0.0 AND confidence < 0.2 THEN ''0.0-0.2''
                            WHEN confidence >= 0.2 AND confidence < 0.4 THEN ''0.2-0.4''
                            WHEN confidence >= 0.4 AND confidence < 0.6 THEN ''0.4-0.6''
                            WHEN confidence >= 0.6 AND confidence < 0.8 THEN ''0.6-0.8''
                            WHEN confidence >= 0.8 AND confidence <= 1.0 THEN ''0.8-1.0''
                        END AS bucket,
                        COUNT(*) AS count
                    FROM %I.extracted_entities
                    GROUP BY bucket
                    ORDER BY bucket
                    WITH DATA
                ', schema_name, schema_name);

                EXECUTE format('
                    CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_confidence_distribution_bucket
                    ON %I.mv_confidence_distribution (bucket)
                ', schema_name);

                EXECUTE format('
                    CREATE MATERIALIZED VIEW IF NOT EXISTS %I.mv_extraction_volume AS
                    SELECT
                        DATE(r.started_at) AS extraction_date,
                        COUNT(*) AS count
                    FROM %I.extracted_entities e
                    JOIN %I.extraction_runs r ON r.id = e.run_id
                    WHERE r.started_at >= NOW() - INTERVAL ''30 days''
                    GROUP BY DATE(r.started_at)
                    ORDER BY extraction_date
                    WITH DATA
                ', schema_name, schema_name, schema_name);

                EXECUTE format('
                    CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_extraction_volume_date
                    ON %I.mv_extraction_volume (extraction_date)
                ', schema_name);

                EXECUTE format('
                    CREATE MATERIALIZED VIEW IF NOT EXISTS %I.mv_document_entity_counts AS
                    SELECT
                        e.entity_id AS entity_type,
                        AVG(entity_count)::float AS avg_per_document
                    FROM (
                        SELECT entity_id, document_id, COUNT(*) AS entity_count
                        FROM %I.extracted_entities
                        GROUP BY entity_id, document_id
                    ) e
                    GROUP BY e.entity_id
                    WITH DATA
                ', schema_name, schema_name);

                EXECUTE format('
                    CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_document_entity_counts_type
                    ON %I.mv_document_entity_counts (entity_type)
                ', schema_name);
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
                WHERE nspname LIKE 'tenant\_%'
            LOOP
                EXECUTE format('DROP MATERIALIZED VIEW IF EXISTS %I.mv_entity_coverage CASCADE', schema_name);
                EXECUTE format('DROP MATERIALIZED VIEW IF EXISTS %I.mv_confidence_distribution CASCADE', schema_name);
                EXECUTE format('DROP MATERIALIZED VIEW IF EXISTS %I.mv_extraction_volume CASCADE', schema_name);
                EXECUTE format('DROP MATERIALIZED VIEW IF EXISTS %I.mv_document_entity_counts CASCADE', schema_name);
            END LOOP;
        END $$;
    """)

    op.execute("DROP MATERIALIZED VIEW IF EXISTS tenant_template.mv_entity_coverage CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS tenant_template.mv_confidence_distribution CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS tenant_template.mv_extraction_volume CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS tenant_template.mv_document_entity_counts CASCADE")
