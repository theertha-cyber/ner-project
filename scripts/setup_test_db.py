"""Create extraction service tables in ner_test database."""
import asyncio
import os
import sys
from urllib.parse import urlparse
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

DATABASE_URL = os.environ.get("NER_DATABASE_URL", "postgresql+asyncpg://ner:ner@localhost:55432/ner_test")

ALLOW_NONSTANDARD_TEST_DB_ENV = "NER_ALLOW_NONSTANDARD_TEST_DB"


def _assert_test_database(url: str) -> None:
    db_name = urlparse(url).path.lstrip("/")
    if db_name.endswith("_test"):
        return

    override = os.environ.get(ALLOW_NONSTANDARD_TEST_DB_ENV, "").lower() in ("1", "true", "yes")
    if override:
        print(
            f"WARNING: '{db_name}' does not end in '_test', but "
            f"{ALLOW_NONSTANDARD_TEST_DB_ENV} is set — proceeding anyway.",
            file=sys.stderr,
        )
        return

    print(
        f"Refusing to run against database '{db_name}' — its name doesn't end in "
        "'_test'. This script creates and mutates fixture schemas and tenant rows; "
        "pointing it at a real dev/prod database will corrupt it. Set NER_DATABASE_URL "
        f"to a database whose name ends in '_test', or set {ALLOW_NONSTANDARD_TEST_DB_ENV}=1 "
        "to override for a deliberately non-standard test database name.",
        file=sys.stderr,
    )
    sys.exit(1)

SCHEMAS = [
    "tenant_test_tenant",
    "tenant_tenant_b",
    "tenant_no_model",
    "tenant_no_model_tenant",
]

