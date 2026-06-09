import io
import os
import uuid
from unittest.mock import patch

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

os.environ.setdefault("NER_DATABASE_URL", "postgresql+asyncpg://ner:ner@localhost:5432/ner_test")
os.environ.setdefault("NER_JWT_SECRET", "test-secret-do-not-use-in-prod")

from src.shared.config import settings
from src.shared.auth import create_access_token
from src.document_service.main import app


def auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def make_token(tid, role="business_user"):
    return create_access_token(tenant_id=tid, user_id="test-user", role=role)


PDF_CONTENT = b"%PDF-1.4 fake pdf content for testing purposes " * 10
PNG_CONTENT = b"\x89PNG\r\n\x1a\nfake png content " * 10

_coll_counter = 0


@pytest.fixture(autouse=True)
async def cleanup_public():
    engine = create_async_engine(
        settings.database_url, isolation_level="AUTOCOMMIT", poolclass=NullPool,
    )
    async with engine.connect() as conn:
        rows = await conn.execute(text("SELECT schema_name FROM information_schema.schemata WHERE schema_name LIKE 'tenant_%'"))
        for row in rows:
            await conn.execute(text(f"DROP SCHEMA IF EXISTS {row[0]} CASCADE"))
    async with engine.connect() as conn:
        await conn.execute(text("DROP TABLE IF EXISTS public.tenants CASCADE"))
    await engine.dispose()


def _create_tables_sql(schema: str) -> list:
    return [
        f"""
            CREATE TABLE IF NOT EXISTS {schema}.documents (
                id VARCHAR PRIMARY KEY,
                tenant_id VARCHAR NOT NULL,
                filename VARCHAR(255) NOT NULL,
                content_type VARCHAR(255),
                file_size BIGINT,
                status VARCHAR(20) DEFAULT 'pending',
                error_message TEXT,
                blob_path VARCHAR(500),
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            )
        """,
        f"""
            CREATE TABLE IF NOT EXISTS {schema}.document_text_spans (
                id VARCHAR PRIMARY KEY,
                document_id VARCHAR NOT NULL,
                span_index INTEGER,
                text TEXT,
                char_start INTEGER,
                char_end INTEGER,
                page_number INTEGER,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """,
    ]


