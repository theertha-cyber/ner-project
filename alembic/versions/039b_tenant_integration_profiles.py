"""create the per-tenant integration profile table in the control plane

ADR-001 puts tenant *content* in per-tenant schemas. A profile is not content: it is the
platform configuration that says which adapters serve a tenant, and the platform must be
able to read it precisely when that tenant's own infrastructure is unreachable. So it
lives in `public`.

The table holds secret *references* only. There is no column a credential value belongs
in, which is what makes "no raw secrets" a property of the schema rather than a rule
someone has to remember.

NOTE (renumbered 2026-09-15): this file was independently created as revision "039" (down_revision
"038") on a separate branch from `039_seed_bootstrap.py`, which also claimed "039" off the same
ambiguous "038" — `alembic history`/`upgrade` cannot resolve a revision ID that names two different
files. Both migrations' DDL was already applied to the shared dev database despite the ambiguity
(verified directly against `ner_dev` before this fix), so this is a pure bookkeeping renumbering,
not a schema repair. This file is renumbered to "039b" and re-chained after `039_seed_bootstrap.py`;
`040_confidence_routed_review.py`'s `down_revision` is updated from "039" to "039b" to match.

Revision ID: 039b
Revises: 039
Create Date: 2026-09-07
"""
from alembic import op

revision = "039b"
down_revision = "039"
branch_labels = None
depends_on = None

STATUSES = ("draft", "validated", "active", "paused", "error", "retired")
RETENTION_MODES = ("platform_blob", "ephemeral", "source_only")


def _quoted(values) -> str:
    return ", ".join(f"'{v}'" for v in values)


def upgrade() -> None:
    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS public.tenant_integration_profiles (
            tenant_id VARCHAR(64) PRIMARY KEY,
            source_adapter VARCHAR(64) NOT NULL DEFAULT 'platform_upload',
            content_store_adapter VARCHAR(64) NOT NULL DEFAULT 'platform_minio',
            relational_adapter VARCHAR(64) NOT NULL DEFAULT 'platform_postgresql',
            index_adapter VARCHAR(64) NOT NULL DEFAULT 'platform_pgvector',
            retention_mode VARCHAR(32) NOT NULL DEFAULT 'platform_blob'
                CHECK (retention_mode IN ({_quoted(RETENTION_MODES)})),
            -- Typed, allowlisted, non-secret configuration. Validated in the application
            -- against a closed per-adapter key set before it ever reaches this column.
            configuration JSONB NOT NULL DEFAULT '{{}}'::jsonb,
            -- References of the form <scheme>://<path>. Never values.
            secret_references JSONB NOT NULL DEFAULT '{{}}'::jsonb,
            status VARCHAR(32) NOT NULL DEFAULT 'draft'
                CHECK (status IN ({_quoted(STATUSES)})),
            -- Sanitised. Names a reference and a failure class, never credential material.
            status_reason TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )

    # Backfill one default profile per existing tenant, so no ingestion path has to cope
    # with a tenant that has no row. The defaults are exactly what the platform does today.
    op.execute(
        """
        INSERT INTO public.tenant_integration_profiles (tenant_id, status)
        SELECT id, 'active' FROM public.tenants
        ON CONFLICT (tenant_id) DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS public.tenant_integration_profiles")
