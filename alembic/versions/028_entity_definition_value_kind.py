"""semantic value kind configuration on entity definitions

Revision ID: 028
Revises: 027
Create Date: 2026-07-31
"""
from alembic import op
import sqlalchemy as sa

revision = "028"
down_revision = "027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE public.entity_definitions ADD COLUMN IF NOT EXISTS value_kind VARCHAR(32)")
    op.execute("ALTER TABLE public.entity_definitions ADD COLUMN IF NOT EXISTS value_unit VARCHAR(32)")


def downgrade() -> None:
    op.execute("ALTER TABLE public.entity_definitions DROP COLUMN IF EXISTS value_unit")
    op.execute("ALTER TABLE public.entity_definitions DROP COLUMN IF EXISTS value_kind")
