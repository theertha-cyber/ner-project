"""backfill analytics materialized views for tenant schemas created after 011

Revision ID: 015
Revises: 014
Create Date: 2026-07-06
"""
from alembic import op

revision = "015"
down_revision = "014"
branch_labels = None
depends_on = None


def upgrade() -> None:
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

                EXECUTE format('REFRESH MATERIALIZED VIEW CONCURRENTLY %I.mv_entity_coverage', schema_name);
                EXECUTE format('REFRESH MATERIALIZED VIEW CONCURRENTLY %I.mv_confidence_distribution', schema_name);
                EXECUTE format('REFRESH MATERIALIZED VIEW CONCURRENTLY %I.mv_extraction_volume', schema_name);
                EXECUTE format('REFRESH MATERIALIZED VIEW CONCURRENTLY %I.mv_document_entity_counts', schema_name);
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
                WHERE nspname LIKE 'tenant\_%' AND nspname != 'tenant_template'
            LOOP
                EXECUTE format('DROP MATERIALIZED VIEW IF EXISTS %I.mv_entity_coverage CASCADE', schema_name);
                EXECUTE format('DROP MATERIALIZED VIEW IF EXISTS %I.mv_confidence_distribution CASCADE', schema_name);
                EXECUTE format('DROP MATERIALIZED VIEW IF EXISTS %I.mv_extraction_volume CASCADE', schema_name);
                EXECUTE format('DROP MATERIALIZED VIEW IF EXISTS %I.mv_document_entity_counts CASCADE', schema_name);
            END LOOP;
        END $$;
    """)