TABLES = [
    """
    CREATE TABLE IF NOT EXISTS "{schema}".extraction_runs (
        id VARCHAR PRIMARY KEY,
        tenant_id VARCHAR NOT NULL,
        document_id VARCHAR,
        model_version VARCHAR,
        status VARCHAR NOT NULL DEFAULT 'queued',
        started_at TIMESTAMP WITH TIME ZONE NOT NULL,
        completed_at TIMESTAMP WITH TIME ZONE,
        total_documents INTEGER NOT NULL DEFAULT 0,
        processed_count INTEGER NOT NULL DEFAULT 0,
        skipped_count INTEGER NOT NULL DEFAULT 0,
        failed_count INTEGER NOT NULL DEFAULT 0,
        processing_mode VARCHAR(32) NOT NULL DEFAULT 'bert_only',
        postprocess_model TEXT,
        postprocess_prompt_version TEXT,
        postprocess_degraded BOOLEAN NOT NULL DEFAULT FALSE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS "{schema}".extracted_entities (
        id VARCHAR PRIMARY KEY,
        run_id VARCHAR NOT NULL,
        entity_id VARCHAR NOT NULL,
        value VARCHAR NOT NULL,
        confidence FLOAT NOT NULL,
        normalized_value VARCHAR,
        source_span_id VARCHAR,
        review_status VARCHAR NOT NULL DEFAULT 'unreviewed',
        corrected_value VARCHAR,
        corrected_by VARCHAR,
        correction_notes VARCHAR,
        document_id VARCHAR
    )
    """,
    # CAP-3 durable Blob sync ledger (alembic 041). Test-only mirror: the suite
    # runs DDL, not alembic, so the tables the migration creates are restated
    # here. Opaque source identity, version tokens, finite outcome classes, and
    # document linkage only.
    """
    CREATE TABLE IF NOT EXISTS "{schema}".azure_blob_sync_runs (
        id VARCHAR PRIMARY KEY,
        tenant_id VARCHAR(64) NOT NULL,
        connection_id VARCHAR NOT NULL,
        trigger VARCHAR(32) NOT NULL,
        outcome VARCHAR(32) NOT NULL DEFAULT 'started',
        reason VARCHAR(64) NOT NULL DEFAULT 'none',
        objects_seen INTEGER NOT NULL DEFAULT 0,
        objects_ingested INTEGER NOT NULL DEFAULT 0,
        objects_skipped INTEGER NOT NULL DEFAULT 0,
        objects_failed INTEGER NOT NULL DEFAULT 0,
        started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        completed_at TIMESTAMPTZ
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS "{schema}".azure_blob_source_objects (
        connection_id VARCHAR NOT NULL,
        object_identity VARCHAR(1024) NOT NULL,
        source_version VARCHAR(256),
        document_id VARCHAR,
        missing_sightings INTEGER NOT NULL DEFAULT 0,
        confirmed_missing BOOLEAN NOT NULL DEFAULT FALSE,
        last_seen_at TIMESTAMPTZ,
        PRIMARY KEY (connection_id, object_identity)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS "{schema}".azure_blob_sync_leases (
        connection_id VARCHAR PRIMARY KEY,
        run_id VARCHAR NOT NULL,
        acquired_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        expires_at TIMESTAMPTZ NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS "{schema}".azure_blob_hidden_documents (
        document_id VARCHAR PRIMARY KEY,
        connection_id VARCHAR NOT NULL,
        cause VARCHAR(32) NOT NULL,
        hidden_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
]

PUBLIC_TABLES = [
    """
    CREATE TABLE IF NOT EXISTS public.tenants (
        id VARCHAR PRIMARY KEY,
        name VARCHAR(255) NOT NULL,
        slug VARCHAR(63) UNIQUE NOT NULL,
        status VARCHAR(20) NOT NULL DEFAULT 'active',
        max_users INTEGER NOT NULL DEFAULT 10,
        max_documents INTEGER NOT NULL DEFAULT 1000,
        max_storage_gb INTEGER NOT NULL DEFAULT 5,
        max_model_versions INTEGER NOT NULL DEFAULT 10,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS public.model_versions (
        id VARCHAR PRIMARY KEY,
        tenant_id VARCHAR NOT NULL,
        version_number VARCHAR NOT NULL,
        status VARCHAR NOT NULL DEFAULT 'created',
        artifact_path TEXT,
        metrics JSON,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS public.entity_definitions (
        id VARCHAR PRIMARY KEY,
        tenant_id VARCHAR NOT NULL,
        name VARCHAR(255) NOT NULL,
        description TEXT,
        examples JSON,
        validation_rule VARCHAR(500),
        target_table VARCHAR(255),
        base_label_mapping JSON,
        value_kind VARCHAR(32),
        value_unit VARCHAR(32),
        -- Both added by migration 037. Restated here rather than left out because the tests
        -- that assert on them would otherwise pass against a schema the migration would never
        -- produce, which is the one shape a test database must not have.
        cardinality VARCHAR(16) NOT NULL DEFAULT 'multi',
        sql_identifier VARCHAR(63),
        version INTEGER NOT NULL DEFAULT 1,
        required_flag BOOLEAN DEFAULT FALSE,
        is_active BOOLEAN DEFAULT TRUE,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    )
    """,
    # `CREATE TABLE IF NOT EXISTS` above is a no-op against a database created before these two
    # columns existed, so they are added separately as well.
    """
    ALTER TABLE public.entity_definitions
        ADD COLUMN IF NOT EXISTS cardinality VARCHAR(16) NOT NULL DEFAULT 'multi',
        ADD COLUMN IF NOT EXISTS sql_identifier VARCHAR(63)
    """,
    """
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint
            WHERE conname = 'ck_entity_definitions_cardinality'
              AND conrelid = 'public.entity_definitions'::regclass
        ) THEN
            ALTER TABLE public.entity_definitions
                ADD CONSTRAINT ck_entity_definitions_cardinality
                CHECK (cardinality IN ('multi', 'single'));
        END IF;
    END $$;
    """,
    """
    CREATE UNIQUE INDEX IF NOT EXISTS uq_entity_definitions_tenant_sql_identifier
        ON public.entity_definitions (tenant_id, sql_identifier)
        WHERE sql_identifier IS NOT NULL
    """,
    """
    CREATE TABLE IF NOT EXISTS public.audit_events (
        id VARCHAR PRIMARY KEY,
        actor VARCHAR(255) NOT NULL,
        role VARCHAR(50) NOT NULL,
        action VARCHAR(255) NOT NULL,
        target VARCHAR(255) NOT NULL,
        kind VARCHAR(50) NOT NULL,
        tenant_id VARCHAR,
        created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
    )
    """,
    # CAP-2 control plane (alembic 040). Test-only mirror: the suite runs DDL, not
    # alembic, so the tables the migration creates are restated here. Non-secret
    # metadata, secret references, and finite safe evidence only.
    """
    CREATE TABLE IF NOT EXISTS public.tenant_data_source_connections (
        id UUID PRIMARY KEY,
        tenant_id VARCHAR(64) NOT NULL,
        provider VARCHAR(32) NOT NULL
            CHECK (provider IN ('azure_blob', 'azure_postgresql')),
        configuration JSONB NOT NULL DEFAULT '{}'::jsonb,
        secret_references JSONB NOT NULL DEFAULT '{}'::jsonb,
        status VARCHAR(32) NOT NULL DEFAULT 'draft'
            CHECK (status IN ('draft', 'validated', 'active', 'paused', 'error', 'retired')),
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
    """,
    """
    CREATE UNIQUE INDEX IF NOT EXISTS uq_data_source_active_provider
        ON public.tenant_data_source_connections (tenant_id, provider)
        WHERE status = 'active'
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_data_source_connections_tenant
        ON public.tenant_data_source_connections (tenant_id)
    """,
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
    """,
]


# `CREATE TABLE IF NOT EXISTS` leaves an already-created table exactly as it is, so a
# schema seeded before a column was added never gains it. These reconcile an existing
# fixture database to the current shape, mirroring what the tenant migrations do to real
# schemas. Each is idempotent.
RECONCILE = [
    """
    ALTER TABLE "{schema}".extraction_runs
        ADD COLUMN IF NOT EXISTS processing_mode VARCHAR(32) NOT NULL DEFAULT 'bert_only',
        ADD COLUMN IF NOT EXISTS postprocess_model TEXT,
        ADD COLUMN IF NOT EXISTS postprocess_prompt_version TEXT,
        ADD COLUMN IF NOT EXISTS postprocess_degraded BOOLEAN NOT NULL DEFAULT FALSE
    """,
]


async def main():
    _assert_test_database(DATABASE_URL)
    engine = create_async_engine(DATABASE_URL)
    async with engine.connect() as conn:
        await conn.execute(text("CREATE SCHEMA IF NOT EXISTS public"))
        for ddl in PUBLIC_TABLES:
            await conn.execute(text(ddl))
        print("  Created public tables")

        for schema in SCHEMAS:
            await conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema}"'))
            for table_ddl in TABLES:
                await conn.execute(text(table_ddl.format(schema=schema)))
            for reconcile_ddl in RECONCILE:
                await conn.execute(text(reconcile_ddl.format(schema=schema)))
            print(f"  Created tables in schema {schema}")

        await conn.execute(text("""
            INSERT INTO public.tenants (id, name, slug, status, max_users, max_documents, max_storage_gb, max_model_versions)
            VALUES
                ('test-tenant', 'Test Tenant', 'test-tenant', 'active', 10, 1000, 5, 10),
                ('tenant-b', 'Tenant B', 'tenant-b', 'active', 10, 1000, 5, 10),
                ('no-model', 'No Model Tenant', 'no-model', 'active', 10, 1000, 5, 10),
                ('no-model-tenant', 'No Model Tenant 2', 'no-model-tenant', 'active', 10, 1000, 5, 10)
            ON CONFLICT (id) DO NOTHING
        """))
        print("  Inserted test tenants")

        await conn.commit()
    await engine.dispose()
    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())

