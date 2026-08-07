"""Create extraction service tables in ner_test database."""
import asyncio
import os
import sys
from urllib.parse import urlparse
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

DATABASE_URL = os.environ.get("NER_DATABASE_URL", "postgresql+asyncpg://ner:ner@localhost:54320/ner_test")

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
        failed_count INTEGER NOT NULL DEFAULT 0
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
        version INTEGER NOT NULL DEFAULT 1,
        required_flag BOOLEAN DEFAULT FALSE,
        is_active BOOLEAN DEFAULT TRUE,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    )
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

