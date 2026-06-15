"""add annotation service tables to tenant_template schema

Revision ID: 004
Revises: 003
Create Date: 2026-06-09
"""
from alembic import op
import sqlalchemy as sa

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE tenant_template.annotation_tasks
            ADD COLUMN IF NOT EXISTS annotator_user_id VARCHAR,
            ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ,
            ALTER COLUMN status SET DEFAULT 'unannotated';
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS tenant_template.spans (
            id VARCHAR PRIMARY KEY,
            document_id VARCHAR NOT NULL REFERENCES tenant_template.documents(id) ON DELETE CASCADE,
            entity_type VARCHAR(255) NOT NULL,
            char_start INTEGER NOT NULL,
            char_end INTEGER NOT NULL,
            text_content VARCHAR NOT NULL,
            confidence FLOAT NOT NULL DEFAULT 1.0,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ
        );
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS tenant_template.suggested_spans (
            id VARCHAR PRIMARY KEY,
            document_id VARCHAR NOT NULL REFERENCES tenant_template.documents(id) ON DELETE CASCADE,
            entity_type VARCHAR(255) NOT NULL,
            char_start INTEGER NOT NULL,
            char_end INTEGER NOT NULL,
            text_content VARCHAR NOT NULL,
            confidence FLOAT NOT NULL,
            created_at TIMESTAMPTZ DEFAULT NOW()
        );
    """)

    op.execute("""
        DROP INDEX IF EXISTS idx_task_active_document;
        CREATE UNIQUE INDEX IF NOT EXISTS idx_task_active_document
            ON tenant_template.annotation_tasks (document_id)
            WHERE status IN ('unannotated', 'in-progress');
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_task_active_document")
    op.execute("DROP TABLE IF EXISTS tenant_template.suggested_spans")
    op.execute("DROP TABLE IF EXISTS tenant_template.spans")
    op.execute("ALTER TABLE tenant_template.annotation_tasks DROP COLUMN IF EXISTS annotator_user_id")
    op.execute("ALTER TABLE tenant_template.annotation_tasks DROP COLUMN IF EXISTS updated_at")
