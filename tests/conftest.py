import os
import subprocess
import sys
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import text
from sqlalchemy.pool import NullPool

os.environ.setdefault("NER_DATABASE_URL", "postgresql+asyncpg://ner:ner@localhost:54320/ner_test")
os.environ.setdefault("NER_DATABASE_URL_SYNC", "postgresql://ner:ner@localhost:54320/ner_test")
os.environ.setdefault("NER_JWT_SECRET", "test-secret-do-not-use-in-prod")
os.environ.setdefault("NER_MINIO_ACCESS_KEY", "test-minio-access-key")
os.environ.setdefault("NER_MINIO_SECRET_KEY", "test-minio-secret-key")

from src.shared.config import settings
from src.gateway.main import app
from src.gateway.models import Base


def pytest_sessionstart(session):
    setup_script = os.path.join(os.path.dirname(__file__), "..", "scripts", "setup_test_db.py")
    if os.path.exists(setup_script):
        subprocess.run([sys.executable, setup_script], check=True, cwd=os.path.dirname(setup_script))


@pytest_asyncio.fixture(scope="function")
async def tenant_schema(engine, setup_database):
    tid = "test-tenant"
    schema_name = f"tenant_{tid.replace('-', '_')}"
    async with engine.begin() as conn:
        await conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema_name}"))
        for stmt in _TENANT_TABLES_SQL.split(";"):
            s = stmt.strip().format(schema=schema_name)
            if s:
                await conn.execute(text(s + ";"))
        await conn.execute(
            text(f"ALTER TABLE {schema_name}.extraction_runs DROP CONSTRAINT IF EXISTS {schema_name}.extraction_runs_document_id_fkey")
        )
        await conn.execute(
            text(f"ALTER TABLE {schema_name}.extraction_runs ALTER COLUMN document_id DROP NOT NULL")
        )
    yield tid, schema_name
    async with engine.begin() as conn:
        await conn.execute(text(f"DROP SCHEMA IF EXISTS {schema_name} CASCADE"))


@pytest_asyncio.fixture(scope="function")
async def engine():
    engine = create_async_engine(settings.database_url, isolation_level="AUTOCOMMIT", poolclass=NullPool)
    yield engine
    await engine.dispose()


BASELINE_TENANT_IDS = ["test-tenant", "tenant-b", "no-model", "no-model-tenant"]
_BASELINE_PLACEHOLDERS = ", ".join(f":id_{i}" for i in range(len(BASELINE_TENANT_IDS)))

