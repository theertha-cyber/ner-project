"""create audit_events table for audit log feature

Revision ID: 020
Revises: 019
Create Date: 2026-07-14
"""
from alembic import op
import sqlalchemy as sa

revision = "020"
down_revision = "019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS public")

    op.create_table(
        "audit_events",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("actor", sa.String(255), nullable=False),
        sa.Column("role", sa.String(50), nullable=False),
        sa.Column("action", sa.String(255), nullable=False),
        sa.Column("target", sa.String(255), nullable=False),
        sa.Column(
            "kind",
            sa.Enum(
                "create", "approve", "promote", "complete",
                "run", "reject", "update",
                name="auditeventkind",
                create_type=True,
            ),
            nullable=False,
        ),
        sa.Column("tenant_id", sa.String(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["public.tenants.id"],
            name="fk_audit_events_tenant_id",
        ),
        sa.PrimaryKeyConstraint("id"),
        schema="public",
    )

    op.create_index(
        "ix_audit_events_created_at_desc",
        "audit_events",
        ["created_at"],
        schema="public",
        postgresql_using="btree",
    )


def downgrade() -> None:
    op.drop_table("audit_events", schema="public")
    op.execute("DROP TYPE IF EXISTS auditeventkind")
