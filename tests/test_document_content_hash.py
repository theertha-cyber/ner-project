"""Content hashing and duplicate identification on document upload.

Covers the `document-content-hash-and-batch-select-all` change: uploads persist a
deterministic SHA-256 of the raw bytes into `documents.checksum`, and a byte-identical
re-upload is *identified* via `duplicate_of` — never rejected, merged, or allowed to
mutate the earlier record.
"""
import hashlib
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
from src.document_service.services.content_hash import compute_content_hash


PDF_CONTENT = b"%PDF-1.4 duplicate detection fixture content " * 10
OTHER_PDF_CONTENT = b"%PDF-1.4 a completely different document body " * 10

_tenant_counter = 0


def auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def make_token(tid, role="business_user"):
    return create_access_token(tenant_id=tid, user_id="test-user", role=role)


_DOCUMENTS_DDL = """
    CREATE TABLE IF NOT EXISTS {schema}.documents (
        id VARCHAR PRIMARY KEY,
        tenant_id VARCHAR NOT NULL,
        filename VARCHAR(255) NOT NULL,
        content_type VARCHAR(255),
        file_size BIGINT,
        checksum VARCHAR(64),
        status VARCHAR(20) DEFAULT 'pending',
        error_message TEXT,
        blob_path VARCHAR(500),
        purpose VARCHAR(20) NOT NULL DEFAULT 'query',
        uploaded_by VARCHAR,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW()
    )
"""


