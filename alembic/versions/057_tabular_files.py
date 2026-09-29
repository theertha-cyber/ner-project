"""uploaded tabular files control plane (ADR-018, ADR-019)

Two platform-only control-plane tables for tenant-uploaded CSV/XLSX files. A file
row carries the served-version pointer; each re-upload is a version row with its
own profile, review, load report and published contract. Objects live in platform
MinIO under `tenants/{tenant_id}/tabular/{file_id}/v{n}/` for every tenant,
whatever its residency mode (ADR-019) — so, unlike 056, nothing here ships to
`tenant_owned` stores: capability resolution reads these tables through a
platform session only (Design D10).

Revision ID: 057
Revises: 056
Create Date: 2026-09-23
"""
from alembic import op

revision = "057"
down_revision = "056"
branch_labels = None
depends_on = None

FILE_STATUSES = ("profiling", "needs_review", "publishing", "ready", "failed", "deleted")
VERSION_STATUSES = ("profiling", "needs_review", "publishing", "ready", "failed", "superseded", "deleted")
SOURCE_KINDS = ("csv", "xlsx")


def _quoted(values) -> str:
    return ", ".join(f"'{v}'" for v in values)


def upgrade() -> None:
    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS public.tabular_files (
            id UUID PRIMARY KEY,
            tenant_id VARCHAR(64) NOT NULL,
            display_name VARCHAR(255) NOT NULL,
            -- The version chat reads. NULL until the first publish succeeds.
            served_version INTEGER,
            status VARCHAR(32) NOT NULL DEFAULT 'profiling'
                CHECK (status IN ({_quoted(FILE_STATUSES)})),
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            deleted_at TIMESTAMPTZ
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_tabular_files_tenant
            ON public.tabular_files (tenant_id)
        """
    )
    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS public.tabular_file_versions (
            file_id UUID NOT NULL REFERENCES public.tabular_files (id) ON DELETE CASCADE,
            version INTEGER NOT NULL,
            tenant_id VARCHAR(64) NOT NULL,
            status VARCHAR(32) NOT NULL DEFAULT 'profiling'
                CHECK (status IN ({_quoted(VERSION_STATUSES)})),
            -- Finite reason class on `failed` (e.g. ROW_LIMIT_EXCEEDED). Never
            -- parser diagnostics or cell contents.
            failure_reason VARCHAR(64),
            source_kind VARCHAR(16) NOT NULL
                CHECK (source_kind IN ({_quoted(SOURCE_KINDS)})),
            source_filename VARCHAR(255) NOT NULL,
            sheet VARCHAR(255),
            original_key TEXT NOT NULL,
            parquet_key TEXT,
            profile JSONB,
            review JSONB,
            load_report JSONB,
            contract JSONB,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            published_at TIMESTAMPTZ,
            PRIMARY KEY (file_id, version)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_tabular_file_versions_tenant
            ON public.tabular_file_versions (tenant_id)
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS public.tabular_file_versions")
    op.execute("DROP TABLE IF EXISTS public.tabular_files")
