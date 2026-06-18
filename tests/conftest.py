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
async def engine():
    engine = create_async_engine(settings.database_url, isolation_level="AUTOCOMMIT", poolclass=NullPool)
    yield engine
    await engine.dispose()


BASELINE_TENANT_IDS = ["test-tenant", "tenant-b", "no-model", "no-model-tenant"]
_BASELINE_PLACEHOLDERS = ", ".join(f":id_{i}" for i in range(len(BASELINE_TENANT_IDS)))


@pytest_asyncio.fixture(scope="function")
async def setup_database(engine):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(text("""
            CREATE SCHEMA IF NOT EXISTS tenant_template
        """))
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
