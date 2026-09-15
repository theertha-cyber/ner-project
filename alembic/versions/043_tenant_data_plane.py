"""tenant data plane control plane: tenant_data_planes, tenant_document_registry,
platform_store_meta, azure_postgresql_data_plane provider (ADR-017)

Three additive control-plane pieces for `tenant-postgresql-data-plane`:

* `public.tenant_data_planes` — one row per tenant recording whether its schema lives
  on the platform database or a tenant-owned store, and that store's status. Every
  tenant existing before this migration is backfilled `platform` / `ready`. `mode` is
  made immutable by a trigger, not just an application check, because this table is the
  one thing the resolver trusts to never silently point a tenant at the wrong server.
* `public.tenant_document_registry` — a content-free per-document projection (id,
  tenant, source type, status, size, checksum, retention mode, timestamps) that exists
  for every tenant regardless of data plane, backfilled from each platform tenant
  schema's `documents` table. It carries no filename, storage reference, or text.
* `azure_postgresql_data_plane` added to the connections provider CHECK, and
  `platform_store_meta` (store identity + applied schema revision) added to
  `tenant_template` and every existing platform tenant schema, seeded with revision 1
  (the revision baseline.py reproduces as of this migration) and a fresh store id — a
  platform schema was never "provisioned" against a tenant store, but recording an
  identity now lets fleet code treat platform and tenant-owned schemas uniformly later.

Revision ID: 043
Revises: 042
Create Date: 2026-09-14
"""
from alembic import op

revision = "043"
down_revision = "042"
branch_labels = None
depends_on = None

DATA_PLANE_MODES = ("platform", "tenant_owned")
DATA_PLANE_STATUSES = (
    "awaiting_store",
    "provisioning",
    "provisioning_failed",
    "ready",
    "migration_required",
    "paused",
    "store_retired",
)
DATA_PLANE_HEALTH_OUTCOMES = ("healthy", "unreachable", "auth_failed", "timeout")
DATA_SOURCE_PROVIDERS = ("azure_blob", "azure_postgresql", "azure_postgresql_data_plane")

# The tenant-store schema revision this migration's tenant_template shape corresponds
# to. src/shared/tenant_store/baseline.py reproduces exactly this shape at revision 1;
# a later tenant-store revision bumps this only by adding a new src/shared/tenant_store/
# revisions/NNNN_*.py module, never by editing this constant.
BASELINE_SCHEMA_REVISION = 1


def _quoted(values) -> str:
    return ", ".join(f"'{v}'" for v in values)


def _for_each_platform_tenant_schema(statement: str) -> str:
    """Apply one statement to every provisioned platform tenant schema.

    `statement` is a `format()` template using `%I` for the schema; its own single
    quotes are doubled here because it is embedded in a PL/pgSQL string literal. Follows
    the 030/034/038 pattern.
    """
    embedded = statement.replace("'", "''")
    return f"""
        DO $$
        DECLARE
            schema_name TEXT;
        BEGIN
            FOR schema_name IN
                SELECT nspname FROM pg_namespace
                WHERE nspname LIKE 'tenant\\_%' AND nspname != 'tenant_template'
            LOOP
                EXECUTE format('{embedded}', schema_name);
            END LOOP;
        END $$;
    """