@pytest.fixture
async def seeded_tenant():
    global _coll_counter
    _coll_counter += 1
    engine = create_async_engine(
        settings.database_url, isolation_level="AUTOCOMMIT", poolclass=NullPool,
    )

    tid = uuid.uuid4().hex
    tenant_schema = f"tenant_{tid}"
    slug = f"doc-test-{_coll_counter}"

    async with engine.connect() as conn:
        await conn.execute(text("CREATE SCHEMA IF NOT EXISTS public"))
        await conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {tenant_schema}"))
    async with engine.begin() as conn:
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS public.tenants (
                id VARCHAR PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                slug VARCHAR(63) NOT NULL UNIQUE,
                status VARCHAR(20) DEFAULT 'active',
                max_users INTEGER DEFAULT 10,
                max_documents INTEGER DEFAULT 1000,
                max_storage_gb INTEGER DEFAULT 5,
                max_model_versions INTEGER DEFAULT 10,
                storage_used_bytes BIGINT DEFAULT 0,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            )
        """))
        for ddl in _create_tables_sql(tenant_schema):
            await conn.execute(text(ddl))

    async with engine.connect() as conn:
        await conn.execute(
            text("INSERT INTO public.tenants (id, name, slug, status) VALUES (:id, :name, :slug, 'active')"),
            {"id": tid, "name": f"Doc Test {_coll_counter}", "slug": slug},
        )

    yield {"tid": tid, "slug": slug}

    async with engine.connect() as conn:
        await conn.execute(text(f"DROP SCHEMA IF EXISTS {tenant_schema} CASCADE"))
        await conn.execute(text("DELETE FROM public.tenants WHERE id = :id"), {"id": tid})
    await engine.dispose()


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_7_1_upload_pdf_returns_201(seeded_tenant, client):
    tid = seeded_tenant["tid"]
    slug = seeded_tenant["slug"]
    token = make_token(tid)

    with patch("src.document_service.api.v1.documents.MinioStorageClient") as mock_storage_cls, \
         patch("src.document_service.api.v1.documents.trigger_ocr") as mock_ocr:
        mock_storage = mock_storage_cls.return_value
        mock_ocr.return_value = None

        resp = await client.post(
            "/api/v1/documents",
            files={"file": ("test.pdf", io.BytesIO(PDF_CONTENT), "application/pdf")},
            headers=auth_header(token),
        )

    assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert "id" in data
    assert data["filename"] == "test.pdf"
    assert data["content_type"] == "application/pdf"
    assert data["status"] == "pending"
    assert data["file_size"] == len(PDF_CONTENT)
    assert mock_storage.upload_file.called


@pytest.mark.asyncio
async def test_7_2_unsupported_file_type_returns_422(seeded_tenant, client):
    tid = seeded_tenant["tid"]
    slug = seeded_tenant["slug"]
    token = make_token(tid)

    resp = await client.post(
        "/api/v1/documents",
        files={"file": ("malware.exe", io.BytesIO(b"fake exe"), "application/x-msdownload")},
        headers=auth_header(token),
    )

    assert resp.status_code == 422, f"Expected 422, got {resp.status_code}: {resp.text}"
    assert "not supported" in resp.text.lower()


@pytest.mark.asyncio
async def test_7_3_file_size_exceeded_returns_413(seeded_tenant, client):
    tid = seeded_tenant["tid"]
    slug = seeded_tenant["slug"]
    token = make_token(tid)

    oversized = b"x" * (51 * 1024 * 1024)

    resp = await client.post(
        "/api/v1/documents",
        files={"file": ("huge.pdf", io.BytesIO(oversized), "application/pdf")},
        headers=auth_header(token),
    )

    assert resp.status_code == 413, f"Expected 413, got {resp.status_code}: {resp.text}"
    assert "50MB" in resp.text or "exceeds" in resp.text.lower()


@pytest.mark.asyncio
async def test_7_4_pdf_ocr_processing(seeded_tenant, client):
    tid = seeded_tenant["tid"]
    slug = seeded_tenant["slug"]
    token = make_token(tid)
    doc_id = str(uuid.uuid4())

    with (
        patch("src.document_service.api.v1.documents.MinioStorageClient") as mock_storage_cls,
        patch("src.document_service.api.v1.documents.trigger_ocr") as mock_trigger,
        patch("src.document_service.api.v1.documents.generate_uuid", return_value=doc_id),
    ):
        mock_storage = mock_storage_cls.return_value
        mock_trigger.return_value = None

        resp = await client.post(
            "/api/v1/documents",
            files={"file": ("report.pdf", io.BytesIO(PDF_CONTENT), "application/pdf")},
            headers=auth_header(token),
        )
        assert resp.status_code == 201

    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    schema = f"tenant_{tid}"
    async with engine.begin() as conn:
        await conn.execute(
            text(f"UPDATE {schema}.documents SET status = 'processed' WHERE id = :id"),
            {"id": doc_id},
        )
        await conn.execute(
            text(f"INSERT INTO {schema}.document_text_spans (id, document_id, span_index, text, char_start, char_end, page_number) VALUES (:id, :doc_id, 0, 'Extracted text', 0, 14, 1)"),
            {"id": str(uuid.uuid4()), "doc_id": doc_id},
        )
    await engine.dispose()

    get_resp = await client.get(
        f"/api/v1/documents/{doc_id}",
        headers=auth_header(token),
    )
    assert get_resp.status_code == 200
    assert get_resp.json()["document"]["status"] == "processed"

    engine2 = create_async_engine(settings.database_url, poolclass=NullPool)
    async with engine2.begin() as conn:
        rows = (await conn.execute(
            text(f"SELECT text FROM {schema}.document_text_spans WHERE document_id = :doc_id"),
            {"doc_id": doc_id},
        )).fetchall()
    await engine2.dispose()
    assert len(rows) > 0


@pytest.mark.asyncio
async def test_7_5_image_ocr_processing(seeded_tenant, client):
    tid = seeded_tenant["tid"]
    slug = seeded_tenant["slug"]
    token = make_token(tid)
    doc_id = str(uuid.uuid4())

    with (
        patch("src.document_service.api.v1.documents.MinioStorageClient") as mock_storage_cls,
        patch("src.document_service.api.v1.documents.trigger_ocr") as mock_trigger,
        patch("src.document_service.api.v1.documents.generate_uuid", return_value=doc_id),
    ):
        mock_storage = mock_storage_cls.return_value
        mock_trigger.return_value = None

        resp = await client.post(
            "/api/v1/documents",
            files={"file": ("scan.png", io.BytesIO(PNG_CONTENT), "image/png")},
            headers=auth_header(token),
        )
        assert resp.status_code == 201

    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    schema = f"tenant_{tid}"
    async with engine.begin() as conn:
        await conn.execute(
            text(f"UPDATE {schema}.documents SET status = 'processed' WHERE id = :id"),
            {"id": doc_id},
        )
        await conn.execute(
            text(f"INSERT INTO {schema}.document_text_spans (id, document_id, span_index, text, char_start, char_end, page_number) VALUES (:id, :doc_id, 0, 'Image OCR text', 0, 14, 1)"),
            {"id": str(uuid.uuid4()), "doc_id": doc_id},
        )
    await engine.dispose()

    get_resp = await client.get(
        f"/api/v1/documents/{doc_id}",
        headers=auth_header(token),
    )
    assert get_resp.status_code == 200
    assert get_resp.json()["document"]["status"] == "processed"


@pytest.mark.asyncio
async def test_7_6_corrupt_pdf_fails(seeded_tenant, client):
    tid = seeded_tenant["tid"]
    slug = seeded_tenant["slug"]
    token = make_token(tid)
    doc_id = str(uuid.uuid4())

    with (
        patch("src.document_service.api.v1.documents.MinioStorageClient") as mock_storage_cls,
        patch("src.document_service.api.v1.documents.trigger_ocr") as mock_trigger,
        patch("src.document_service.api.v1.documents.generate_uuid", return_value=doc_id),
    ):
        mock_storage = mock_storage_cls.return_value
        mock_trigger.return_value = None

        resp = await client.post(
            "/api/v1/documents",
            files={"file": ("corrupt.pdf", io.BytesIO(b"not a pdf at all"), "application/pdf")},
            headers=auth_header(token),
        )
        assert resp.status_code == 201

    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    schema = f"tenant_{tid}"
    async with engine.begin() as conn:
        await conn.execute(
            text(f"UPDATE {schema}.documents SET status = 'failed', error_message = 'Corrupt PDF: cannot read trailer' WHERE id = :id"),
            {"id": doc_id},
        )
    await engine.dispose()

    get_resp = await client.get(
        f"/api/v1/documents/{doc_id}",
        headers=auth_header(token),
    )
    assert get_resp.status_code == 200
    doc = get_resp.json()["document"]
    assert doc["status"] == "failed"
    assert doc["error_message"]


@pytest.mark.asyncio
async def test_7_7_list_with_status_filter(seeded_tenant, client):
    tid = seeded_tenant["tid"]
    slug = seeded_tenant["slug"]
    token = make_token(tid)

    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    schema = f"tenant_{tid}"
    async with engine.begin() as conn:
        for i in range(3):
            did = str(uuid.uuid4())
            st = "processed" if i < 2 else "pending"
            await conn.execute(
                text(f"INSERT INTO {schema}.documents (id, tenant_id, filename, content_type, file_size, status, blob_path) VALUES (:id, :tid, :fn, 'application/pdf', 1000, :st, '/blob')"),
                {"id": did, "tid": tid, "fn": f"file{i}.pdf", "st": st},
            )
    await engine.dispose()

    resp = await client.get(
        "/api/v1/documents?status=processed",
        headers=auth_header(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert all(d["status"] == "processed" for d in data["documents"])


@pytest.mark.asyncio
async def test_7_8_get_document_metadata(seeded_tenant, client):
    tid = seeded_tenant["tid"]
    slug = seeded_tenant["slug"]
    token = make_token(tid)
    doc_id = str(uuid.uuid4())

    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    schema = f"tenant_{tid}"
    async with engine.begin() as conn:
        await conn.execute(
            text(f"INSERT INTO {schema}.documents (id, tenant_id, filename, content_type, file_size, status, blob_path) VALUES (:id, :tid, 'meta.pdf', 'application/pdf', 2048, 'processed', '/blob')"),
            {"id": doc_id, "tid": tid},
        )
    await engine.dispose()

    resp = await client.get(
        f"/api/v1/documents/{doc_id}",
        headers=auth_header(token),
    )
    assert resp.status_code == 200
    doc = resp.json()["document"]
    assert doc["id"] == doc_id
    assert doc["filename"] == "meta.pdf"
    assert doc["content_type"] == "application/pdf"
    assert doc["file_size"] == 2048
    assert doc["status"] == "processed"
    assert "created_at" in doc


@pytest.mark.asyncio
async def test_7_9_soft_delete_document(seeded_tenant, client):
    tid = seeded_tenant["tid"]
    slug = seeded_tenant["slug"]
    token = make_token(tid)
    doc_id = str(uuid.uuid4())

    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    schema = f"tenant_{tid}"
    async with engine.begin() as conn:
        await conn.execute(
            text(f"INSERT INTO {schema}.documents (id, tenant_id, filename, content_type, file_size, status, blob_path) VALUES (:id, :tid, 'del.pdf', 'application/pdf', 512, 'processed', '/blob')"),
            {"id": doc_id, "tid": tid},
        )
    await engine.dispose()

    del_resp = await client.delete(
        f"/api/v1/documents/{doc_id}",
        headers=auth_header(token),
    )
    assert del_resp.status_code == 200
    assert del_resp.json()["status"] == "deleted"

    get_resp = await client.get(
        f"/api/v1/documents/{doc_id}",
        headers=auth_header(token),
    )
    assert get_resp.status_code == 200
    assert get_resp.json()["document"]["status"] == "deleted"


@pytest.mark.asyncio
async def test_7_10_matching_tenant_jwt_returns_200(seeded_tenant, client):
    tid = seeded_tenant["tid"]
    slug = seeded_tenant["slug"]
    token = make_token(tid)

    resp = await client.get(
        "/api/v1/documents",
        headers=auth_header(token),
    )
    assert resp.status_code == 200


async def _ensure_public_tenants():  # noqa
    engine = create_async_engine(settings.database_url, isolation_level="AUTOCOMMIT", poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.execute(text("CREATE SCHEMA IF NOT EXISTS public"))
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS public.tenants (
                id VARCHAR PRIMARY KEY, name VARCHAR(255) NOT NULL, slug VARCHAR(63) NOT NULL UNIQUE,
                status VARCHAR(20) DEFAULT 'active', max_users INTEGER DEFAULT 10,
                max_documents INTEGER DEFAULT 1000, max_storage_gb INTEGER DEFAULT 5,
                max_model_versions INTEGER DEFAULT 10, storage_used_bytes BIGINT DEFAULT 0,
                created_at TIMESTAMPTZ DEFAULT NOW(), updated_at TIMESTAMPTZ DEFAULT NOW()
            )
        """))
    await engine.dispose()


@pytest.mark.asyncio
async def test_7_11_jwt_with_unknown_tenant_returns_404(client):
    await _ensure_public_tenants()
    fake_tid = "00000000-0000-0000-0000-000000000000"
    token = make_token(fake_tid)

    resp = await client.get(
        "/api/v1/documents",
        headers=auth_header(token),
    )
    assert resp.status_code == 404, f"Expected 404, got {resp.status_code}: {resp.text}"


@pytest.mark.asyncio
async def test_7_12_jwt_without_tenant_returns_401(client):
    from src.shared.auth import create_access_token
    bad_token = create_access_token(tenant_id=None, user_id="no-tenant", role="business_user")

    resp = await client.get(
        "/api/v1/documents",
        headers=auth_header(bad_token),
    )
    assert resp.status_code == 401, f"Expected 401, got {resp.status_code}: {resp.text}"
