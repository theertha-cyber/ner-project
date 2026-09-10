"""tenant-admin azure connection control plane (CAP-2)

ADR-011 extends the public tenant-bound control plane with lifecycle records for only
Azure Blob Storage and Azure Database for PostgreSQL. These tables hold non-sensitive
metadata, secret *references*, and finite safe lifecycle/test/activation evidence.
There is no column a credential value, endpoint, provider diagnostic, or tenant
content belongs in.

Revision ID: 040
Revises: 039
Create Date: 2026-09-10
"""
from alembic import op

revision = "040"
down_revision = "039"
branch_labels = None
depends_on = None

PROVIDERS = ("azure_blob", "azure_postgresql")
STATUSES = ("draft", "validated", "active", "paused", "error", "retired")


def _quoted(values) -> str:
    return ", ".join(f"'{v}'" for v in values)


def upgrade() -> None:
    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS public.tenant_data_source_connections (
            id UUID PRIMARY KEY,
            tenant_id VARCHAR(64) NOT NULL,
            provider VARCHAR(32) NOT NULL
                CHECK (provider IN ({_quoted(PROVIDERS)})),
            -- Typed, allowlisted, non-secret configuration. Validated in the
            -- application against a closed per-provider key set before it reaches
            -- this column. Only field *names* are ever read back out.
            configuration JSONB NOT NULL DEFAULT '{{}}'::jsonb,
            -- References of the form <scheme>://<path>. Never values.
            secret_references JSONB NOT NULL DEFAULT '{{}}'::jsonb,
            status VARCHAR(32) NOT NULL DEFAULT 'draft'
                CHECK (status IN ({_quoted(STATUSES)})),
            -- Finite safe lifecycle/test/activation evidence. Outcome and reason
            -- classes only, plus correlation timestamps. Never endpoints,
            -- provider errors, credentials, or tenant content.
            last_test_outcome VARCHAR(32) NOT NULL DEFAULT 'not_run',
            last_test_reason VARCHAR(64) NOT NULL DEFAULT 'none',
            last_test_at TIMESTAMPTZ,
            test_config_digest VARCHAR(64),
            activation_outcome VARCHAR(32) NOT NULL DEFAULT 'inactive',
            activation_reason VARCHAR(64) NOT NULL DEFAULT 'none',
            activated_at TIMESTAMPTZ,
            activation_evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
            replaces_connection_id UUID
                REFERENCES public.tenant_data_source_connections (id)
                ON DELETE SET NULL,
            replaced_by_connection_id UUID
                REFERENCES public.tenant_data_source_connections (id)
                ON DELETE SET NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    # One active connection per (tenant, provider): the atomic concurrent-limit
    # enforcement ADR-011 requires. The application maps an attempted second
    # activation to ACTIVE_PROVIDER_EXISTS; the constraint makes the race safe.
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_data_source_active_provider
            ON public.tenant_data_source_connections (tenant_id, provider)
            WHERE status = 'active'
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_data_source_connections_tenant
            ON public.tenant_data_source_connections (tenant_id)
        """
    )

    # Tenant/method/path/key-scoped idempotency records with a 24-hour replay
    # window. Only the body digest and the replayable *safe* response are stored.
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS public.tenant_data_source_idempotency (
            tenant_id VARCHAR(64) NOT NULL,
            method VARCHAR(16) NOT NULL,
            path TEXT NOT NULL,
            idempotency_key VARCHAR(128) NOT NULL,
            body_digest VARCHAR(64) NOT NULL,
            response_status INTEGER NOT NULL,
            response_body JSONB NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (tenant_id, method, path, idempotency_key)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_data_source_idempotency_created
            ON public.tenant_data_source_idempotency (created_at)
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS public.tenant_data_source_idempotency")
    op.execute("DROP TABLE IF EXISTS public.tenant_data_source_connections")
