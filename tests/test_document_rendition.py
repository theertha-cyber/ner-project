"""Converting an original into a viewable PDF.

Covers the rendition capability: conversion per format, that a rendition is derived and
never replaces the original, that nothing is persisted, and that every failure is reported
rather than masked.

The failure cases matter more than the happy path here. A conversion that silently
returns an empty PDF, or the unconverted bytes under a PDF media type, produces a blank
panel — and a reader checking a citation cannot tell a blank document from a broken one.
"""

import csv
import io
import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker

from src.document_service import rendition
from src.document_service.main import app
from src.shared.auth import create_access_token

pytestmark = [pytest.mark.verification, pytest.mark.integration]

USER = "recruiter-1"


def _tiff_bytes(pages: int = 3) -> bytes:
    """A real multi-page TIFF, so the page-per-frame assertion means something."""
    from PIL import Image

    frames = [Image.new("RGB", (80, 60), color=(i * 60 % 255, 90, 120)) for i in range(pages)]
    buffer = io.BytesIO()
    frames[0].save(buffer, format="TIFF", save_all=True, append_images=frames[1:])
    return buffer.getvalue()


def _csv_bytes() -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["candidate", "skill", "years"])
    writer.writerow(["Alice", "Python", "5"])
    writer.writerow(["Dave", "Flask", "7"])
    return buffer.getvalue().encode()


def _pdf_page_count(data: bytes) -> int:
    import fitz

    with fitz.open(stream=data, filetype="pdf") as doc:
        return doc.page_count


def _pdf_text(data: bytes) -> str:
    import fitz

    with fitz.open(stream=data, filetype="pdf") as doc:
        return " ".join(page.get_text() for page in doc)


# --- Conversion per format -----------------------------------------------------------


def test_a_multi_page_tiff_becomes_one_pdf_page_per_frame():
    """Page structure is preserved, so a page reference into the original still means
    something in the rendition."""
    converted = rendition.to_pdf(_tiff_bytes(pages=3), "image/tiff")

    assert converted.startswith(b"%PDF")
    assert _pdf_page_count(converted) == 3


def test_a_csv_becomes_a_readable_pdf():
    converted = rendition.to_pdf(_csv_bytes(), "text/csv")

    assert converted.startswith(b"%PDF")
    rendered = _pdf_text(converted)
    assert "Alice" in rendered
    assert "Python" in rendered


def test_a_large_csv_paginates_rather_than_truncating():
    rows = "\n".join(f"row-{i},value-{i}" for i in range(400)).encode()
    converted = rendition.to_pdf(rows, "text/csv")

    assert _pdf_page_count(converted) > 1
    assert "row-399" in _pdf_text(converted)


def test_natively_renderable_formats_are_not_converted():
    from src.document_service.media_types import requires_conversion

    assert requires_conversion("application/pdf") is False
    assert requires_conversion("image/png") is False
    assert requires_conversion("image/jpeg") is False
    # Formats no browser renders do need it.
    assert requires_conversion("image/tiff") is True
    assert requires_conversion("text/csv") is True
    assert requires_conversion(
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    ) is True


# --- Failure is reported, never masked -----------------------------------------------


def test_a_corrupt_original_fails_explicitly():
    with pytest.raises(rendition.ConversionFailed):
        rendition.to_pdf(b"this is not a tiff", "image/tiff")


def test_an_oversized_original_is_refused_before_parsing():
    oversized = b"x" * (rendition.MAX_CONVERTIBLE_BYTES + 1)
    with pytest.raises(rendition.ConversionTooLarge):
        rendition.to_pdf(oversized, "text/csv")


def test_an_unsupported_type_is_refused_rather_than_guessed():
    with pytest.raises(rendition.ConversionFailed):
        rendition.to_pdf(b"%PDF-1.4", "application/zip")


def test_a_missing_converter_is_reported_not_masked(monkeypatch):
    """The Word toolchain lives only in the converting service's image. Elsewhere this is
    a deployment fact, and must surface as a failure rather than a blank document."""
    import subprocess

    def _absent(*args, **kwargs):
        raise FileNotFoundError("soffice")

    monkeypatch.setattr(subprocess, "run", _absent)

    with pytest.raises(rendition.ConversionFailed):
        rendition.to_pdf(b"PK\x03\x04 fake docx", rendition_word_type())


def test_a_conversion_that_exceeds_its_bound_is_abandoned(monkeypatch):
    import subprocess

    def _hang(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="soffice", timeout=rendition.CONVERSION_TIMEOUT_SECONDS)

    monkeypatch.setattr(subprocess, "run", _hang)

    with pytest.raises(rendition.ConversionTimedOut):
        rendition.to_pdf(b"PK\x03\x04 fake docx", rendition_word_type())


