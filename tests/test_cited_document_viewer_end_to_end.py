"""End-to-end proof that a cited document opens — verification.md § end-to-end rows.

Every other suite here exercises one layer. This one drives the real HTTP routes with a
signed JWT against a real tenant schema holding one document per retention mode plus a
chat attachment, and asserts what a reader would actually get: the bytes, or the specific
reason they cannot have them.

The precedent is `tests/test_chat_uploader_isolation_end_to_end.py`, written after that
change shipped with every layer tested and the whole path untested. Source inspection is
not proof.
"""

import io
import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker

from src.document_service.main import app
from src.shared.auth import create_access_token

pytestmark = [pytest.mark.verification, pytest.mark.integration]

READER = "recruiter-1"
COLLEAGUE = "recruiter-2"
CONV = "viewer-e2e-conversation"

PDF_BYTES = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"


def _tiff(pages: int = 2) -> bytes:
    from PIL import Image

    frames = [Image.new("RGB", (60, 40), (20 * i, 100, 140)) for i in range(pages)]
    buffer = io.BytesIO()
    frames[0].save(buffer, format="TIFF", save_all=True, append_images=frames[1:])
    return buffer.getvalue()


class _Store:
    def __init__(self):
        self.objects = {}

    def open(self, reference):
        return self.objects.get(reference)


@pytest_asyncio.fixture
async def library(tenant_schema, engine, monkeypatch):
    """One document per shape a reader can encounter from a citation chip."""
    tenant_id, schema = tenant_schema
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    store = _Store()
    ids = {}

    from src.document_service import content_resolution

    monkeypatch.setattr(content_resolution, "store_for", lambda mode: store)

    async def _reopen(tenant, source_id, external_id):
        return PDF_BYTES

    content_resolution.register_source_reopener("azure_blob", _reopen)

    async with session_factory() as session:
        for column, ddl in (
            ("ingested_by_kind", "VARCHAR(32)"),
            ("conversation_id", "VARCHAR"),
            ("retention_mode", "VARCHAR(32) NOT NULL DEFAULT 'platform_blob'"),
            ("blob_path", "VARCHAR(500)"),
            ("content_type", "VARCHAR(255)"),
            ("source_type", "VARCHAR(64)"),
            ("source_id", "VARCHAR(128)"),
            ("external_id", "VARCHAR(512)"),
        ):
            await session.execute(
                text(f"ALTER TABLE {schema}.documents ADD COLUMN IF NOT EXISTS {column} {ddl}")
            )
        await session.execute(
            text(
                f"INSERT INTO {schema}.conversations (id, tenant_id, user_id, title) "
                "VALUES (:c, :t, :u, 'T') ON CONFLICT (id) DO NOTHING"
            ),
            {"c": CONV, "t": tenant_id, "u": READER},
        )

        # key, filename, uploader, conversation, retention, payload, source_type
        seeds = [
            ("retained", "alice.pdf", READER, None, "platform_blob", PDF_BYTES, "platform_upload"),
            ("colleague", "dave.pdf", COLLEAGUE, None, "platform_blob", PDF_BYTES, "platform_upload"),
            ("synced", "carol.pdf", None, None, "source_only", None, "azure_blob"),
            ("released", "gone.pdf", READER, None, "ephemeral", None, "platform_upload"),
            ("attachment", "jd.pdf", READER, CONV, "platform_blob", PDF_BYTES, "platform_upload"),
            ("scan", "scan.tiff", READER, None, "platform_blob", _tiff(2), "platform_upload"),
        ]
        for key, filename, uploader, conv, retention, payload, source_type in seeds:
            doc_id = f"doc-{key}-{uuid.uuid4()}"
            ids[key] = doc_id
            reference = f"tenants/{tenant_id}/documents/{doc_id}" if payload else None
            if payload:
                store.objects[reference] = payload
            await session.execute(
                text(f"""
                    INSERT INTO {schema}.documents
                        (id, tenant_id, filename, status, purpose, uploaded_by,
                         ingested_by_kind, conversation_id, retention_mode, blob_path,
                         content_type, source_type, external_id, file_size)
                    VALUES (:id, :t, :fn, 'processed', 'query', :up, :kind, :conv,
                            :ret, :ref, 'application/pdf', :st, 'external/1', :size)
                """),
                {"id": doc_id, "t": tenant_id, "fn": filename, "up": uploader,
                 "kind": "source_system" if uploader is None else "human",
                 "conv": conv, "ret": retention, "ref": reference,
                 "st": source_type, "size": len(payload or b"")},
            )
        await session.commit()

    yield tenant_id, schema, ids


