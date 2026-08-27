"""processing mode and post-processor provenance on extraction_runs

A batch run must record which processing mode it actually ran under, and which
post-processor produced any changes, so a quality shift is traceable to a prompt or
model revision rather than guessed at. `processing_mode` defaults to `bert_only`, which
is what every pre-existing run really was.

`postprocess_degraded` marks a run that completed with post-processing partially or
wholly unavailable — the fail-open path persists the deterministic extraction and marks
the run rather than failing it, so without this column a degraded run would be
indistinguishable from a clean one.

Revision ID: 036
Revises: 035
Create Date: 2026-08-14
"""
from alembic import op

revision = "036"
down_revision = "035"
branch_labels = None
depends_on = None

_ADD_COLUMNS = """
    ALTER TABLE {schema}.extraction_runs
        ADD COLUMN IF NOT EXISTS processing_mode VARCHAR(32) NOT NULL DEFAULT 'bert_only',
        ADD COLUMN IF NOT EXISTS postprocess_model TEXT,
        ADD COLUMN IF NOT EXISTS postprocess_prompt_version TEXT,
        ADD COLUMN IF NOT EXISTS postprocess_degraded BOOLEAN NOT NULL DEFAULT FALSE
"""

_DROP_COLUMNS = """
    ALTER TABLE {schema}.extraction_runs
        DROP COLUMN IF EXISTS processing_mode,
        DROP COLUMN IF EXISTS postprocess_model,
        DROP COLUMN IF EXISTS postprocess_prompt_version,
        DROP COLUMN IF EXISTS postprocess_degraded
"""


def upgrade() -> None:
    op.execute(_ADD_COLUMNS.format(schema="tenant_template"))

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
                    WHERE table_schema = schema_name AND table_name = 'extraction_runs'
                ) THEN
                    EXECUTE format('
                        ALTER TABLE %I.extraction_runs
                            ADD COLUMN IF NOT EXISTS processing_mode VARCHAR(32) NOT NULL DEFAULT ''bert_only'',
                            ADD COLUMN IF NOT EXISTS postprocess_model TEXT,
                            ADD COLUMN IF NOT EXISTS postprocess_prompt_version TEXT,
                            ADD COLUMN IF NOT EXISTS postprocess_degraded BOOLEAN NOT NULL DEFAULT FALSE
                    ', schema_name);
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
                    WHERE table_schema = schema_name AND table_name = 'extraction_runs'
                ) THEN
                    EXECUTE format('
                        ALTER TABLE %I.extraction_runs
                            DROP COLUMN IF EXISTS processing_mode,
                            DROP COLUMN IF EXISTS postprocess_model,
                            DROP COLUMN IF EXISTS postprocess_prompt_version,
                            DROP COLUMN IF EXISTS postprocess_degraded
                    ', schema_name);
                END IF;
            END LOOP;
        END $$;
    """)
    op.execute(_DROP_COLUMNS.format(schema="tenant_template"))