def upgrade() -> None:
    # --- tenant_data_planes -------------------------------------------------------
    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS public.tenant_data_planes (
            tenant_id VARCHAR(64) PRIMARY KEY
                REFERENCES public.tenants (id) ON DELETE CASCADE,
            mode VARCHAR(32) NOT NULL
                CHECK (mode IN ({_quoted(DATA_PLANE_MODES)})),
            status VARCHAR(32) NOT NULL
                CHECK (status IN ({_quoted(DATA_PLANE_STATUSES)})),
            connection_id UUID
                REFERENCES public.tenant_data_source_connections (id) ON DELETE SET NULL,
            store_id UUID,
            schema_revision INTEGER,
            -- Finite safe reason only. Never an endpoint, credential, or driver message.
            status_reason VARCHAR(64) NOT NULL DEFAULT 'none',
            health_outcome VARCHAR(32)
                CHECK (health_outcome IN ({_quoted(DATA_PLANE_HEALTH_OUTCOMES)})),
            health_checked_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.reject_tenant_data_plane_mode_change()
        RETURNS trigger AS $$
        BEGIN
            IF NEW.mode IS DISTINCT FROM OLD.mode THEN
                RAISE EXCEPTION 'DATA_PLANE_MODE_IMMUTABLE'
                    USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        "DROP TRIGGER IF EXISTS trg_tenant_data_plane_mode_immutable "
        "ON public.tenant_data_planes"
    )
    op.execute(
        """
        CREATE TRIGGER trg_tenant_data_plane_mode_immutable
        BEFORE UPDATE ON public.tenant_data_planes
        FOR EACH ROW EXECUTE FUNCTION public.reject_tenant_data_plane_mode_change()
        """
    )
    op.execute(
        """
        INSERT INTO public.tenant_data_planes (tenant_id, mode, status)
        SELECT id, 'platform', 'ready' FROM public.tenants
        ON CONFLICT (tenant_id) DO NOTHING
        """
    )

    # --- tenant_document_registry --------------------------------------------------
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS public.tenant_document_registry (
            document_id VARCHAR(64) NOT NULL,
            tenant_id VARCHAR(64) NOT NULL
                REFERENCES public.tenants (id) ON DELETE CASCADE,
            source_type VARCHAR(64) NOT NULL,
            status VARCHAR(20) NOT NULL,
            file_size_bytes BIGINT,
            checksum VARCHAR(64),
            retention_mode VARCHAR(32) NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (tenant_id, document_id)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_tenant_document_registry_tenant
            ON public.tenant_document_registry (tenant_id)
        """
    )
    op.execute(
        _for_each_platform_tenant_schema(
            """
            INSERT INTO public.tenant_document_registry
                (document_id, tenant_id, source_type, status, file_size_bytes,
                 checksum, retention_mode, created_at, updated_at)
            SELECT id, tenant_id, source_type, status,
                   COALESCE(file_size_bytes, file_size), checksum, retention_mode,
                   created_at, COALESCE(updated_at, created_at)
            FROM %I.documents
            ON CONFLICT (tenant_id, document_id) DO NOTHING
            """
        )
    )

    # --- azure_postgresql_data_plane provider --------------------------------------
    op.execute(
        "ALTER TABLE public.tenant_data_source_connections "
        "DROP CONSTRAINT IF EXISTS tenant_data_source_connections_provider_check"
    )
    op.execute(
        f"ALTER TABLE public.tenant_data_source_connections "
        f"ADD CONSTRAINT tenant_data_source_connections_provider_check "
        f"CHECK (provider IN ({_quoted(DATA_SOURCE_PROVIDERS)}))"
    )

    # --- platform_store_meta --------------------------------------------------------
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS tenant_template.platform_store_meta (
            store_id UUID NOT NULL,
            tenant_id VARCHAR(64) NOT NULL,
            schema_revision INTEGER NOT NULL,
            provisioned_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        f"""
        DO $$
        DECLARE
            schema_name TEXT;
            tid TEXT;
        BEGIN
            FOR schema_name IN
                SELECT nspname FROM pg_namespace
                WHERE nspname LIKE 'tenant\\_%' AND nspname != 'tenant_template'
            LOOP
                EXECUTE format(
                    'CREATE TABLE IF NOT EXISTS %I.platform_store_meta ('
                    '  store_id UUID NOT NULL,'
                    '  tenant_id VARCHAR(64) NOT NULL,'
                    '  schema_revision INTEGER NOT NULL,'
                    '  provisioned_at TIMESTAMPTZ NOT NULL DEFAULT NOW()'
                    ')',
                    schema_name
                );
                tid := substring(schema_name FROM 8);
                EXECUTE format(
                    'INSERT INTO %I.platform_store_meta '
                    '  (store_id, tenant_id, schema_revision) '
                    'SELECT gen_random_uuid(), %L, {BASELINE_SCHEMA_REVISION} '
                    'WHERE NOT EXISTS (SELECT 1 FROM %I.platform_store_meta)',
                    schema_name, tid, schema_name
                );
            END LOOP;
        END $$;
        """
    )
    op.execute(
        f"""
        UPDATE public.tenant_data_planes
        SET schema_revision = {BASELINE_SCHEMA_REVISION}
        WHERE mode = 'platform'
        """
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE public.tenant_data_source_connections "
        "DROP CONSTRAINT IF EXISTS tenant_data_source_connections_provider_check"
    )
    op.execute(
        "ALTER TABLE public.tenant_data_source_connections "
        "ADD CONSTRAINT tenant_data_source_connections_provider_check "
        "CHECK (provider IN ('azure_blob', 'azure_postgresql'))"
    )
    op.execute("DROP TABLE IF EXISTS public.tenant_document_registry")
    op.execute(
        "DROP TRIGGER IF EXISTS trg_tenant_data_plane_mode_immutable "
        "ON public.tenant_data_planes"
    )
    op.execute("DROP TABLE IF EXISTS public.tenant_data_planes")
    op.execute("DROP FUNCTION IF EXISTS public.reject_tenant_data_plane_mode_change()")
    # platform_store_meta is left in place on downgrade: it is additive-only bookkeeping
    # (ADR-014) that later revisions and migrate.py depend on existing going forward.
