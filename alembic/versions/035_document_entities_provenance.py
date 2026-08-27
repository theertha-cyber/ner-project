"""extraction provenance columns on document_entities

Adds the minimum set needed to answer "what did BERT originally extract?" and "what
exactly did the post-processor change?" without a sidecar table — every column is
nullable or defaulted, so existing readers (which all use explicit SELECT lists) are
untouched. `source_entity_value` / `source_entity_type` are populated only when a value
or type actually changed, so the table does not double for the majority of rows nothing
touches.

`extraction_schema_version` marks which pipeline produced a row. Rows written before
the confidence-calibration fix hold raw logits in `confidence`; those cannot be
converted to probabilities after the fact (the logit vector is gone), so they are left
alone and confidence-gated logic ignores anything not marked calibrated.

Revision ID: 035
Revises: 034
Create Date: 2026-08-14
"""
from alembic import op

revision = "035"
down_revision = "034"
branch_labels = None
depends_on = None

# Schema version of the pre-change pipeline: uncalibrated confidence, no punctuation
# trimming, no validity gate, one row per mention.
LEGACY_SCHEMA_VERSION = 1

_ADD_COLUMNS = """
    ALTER TABLE {schema}.document_entities
        ADD COLUMN IF NOT EXISTS source_entity_value TEXT,
        ADD COLUMN IF NOT EXISTS source_entity_type TEXT,
        ADD COLUMN IF NOT EXISTS postprocess_status TEXT NOT NULL DEFAULT 'not_applied',
        ADD COLUMN IF NOT EXISTS postprocess_model TEXT,
        ADD COLUMN IF NOT EXISTS postprocess_prompt_version TEXT,
        ADD COLUMN IF NOT EXISTS postprocess_at TIMESTAMP WITH TIME ZONE,
        ADD COLUMN IF NOT EXISTS extraction_schema_version INTEGER NOT NULL DEFAULT 1,
        ADD COLUMN IF NOT EXISTS occurrence_count INTEGER NOT NULL DEFAULT 1
"""

_ADD_INDEX = (
    "CREATE INDEX IF NOT EXISTS idx_{suffix}_postprocess_status "
    "ON {schema}.document_entities (postprocess_status) "
    "WHERE postprocess_status <> 'not_applied'"
)

_DROP_COLUMNS = """
    ALTER TABLE {schema}.document_entities
        DROP COLUMN IF EXISTS source_entity_value,
        DROP COLUMN IF EXISTS source_entity_type,
        DROP COLUMN IF EXISTS postprocess_status,
        DROP COLUMN IF EXISTS postprocess_model,
        DROP COLUMN IF EXISTS postprocess_prompt_version,
        DROP COLUMN IF EXISTS postprocess_at,
        DROP COLUMN IF EXISTS extraction_schema_version,
        DROP COLUMN IF EXISTS occurrence_count
"""


def upgrade() -> None:
    op.execute(_ADD_COLUMNS.format(schema="tenant_template"))
    op.execute(_ADD_INDEX.format(schema="tenant_template", suffix="document_entities_template"))

    # Existing tenant schemas are walked rather than listed, and a schema without the
    # table is skipped instead of aborting the run — a tenant provisioned before
    # `document_entities` existed must not block the migration for everyone else.
    op.execute(r"""
        DO $$
        DECLARE
            schema_name TEXT;
        BEGIN
            FOR schema_name IN
                SELECT nspname FROM pg_namespace
                WHERE nspname LIKE 'tenant\_%' AND nspname != 'tenant_template'
            LOOP
                IF EXISTS (
                    SELECT 1 FROM information_schema.tables
                    WHERE table_schema = schema_name AND table_name = 'document_entities'
                ) THEN
                    EXECUTE format('
                        ALTER TABLE %I.document_entities
                            ADD COLUMN IF NOT EXISTS source_entity_value TEXT,
                            ADD COLUMN IF NOT EXISTS source_entity_type TEXT,
                            ADD COLUMN IF NOT EXISTS postprocess_status TEXT NOT NULL DEFAULT ''not_applied'',
                            ADD COLUMN IF NOT EXISTS postprocess_model TEXT,
                            ADD COLUMN IF NOT EXISTS postprocess_prompt_version TEXT,
                            ADD COLUMN IF NOT EXISTS postprocess_at TIMESTAMP WITH TIME ZONE,
                            ADD COLUMN IF NOT EXISTS extraction_schema_version INTEGER NOT NULL DEFAULT 1,
                            ADD COLUMN IF NOT EXISTS occurrence_count INTEGER NOT NULL DEFAULT 1
                    ', schema_name);
                    EXECUTE format('
                        CREATE INDEX IF NOT EXISTS idx_%s_postprocess_status ON %I.document_entities (postprocess_status) WHERE postprocess_status <> ''not_applied''
                    ', schema_name, schema_name);
                END IF;
            END LOOP;
        END $$;
    """)


def downgrade() -> None:
    op.execute(r"""
        DO $$
        DECLARE
            schema_name TEXT;
        BEGIN
            FOR schema_name IN
                SELECT nspname FROM pg_namespace
                WHERE nspname LIKE 'tenant\_%' AND nspname != 'tenant_template'
            LOOP
                IF EXISTS (
                    SELECT 1 FROM information_schema.tables
                    WHERE table_schema = schema_name AND table_name = 'document_entities'
                ) THEN
                    EXECUTE format('
                        ALTER TABLE %I.document_entities
                            DROP COLUMN IF EXISTS source_entity_value,
                            DROP COLUMN IF EXISTS source_entity_type,
                            DROP COLUMN IF EXISTS postprocess_status,
                            DROP COLUMN IF EXISTS postprocess_model,
                            DROP COLUMN IF EXISTS postprocess_prompt_version,
                            DROP COLUMN IF EXISTS postprocess_at,
                            DROP COLUMN IF EXISTS extraction_schema_version,
                            DROP COLUMN IF EXISTS occurrence_count
                    ', schema_name);
                END IF;
            END LOOP;
        END $$;
    """)
    op.execute(_DROP_COLUMNS.format(schema="tenant_template"))
