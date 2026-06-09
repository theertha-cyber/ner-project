"""add document service columns to tenant_template schema

Revision ID: 003
Revises: 002
Create Date: 2026-06-09
"""
from alembic import op
import sqlalchemy as sa

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE tenant_template.documents
            ADD COLUMN IF NOT EXISTS content_type VARCHAR(255),
            ADD COLUMN IF NOT EXISTS file_size BIGINT,
            ADD COLUMN IF NOT EXISTS blob_path VARCHAR(500),
            ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW();
    """)

    op.execute("""
        ALTER TABLE tenant_template.document_text_spans
            ADD COLUMN IF NOT EXISTS span_index INTEGER,
            ADD COLUMN IF NOT EXISTS char_start INTEGER,
            ADD COLUMN IF NOT EXISTS char_end INTEGER,
            ADD COLUMN IF NOT EXISTS page_number INTEGER,
            ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW();
    """)

    op.execute("""
        ALTER TABLE public.tenants
            ADD COLUMN IF NOT EXISTS storage_used_bytes BIGINT DEFAULT 0;
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE public.tenants DROP COLUMN IF EXISTS storage_used_bytes")
    op.execute("ALTER TABLE tenant_template.document_text_spans DROP COLUMN IF EXISTS span_index")
    op.execute("ALTER TABLE tenant_template.document_text_spans DROP COLUMN IF EXISTS char_start")
    op.execute("ALTER TABLE tenant_template.document_text_spans DROP COLUMN IF EXISTS char_end")
    op.execute("ALTER TABLE tenant_template.document_text_spans DROP COLUMN IF EXISTS page_number")
    op.execute("ALTER TABLE tenant_template.document_text_spans DROP COLUMN IF EXISTS created_at")
    op.execute("ALTER TABLE tenant_template.documents DROP COLUMN IF EXISTS content_type")
    op.execute("ALTER TABLE tenant_template.documents DROP COLUMN IF EXISTS file_size")
    op.execute("ALTER TABLE tenant_template.documents DROP COLUMN IF EXISTS blob_path")
    op.execute("ALTER TABLE tenant_template.documents DROP COLUMN IF EXISTS updated_at")