async def _open(tenant_id, doc_id, user=READER, role="business_user"):
    token = create_access_token(tenant_id=tenant_id, user_id=user, role=role)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.get(
            f"/api/v1/documents/{doc_id}/content",
            headers={"Authorization": f"Bearer {token}"},
        )


async def _probe(tenant_id, doc_id, user=READER):
    token = create_access_token(tenant_id=tenant_id, user_id=user, role="business_user")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.get(
            f"/api/v1/documents/{doc_id}/content/status",
            headers={"Authorization": f"Bearer {token}"},
        )


# --- What a reader gets from a chip --------------------------------------------------


async def test_a_reader_opens_the_document_their_answer_cited(library):
    """The feature, end to end."""
    tenant_id, _schema, ids = library
    response = await _open(tenant_id, ids["retained"])

    assert response.status_code == 200, response.text
    assert response.content == PDF_BYTES
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["content-disposition"].startswith("inline")


async def test_a_reader_opens_their_own_attachment_from_the_thread(library):
    tenant_id, _schema, ids = library
    response = await _open(tenant_id, ids["attachment"])

    assert response.status_code == 200, response.text
    assert response.content == PDF_BYTES


async def test_an_azure_synced_document_opens_by_re_reading_its_source(library):
    """No platform copy exists for these at all — the bytes come back from the source
    adapter, and this only works because the adapter is registered in this process."""
    tenant_id, _schema, ids = library
    response = await _open(tenant_id, ids["synced"])

    assert response.status_code == 200, response.text
    assert response.content == PDF_BYTES


async def test_a_scan_is_converted_and_opens_as_a_pdf(library):
    tenant_id, _schema, ids = library
    response = await _open(tenant_id, ids["scan"])

    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF")


# --- What a reader is told when they cannot ------------------------------------------


async def test_a_released_original_says_so_rather_than_failing_vaguely(library):
    tenant_id, _schema, ids = library
    response = await _open(tenant_id, ids["released"])

    assert response.status_code == 410
    assert response.json()["detail"]["code"] == "ORIGINAL_RELEASED"
    assert "retention" in response.json()["detail"]["message"].lower()


async def test_a_colleagues_document_does_not_open(library):
    """The uploader rule reaches the byte boundary too: a chip is only shown for a
    document the reader may see, and this is what stops that being the only thing
    standing between them and the file."""
    tenant_id, _schema, ids = library
    response = await _open(tenant_id, ids["colleague"])

    assert response.status_code == 403
    assert b"%PDF" not in response.content


async def test_a_colleague_cannot_open_the_attachment(library):
    tenant_id, _schema, ids = library
    response = await _open(tenant_id, ids["attachment"], user=COLLEAGUE)

    assert response.status_code == 403
    assert b"%PDF" not in response.content


# --- The probe answers before any transfer -------------------------------------------


async def test_the_probe_tells_the_viewer_how_to_render_before_transfer(library):
    tenant_id, _schema, ids = library

    retained = (await _probe(tenant_id, ids["retained"])).json()
    scan = (await _probe(tenant_id, ids["scan"])).json()
    released = (await _probe(tenant_id, ids["released"])).json()

    assert retained["available"] is True and retained["render_mode"] == "pdf"
    assert scan["render_mode"] == "convert"
    assert released["available"] is False and released["reason"] == "ORIGINAL_RELEASED"


async def test_no_response_discloses_where_the_bytes_live(library):
    tenant_id, _schema, ids = library
    for key in ("retained", "synced", "scan"):
        response = await _open(tenant_id, ids[key])
        assert not response.is_redirect
        headers = " ".join(f"{k}:{v}" for k, v in response.headers.items()).lower()
        for leak in ("location", "x-amz", "amazonaws", "blob.core.windows.net", "minio", "tenants/"):
            assert leak not in headers, f"{leak} disclosed for {key}"