async def _provision_tenant(engine) -> dict:
    global _tenant_counter
    _tenant_counter += 1
    tid = uuid.uuid4().hex
    schema = f"tenant_{tid}"

    async with engine.connect() as conn:
        await conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema}"))
    async with engine.begin() as conn:
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS public.tenants (
                id VARCHAR PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                slug VARCHAR(63) NOT NULL UNIQUE,
                status VARCHAR(20) DEFAULT 'active',
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            )
        """))
        await conn.execute(text(_DOCUMENTS_DDL.format(schema=schema)))
    async with engine.connect() as conn:
        await conn.execute(
            text("INSERT INTO public.tenants (id, name, slug, status) VALUES (:id, :name, :slug, 'active')"),
            {"id": tid, "name": f"Hash Test {_tenant_counter}", "slug": f"hash-test-{_tenant_counter}"},
        )
    return {"tid": tid, "schema": schema}


@pytest.fixture
async def engine():
    eng = create_async_engine(
        settings.database_url, isolation_level="AUTOCOMMIT", poolclass=NullPool,
    )
    yield eng
    await eng.dispose()


@pytest.fixture
async def tenant(engine):
    provisioned = await _provision_tenant(engine)
    yield provisioned
    async with engine.connect() as conn:
        await conn.execute(text(f"DROP SCHEMA IF EXISTS {provisioned['schema']} CASCADE"))
        await conn.execute(text("DELETE FROM public.tenants WHERE id = :id"), {"id": provisioned["tid"]})


@pytest.fixture
async def second_tenant(engine):
    provisioned = await _provision_tenant(engine)
    yield provisioned
    async with engine.connect() as conn:
        await conn.execute(text(f"DROP SCHEMA IF EXISTS {provisioned['schema']} CASCADE"))
        await conn.execute(text("DELETE FROM public.tenants WHERE id = :id"), {"id": provisioned["tid"]})


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def _upload(client, tid, filename, content):
    with patch("src.document_service.api.v1.documents.MinioStorageClient"), \
         patch("src.document_service.api.v1.documents.trigger_ocr"):
        return await client.post(
            "/api/v1/documents",
            files={"file": (filename, io.BytesIO(content), "application/pdf")},
            headers=auth_header(make_token(tid)),
        )


async def _stored_checksum(engine, schema, doc_id) -> str | None:
    async with engine.connect() as conn:
        result = await conn.execute(
            text(f"SELECT checksum FROM {schema}.documents WHERE id = :id"), {"id": doc_id}
        )
        row = result.fetchone()
        return row[0] if row else None


class TestContentHashDeterminism:
    """Spec: Identical content produces the same deterministic hash."""

    def test_same_bytes_produce_the_same_hash(self):
        assert compute_content_hash(PDF_CONTENT) == compute_content_hash(PDF_CONTENT)

    def test_hash_is_64_char_lowercase_sha256_hex(self):
        digest = compute_content_hash(PDF_CONTENT)
        assert digest == hashlib.sha256(PDF_CONTENT).hexdigest()
        assert len(digest) == 64
        assert digest == digest.lower()
        assert all(c in "0123456789abcdef" for c in digest)

    def test_different_bytes_produce_different_hashes(self):
        assert compute_content_hash(PDF_CONTENT) != compute_content_hash(OTHER_PDF_CONTENT)

    def test_hash_does_not_depend_on_filename(self):
        """The helper takes only bytes — there is no filename input path at all."""
        assert compute_content_hash(b"same") == compute_content_hash(bytearray(b"same"))


@pytest.mark.asyncio
class TestUploadPersistsChecksum:
    """Spec: Upload persists a SHA-256 content hash."""

    async def test_upload_returns_and_stores_the_checksum(self, tenant, client, engine):
        resp = await _upload(client, tenant["tid"], "test.pdf", PDF_CONTENT)

        assert resp.status_code == 201, resp.text
        data = resp.json()
        expected = hashlib.sha256(PDF_CONTENT).hexdigest()
        assert data["checksum"] == expected
        assert await _stored_checksum(engine, tenant["schema"], data["id"]) == expected

    async def test_document_metadata_exposes_the_checksum(self, tenant, client):
        upload = await _upload(client, tenant["tid"], "test.pdf", PDF_CONTENT)
        doc_id = upload.json()["id"]

        resp = await client.get(
            f"/api/v1/documents/{doc_id}", headers=auth_header(make_token(tenant["tid"]))
        )

        assert resp.status_code == 200, resp.text
        assert resp.json()["document"]["checksum"] == hashlib.sha256(PDF_CONTENT).hexdigest()


@pytest.mark.asyncio
class TestDuplicateIdentification:
    """Spec: Different filenames with identical content are recognised as identical."""

    async def test_identical_content_under_a_different_filename_is_linked(self, tenant, client, engine):
        first = await _upload(client, tenant["tid"], "original.pdf", PDF_CONTENT)
        second = await _upload(client, tenant["tid"], "renamed-copy.pdf", PDF_CONTENT)

        assert first.status_code == 201, first.text
        assert second.status_code == 201, second.text
        first_data, second_data = first.json(), second.json()

        assert second_data["id"] != first_data["id"]
        assert second_data["checksum"] == first_data["checksum"]
        assert second_data["duplicate_of"] == first_data["id"]
        assert first_data["duplicate_of"] is None

        schema = tenant["schema"]
        assert await _stored_checksum(engine, schema, first_data["id"]) == \
            await _stored_checksum(engine, schema, second_data["id"])

    async def test_a_third_copy_points_at_the_original(self, tenant, client):
        first = await _upload(client, tenant["tid"], "a.pdf", PDF_CONTENT)
        await _upload(client, tenant["tid"], "b.pdf", PDF_CONTENT)
        third = await _upload(client, tenant["tid"], "c.pdf", PDF_CONTENT)

        assert third.json()["duplicate_of"] == first.json()["id"]

    async def test_different_content_is_not_a_duplicate(self, tenant, client):
        first = await _upload(client, tenant["tid"], "one.pdf", PDF_CONTENT)
        second = await _upload(client, tenant["tid"], "two.pdf", OTHER_PDF_CONTENT)

        assert second.json()["duplicate_of"] is None
        assert second.json()["checksum"] != first.json()["checksum"]

    async def test_duplicate_upload_does_not_modify_the_original(self, tenant, client, engine):
        first = await _upload(client, tenant["tid"], "original.pdf", PDF_CONTENT)
        first_id = first.json()["id"]

        schema = tenant["schema"]
        async with engine.connect() as conn:
            await conn.execute(
                text(f"UPDATE {schema}.documents SET status = 'processed' WHERE id = :id"),
                {"id": first_id},
            )

        second = await _upload(client, tenant["tid"], "copy.pdf", PDF_CONTENT)

        async with engine.connect() as conn:
            result = await conn.execute(
                text(f"SELECT id, filename, status, uploaded_by FROM {schema}.documents WHERE id = :id"),
                {"id": first_id},
            )
            row = result.fetchone()

        assert row is not None
        assert row.filename == "original.pdf"
        assert row.status == "processed"
        assert second.json()["id"] != first_id
        assert second.json()["status"] == "pending"
        assert second.json()["duplicate_of"] == first_id

    async def test_duplicate_detection_does_not_cross_tenants(self, tenant, second_tenant, client):
        await _upload(client, tenant["tid"], "shared.pdf", PDF_CONTENT)
        other = await _upload(client, second_tenant["tid"], "shared.pdf", PDF_CONTENT)

        assert other.status_code == 201, other.text
        assert other.json()["duplicate_of"] is None

    async def test_soft_deleted_document_is_not_reported_as_a_duplicate(self, tenant, client, engine):
        first = await _upload(client, tenant["tid"], "gone.pdf", PDF_CONTENT)
        async with engine.connect() as conn:
            await conn.execute(
                text(f"UPDATE {tenant['schema']}.documents SET status = 'deleted' WHERE id = :id"),
                {"id": first.json()["id"]},
            )

        second = await _upload(client, tenant["tid"], "gone-again.pdf", PDF_CONTENT)

        assert second.json()["duplicate_of"] is None