def test_no_failure_path_returns_the_unconverted_bytes():
    """The failure that would be invisible: handing pdf.js a docx labelled as a PDF."""
    original = b"PK\x03\x04 definitely not a pdf"
    for media_type in ("image/tiff", "text/csv", "application/zip"):
        try:
            produced = rendition.to_pdf(original, media_type)
        except rendition.ConversionFailed:
            continue
        assert produced != original
        assert produced.startswith(b"%PDF")


def rendition_word_type() -> str:
    return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


# --- Nothing is persisted ------------------------------------------------------------


def test_conversion_writes_nothing_to_any_store(monkeypatch):
    """A stored rendition of an `ephemeral` or `source_only` document would durably
    recreate what that tenant's retention policy deleted or declined to store."""
    puts = []

    class _Watching:
        def put(self, *args, **kwargs):
            puts.append(args)
            return "ref"

        def open(self, reference):
            return None

        def delete(self, reference):
            pass

    from src.document_service import content_resolution

    monkeypatch.setattr(content_resolution, "store_for", lambda mode: _Watching())

    rendition.to_pdf(_csv_bytes(), "text/csv")

    assert puts == []


def test_the_module_persists_nothing_at_all():
    """Asserted on the source as well as on behaviour: a cache added later without a
    retention gate is exactly the mistake this is guarding."""
    import inspect

    source = inspect.getsource(rendition)
    for forbidden in ("get_durable_store", "get_working_store", ".put("):
        assert forbidden not in source, f"rendition writes to a store ({forbidden})"


# --- Through the route ----------------------------------------------------------------


@pytest_asyncio.fixture
async def convertible(tenant_schema, engine, monkeypatch):
    tenant_id, schema = tenant_schema
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    store = type("S", (), {"objects": {}, "open": lambda self, r: self.objects.get(r)})()
    store.objects = {}
    ids = {}

    from src.document_service import content_resolution

    monkeypatch.setattr(content_resolution, "store_for", lambda mode: store)

    async with session_factory() as session:
        for column, ddl in (
            ("ingested_by_kind", "VARCHAR(32)"),
            ("conversation_id", "VARCHAR"),
            ("retention_mode", "VARCHAR(32) NOT NULL DEFAULT 'platform_blob'"),
            ("blob_path", "VARCHAR(500)"),
            ("content_type", "VARCHAR(255)"),
            ("source_type", "VARCHAR(64)"),
        ):
            await session.execute(
                text(f"ALTER TABLE {schema}.documents ADD COLUMN IF NOT EXISTS {column} {ddl}")
            )
        for key, filename, payload in (
            ("csv", "table.csv", _csv_bytes()),
            ("tiff", "scan.tiff", _tiff_bytes(2)),
            ("broken", "broken.tiff", b"not a tiff at all"),
        ):
            doc_id = f"doc-{key}-{uuid.uuid4()}"
            ids[key] = doc_id
            reference = f"tenants/{tenant_id}/documents/{doc_id}"
            store.objects[reference] = payload
            await session.execute(
                text(f"""
                    INSERT INTO {schema}.documents
                        (id, tenant_id, filename, status, purpose, uploaded_by,
                         ingested_by_kind, retention_mode, blob_path, content_type,
                         source_type, file_size)
                    VALUES (:id, :t, :fn, 'processed', 'query', :u, 'human',
                            'platform_blob', :ref, NULL, 'platform_upload', :size)
                """),
                {"id": doc_id, "t": tenant_id, "fn": filename, "u": USER,
                 "ref": reference, "size": len(payload)},
            )
        await session.commit()

    yield tenant_id, schema, ids


async def _fetch(tenant_id, doc_id):
    token = create_access_token(tenant_id=tenant_id, user_id=USER, role="business_user")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.get(
            f"/api/v1/documents/{doc_id}/content",
            headers={"Authorization": f"Bearer {token}"},
        )


async def test_a_csv_is_served_as_a_pdf(convertible):
    tenant_id, _schema, ids = convertible
    response = await _fetch(tenant_id, ids["csv"])

    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF")


async def test_a_tiff_is_served_as_a_pdf_with_its_pages(convertible):
    tenant_id, _schema, ids = convertible
    response = await _fetch(tenant_id, ids["tiff"])

    assert response.status_code == 200, response.text
    assert _pdf_page_count(response.content) == 2


async def test_a_failed_conversion_is_reported_and_leaves_the_document_alone(
    convertible, engine,
):
    tenant_id, schema, ids = convertible
    response = await _fetch(tenant_id, ids["broken"])

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "CONVERSION_FAILED"
    assert not response.content.startswith(b"%PDF")

    async with async_sessionmaker(engine, expire_on_commit=False)() as session:
        row = (await session.execute(
            text(f"SELECT status, content_type, blob_path FROM {schema}.documents WHERE id = :i"),
            {"i": ids["broken"]},
        )).fetchone()

    assert row.status == "processed", "a failed conversion changed the document's status"
    assert row.blob_path is not None, "a failed conversion altered the storage reference"
