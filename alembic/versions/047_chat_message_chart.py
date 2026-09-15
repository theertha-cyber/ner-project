"""chat_messages.chart — the chart rendered alongside an assistant answer

Revision ID: 047
Revises: 046
Create Date: 2026-09-15

When the generation model proposes a chart and its numbers are validated against the
turn's retrieved rows, the chart is delivered with the answer and must survive reload
of the conversation. Stored as JSONB beside `sources`, which sets the precedent for a
structured payload hanging off a chat message. Nullable with no backfill: every row
written before this column, and every turn that produces no chart, reads back as
chart-less, which is correct (chat-chart-generation design.md Decision 5).
"""
from alembic import op
from tenant_schema_ddl import apply_to_all_tenant_schemas

revision = "047"
down_revision = "046"
branch_labels = None
depends_on = None


def upgrade() -> None:
    apply_to_all_tenant_schemas(
        op,
        "ALTER TABLE {schema}.chat_messages ADD COLUMN IF NOT EXISTS chart JSONB NULL",
    )


def downgrade() -> None:
    apply_to_all_tenant_schemas(
        op,
        "ALTER TABLE {schema}.chat_messages DROP COLUMN IF EXISTS chart",
    )
