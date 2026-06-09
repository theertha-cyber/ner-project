"""initial schema: tenants, tenant_users, entity_definitions in public schema

Revision ID: 001
Revises:
Create Date: 2026-06-05
"""
from alembic import op
import sqlalchemy as sa

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS public")

    op.create_table(
        "tenants",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(63), nullable=False),
        sa.Column("status", sa.String(20), server_default="active", nullable=False),
        sa.Column("max_users", sa.Integer(), server_default="10", nullable=False),
        sa.Column("max_documents", sa.Integer(), server_default="1000", nullable=False),
        sa.Column("max_storage_gb", sa.Integer(), server_default="5", nullable=False),
        sa.Column("max_model_versions", sa.Integer(), server_default="10", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
        schema="public",
    )
    op.create_index("ix_tenants_slug", "tenants", ["slug"], schema="public")

    op.create_table(
        "tenant_users",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role",
                  sa.Enum("system_admin", "tenant_admin", "business_user", "annotator",
                          name="user_role"),
                  nullable=False),
        sa.Column("status", sa.String(20), server_default="active", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["tenant_id"], ["public.tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email", "tenant_id", name="uq_email_per_tenant"),
        schema="public",
    )

    op.create_table(
        "entity_definitions",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("examples", sa.JSON(), nullable=True),
        sa.Column("validation_rule", sa.String(500), nullable=True),
        sa.Column("target_table", sa.String(255), nullable=True),
        sa.Column("base_label_mapping", sa.JSON(), nullable=True),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("required_flag", sa.Boolean(), server_default="false"),
        sa.Column("is_active", sa.Boolean(), server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["tenant_id"], ["public.tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        schema="public",
    )


def downgrade() -> None:
    op.drop_table("entity_definitions", schema="public")
    op.drop_table("tenant_users", schema="public")
    op.drop_table("tenants", schema="public")
    op.execute("DROP TYPE IF EXISTS user_role")