_TENANT_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS {schema}.documents (
    id VARCHAR PRIMARY KEY,
    tenant_id VARCHAR NOT NULL,
    filename VARCHAR(255) NOT NULL,
    mime_type VARCHAR(100),
    file_size_bytes BIGINT,
    checksum VARCHAR(64),
    storage_uri VARCHAR(500),
    status VARCHAR(20) DEFAULT 'uploaded',
    ocr_applied_flag BOOLEAN DEFAULT false,
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS {schema}.document_text_spans (
    id VARCHAR PRIMARY KEY,
    document_id VARCHAR NOT NULL REFERENCES {schema}.documents(id) ON DELETE CASCADE,
    page_no INTEGER,
    block_no INTEGER,
    text TEXT,
    start_offset INTEGER,
    end_offset INTEGER,
    ocr_confidence FLOAT
);
CREATE TABLE IF NOT EXISTS {schema}.annotation_tasks (
    id VARCHAR PRIMARY KEY,
    document_id VARCHAR NOT NULL REFERENCES {schema}.documents(id) ON DELETE CASCADE,
    assignee VARCHAR,
    status VARCHAR(20) DEFAULT 'unannotated',
    reviewer VARCHAR,
    dataset_version INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS {schema}.spans (
    id VARCHAR PRIMARY KEY,
    document_id VARCHAR NOT NULL REFERENCES {schema}.documents(id) ON DELETE CASCADE,
    entity_type VARCHAR(255) NOT NULL,
    char_start INTEGER NOT NULL,
    char_end INTEGER NOT NULL,
    text_content VARCHAR NOT NULL,
    confidence FLOAT NOT NULL DEFAULT 1.0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ
);
CREATE TABLE IF NOT EXISTS {schema}.suggested_spans (
    id VARCHAR PRIMARY KEY,
    document_id VARCHAR NOT NULL REFERENCES {schema}.documents(id) ON DELETE CASCADE,
    entity_type VARCHAR(255) NOT NULL,
    char_start INTEGER NOT NULL,
    char_end INTEGER NOT NULL,
    text_content VARCHAR NOT NULL,
    confidence FLOAT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS {schema}.training_jobs (
    id VARCHAR PRIMARY KEY,
    tenant_id VARCHAR NOT NULL,
    dataset_version INTEGER,
    base_model VARCHAR(255),
    hyperparameters JSONB,
    status VARCHAR(20) DEFAULT 'queued',
    metrics_uri VARCHAR(500),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ
);
CREATE TABLE IF NOT EXISTS {schema}.model_versions (
    id VARCHAR PRIMARY KEY,
    tenant_id VARCHAR NOT NULL,
    version INTEGER NOT NULL,
    artifact_uri VARCHAR(500),
    training_job_id VARCHAR,
    metrics JSONB,
    status VARCHAR(20) DEFAULT 'candidate',
    active_flag BOOLEAN DEFAULT false,
    promoted_by VARCHAR,
    promoted_at TIMESTAMPTZ
);
CREATE TABLE IF NOT EXISTS {schema}.extraction_runs (
    id VARCHAR PRIMARY KEY,
    tenant_id VARCHAR NOT NULL,
    document_id VARCHAR NOT NULL REFERENCES {schema}.documents(id) ON DELETE CASCADE,
    model_version VARCHAR,
    status VARCHAR(20) DEFAULT 'queued',
    started_at TIMESTAMPTZ
);
CREATE TABLE IF NOT EXISTS {schema}.extracted_entities (
    id VARCHAR PRIMARY KEY,
    run_id VARCHAR NOT NULL REFERENCES {schema}.extraction_runs(id) ON DELETE CASCADE,
    entity_id VARCHAR NOT NULL,
    value TEXT,
    confidence FLOAT,
    normalized_value TEXT,
    source_span_id VARCHAR,
    review_status VARCHAR(20) DEFAULT 'unreviewed',
    corrected_value TEXT,
    corrected_by VARCHAR,
    correction_notes TEXT,
    document_id VARCHAR
);
"""


@pytest_asyncio.fixture(scope="function")
async def setup_database(engine):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(text("""
            CREATE SCHEMA IF NOT EXISTS tenant_template
        """))
        for stmt in _TENANT_TABLES_SQL.split(";"):
            s = stmt.strip().format(schema="tenant_template")
            if s:
                await conn.execute(text(s + ";"))
        await conn.execute(text("""
            INSERT INTO public.tenants (id, name, slug, status, max_users, max_documents, max_storage_gb, max_model_versions)
            VALUES
                ('test-tenant', 'Test Tenant', 'test-tenant', 'active', 10, 1000, 5, 10),
                ('tenant-b', 'Tenant B', 'tenant-b', 'active', 10, 1000, 5, 10),
                ('no-model', 'No Model Tenant', 'no-model', 'active', 10, 1000, 5, 10),
                ('no-model-tenant', 'No Model Tenant 2', 'no-model-tenant', 'active', 10, 1000, 5, 10)
            ON CONFLICT (id) DO NOTHING
        """))
    yield
    async with engine.begin() as conn:
        await conn.execute(text("DROP TABLE IF EXISTS public.tenant_users CASCADE"))
        await conn.execute(text("DROP TABLE IF EXISTS public.entity_definitions CASCADE"))
        await conn.execute(text("DROP TABLE IF EXISTS tenant_template.documents CASCADE"))
        baseline_params = {f"id_{i}": tid for i, tid in enumerate(BASELINE_TENANT_IDS)}
        await conn.execute(
            text(f"DELETE FROM public.tenants WHERE id NOT IN ({_BASELINE_PLACEHOLDERS})"),
            baseline_params,
        )


@pytest_asyncio.fixture
async def db_session(engine, setup_database):
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def client(engine, setup_database):
    from src.shared.database import get_engine
    app.state.db_factory = get_engine
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
