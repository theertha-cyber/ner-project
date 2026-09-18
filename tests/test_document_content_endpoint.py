"""The content routes: bytes, probe, media-type coercion and the failure taxonomy.

Covers the content-access rows not covered by the authorization suite, plus
"A content response carries bytes, not a location" and the startup-registration scenario.

The test that matters most here is `test_a_stored_html_type_is_never_served_as_html`.
The portal cannot put an Authorization header on an `<iframe src>`, so it fetches bytes
and renders them from an object URL — and an object URL inherits the portal's origin,
where the access token lives in memory. `documents.content_type` is whatever the
uploading client declared and is never validated against the file, so echoing it back
would be handing a browser something it is willing to execute inside that origin.
"""

import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker

from src.document_service.main import app
from src.shared.auth import create_access_token

pytestmark = [pytest.mark.verification, pytest.mark.integration]

USER = "recruiter-1"
PDF_BYTES = b"%PDF-1.4\n" + bytes(range(256)) * 4  # includes non-UTF8, so truncation shows


def auth(tenant_id, user_id=USER, role="business_user"):
    token = create_access_token(tenant_id=tenant_id, user_id=user_id, role=role)
    return {"Authorization": f"Bearer {token}"}


class _FakeStore:
    def __init__(self):
        self.objects = {}
        self.opened = []

    def open(self, reference):
        self.opened.append(reference)
        return self.objects.get(reference)


@pytest_asyncio.fixture
async def docs(tenant_schema, engine, monkeypatch):
    """One document per interesting shape, sharing a fake content store."""
    tenant_id, schema = tenant_schema
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    store = _FakeStore()
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
            ("source_id", "VARCHAR(128)"),
            ("external_id", "VARCHAR(512)"),
        ):
            await session.execute(
                text(f"ALTER TABLE {schema}.documents ADD COLUMN IF NOT EXISTS {column} {ddl}")
            )

        # (key, filename, declared content_type, retention, has reference, source_type)
        seeds = [
            ("pdf", "report.pdf", "application/pdf", "platform_blob", True, "platform_upload"),
            ("png", "scan.png", "image/png", "platform_blob", True, "platform_upload"),
            ("docx", "cv.docx", None, "platform_blob", True, "platform_upload"),
            ("csv", "table.csv", "text/csv", "platform_blob", True, "platform_upload"),
            # The attack shape: an allowed extension, a declared type that is not.
            ("html_typed", "resume.pdf", "text/html", "platform_blob", True, "platform_upload"),
            # An ephemeral document past its terminal state: reference released.
            ("released", "gone.pdf", "application/pdf", "ephemeral", False, "platform_upload"),
            # A reference that the store no longer holds.
            ("missing", "lost.pdf", "application/pdf", "platform_blob", True, "platform_upload"),
            ("source_only", "synced.pdf", "application/pdf", "source_only", False, "azure_blob"),
            ("no_adapter", "orphan.pdf", "application/pdf", "source_only", False, "nowhere"),
        ]
        for key, filename, declared, retention, has_ref, source_type in seeds:
            doc_id = f"doc-{key}-{uuid.uuid4()}"
            ids[key] = doc_id
            reference = f"tenants/{tenant_id}/documents/{doc_id}" if has_ref else None
            if has_ref and key != "missing":
                store.objects[reference] = PDF_BYTES
            await session.execute(
                text(f"""
                    INSERT INTO {schema}.documents
                        (id, tenant_id, filename, status, purpose, uploaded_by,
                         ingested_by_kind, retention_mode, blob_path, content_type,
                         source_type, file_size)
                    VALUES (:id, :t, :fn, 'processed', 'query', :u, 'human',
                            :ret, :ref, :ct, :st, :size)
                """),
                {"id": doc_id, "t": tenant_id, "fn": filename, "u": USER,
                 "ret": retention, "ref": reference, "ct": declared,
                 "st": source_type, "size": len(PDF_BYTES)},
            )
        await session.commit()

    yield tenant_id, schema, ids, store


async def _get(path, tenant_id, **kw):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.get(path, headers=auth(tenant_id, **kw))


async def _content(tenant_id, doc_id, **kw):
    return await _get(f"/api/v1/documents/{doc_id}/content", tenant_id, **kw)


async def _probe(tenant_id, doc_id, **kw):
    return await _get(f"/api/v1/documents/{doc_id}/content/status", tenant_id, **kw)


# --- Serving the original -----------------------------------------------------------


async def test_a_retained_original_is_returned_byte_for_byte(docs):
    tenant_id, _schema, ids, _store = docs
    response = await _content(tenant_id, ids["pdf"])

    assert response.status_code == 200, response.text
    assert response.content == PDF_BYTES
    assert response.headers["content-disposition"].startswith("inline")


async def test_a_supported_format_is_served_as_itself(docs):
    tenant_id, _schema, ids, _store = docs
    assert (await _content(tenant_id, ids["pdf"])).headers["content-type"] == "application/pdf"
    assert (await _content(tenant_id, ids["png"])).headers["content-type"] == "image/png"


# --- Media-type coercion: the security case -----------------------------------------


async def test_a_stored_html_type_is_never_served_as_html(docs):
    """The recorded type is attacker-chosen: ingestion validates the extension, not the
    declared type. A served `text/html` would execute in the portal's origin."""
    tenant_id, _schema, ids, _store = docs
    response = await _content(tenant_id, ids["html_typed"])

    assert response.status_code == 200
    assert "text/html" not in response.headers["content-type"]
    # `.pdf` is what ingestion actually validated, so that is what it is served as.
    assert response.headers["content-type"] == "application/pdf"


async def test_content_type_sniffing_is_disabled(docs):
    tenant_id, _schema, ids, _store = docs
    response = await _content(tenant_id, ids["pdf"])
    assert response.headers["x-content-type-options"] == "nosniff"


async def test_the_response_is_sandboxed(docs):
    tenant_id, _schema, ids, _store = docs
    csp = (await _content(tenant_id, ids["pdf"])).headers["content-security-policy"]
    assert "sandbox" in csp
    assert "object-src 'none'" in csp


async def test_the_response_is_not_cached(docs):
    tenant_id, _schema, ids, _store = docs
    assert "no-store" in (await _content(tenant_id, ids["pdf"])).headers["cache-control"]


# --- "A content response carries bytes, not a location" -----------------------------


async def test_no_response_is_a_redirect_or_names_a_storage_location(docs):
    """Asserted for failures as well as successes: an error path is exactly where a
    storage detail tends to leak out in a message or a header."""
    tenant_id, _schema, ids, _store = docs
    for key in ("pdf", "png", "docx", "released", "missing", "no_adapter"):
        response = await _content(tenant_id, ids[key])
        assert not response.is_redirect, key
        joined = " ".join(f"{k}: {v}" for k, v in response.headers.items()).lower()
        for leak in ("location", "x-amz", "amazonaws", "blob.core.windows.net", "minio"):
            assert leak not in joined, f"{leak} disclosed in headers for {key}"
        if response.headers.get("content-type", "").startswith("application/json"):
            assert "tenants/" not in response.text, f"storage reference leaked in body for {key}"


async def test_the_natively_renderable_formats_are_served_unconverted(docs):
    tenant_id, _schema, ids, _store = docs
    for key in ("pdf", "png"):
        response = await _content(tenant_id, ids[key])
        assert response.status_code == 200, key
        assert response.content == PDF_BYTES, f"{key} was altered on the way out"


# --- The probe ------------------------------------------------------------------------


async def test_the_probe_describes_a_viewable_document_without_reading_bytes(docs):
    tenant_id, _schema, ids, store = docs
    before = list(store.opened)

    response = await _probe(tenant_id, ids["pdf"])

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["available"] is True
    assert body["render_mode"] == "pdf"
    assert body["media_type"] == "application/pdf"
    assert body["file_size"] == len(PDF_BYTES)
    assert store.opened == before, "the probe opened the content store"


async def test_the_probe_reports_a_released_original(docs):
    tenant_id, _schema, ids, store = docs
    before = list(store.opened)

    body = (await _probe(tenant_id, ids["released"])).json()

    assert body["available"] is False
    assert body["reason"] == "ORIGINAL_RELEASED"
    assert store.opened == before


async def test_the_probe_reports_that_conversion_is_required(docs):
    tenant_id, _schema, ids, _store = docs
    for key in ("docx", "csv"):
        body = (await _probe(tenant_id, ids[key])).json()
        assert body["render_mode"] == "convert", key


async def test_the_probe_render_mode_ignores_the_declared_type(docs):
    """The client is told how to render by the same authority that decides what is
    served — otherwise the two could disagree and the viewer would frame HTML."""
    tenant_id, _schema, ids, _store = docs
    body = (await _probe(tenant_id, ids["html_typed"])).json()
    assert body["media_type"] == "application/pdf"
    assert body["render_mode"] == "pdf"


# --- The failure taxonomy -------------------------------------------------------------


async def test_a_released_original_is_permanent_and_distinct(docs):
    tenant_id, _schema, ids, _store = docs
    response = await _content(tenant_id, ids["released"])

    assert response.status_code == 410
    assert response.json()["detail"]["code"] == "ORIGINAL_RELEASED"


async def test_a_missing_object_is_distinct_from_a_released_one(docs):
    tenant_id, _schema, ids, _store = docs
    response = await _content(tenant_id, ids["missing"])

    assert response.json()["detail"]["code"] == "ORIGINAL_MISSING"
    assert response.json()["detail"]["code"] != "ORIGINAL_RELEASED"


async def test_a_source_with_no_adapter_is_a_configuration_fact(docs):
    tenant_id, _schema, ids, _store = docs
    response = await _content(tenant_id, ids["no_adapter"])

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "SOURCE_NOT_REOPENABLE"


async def test_an_unreachable_source_is_transient_and_distinct(docs, monkeypatch):
    """The distinction with product weight: a released original is permanent and the
    tenant's own policy; an unreachable source is worth retrying."""
    tenant_id, _schema, ids, _store = docs

    from src.document_service import content_resolution

    async def _failing(tenant, source_id, external_id):
        raise RuntimeError("remote refused")

    content_resolution.register_source_reopener("azure_blob", _failing)

    response = await _content(tenant_id, ids["source_only"])

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "SOURCE_UNAVAILABLE"
    assert response.json()["detail"]["code"] != "ORIGINAL_RELEASED"


async def test_a_source_only_document_is_served_from_its_adapter(docs):
    tenant_id, _schema, ids, store = docs

    from src.document_service import content_resolution

    async def _reopen(tenant, source_id, external_id):
        return b"%PDF-1.4 from azure"

    content_resolution.register_source_reopener("azure_blob", _reopen)
    before = list(store.opened)

    response = await _content(tenant_id, ids["source_only"])

    assert response.status_code == 200, response.text
    assert response.content == b"%PDF-1.4 from azure"
    assert store.opened == before, "a platform store was read for source-only content"


async def test_no_bytes_are_retained_after_a_source_only_view(docs):
    tenant_id, _schema, ids, store = docs

    from src.document_service import content_resolution

    async def _reopen(tenant, source_id, external_id):
        return b"%PDF-1.4 from azure"

    content_resolution.register_source_reopener("azure_blob", _reopen)
    await _content(tenant_id, ids["source_only"])

    assert store.objects.get(ids["source_only"]) is None
    assert not any(ids["source_only"] in ref for ref in store.objects)


async def test_existing_derived_data_survives_a_failed_view(docs, engine):
    tenant_id, schema, ids, _store = docs
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    await _content(tenant_id, ids["released"])
    await _content(tenant_id, ids["missing"])

    async with session_factory() as session:
        rows = (await session.execute(
            text(
                f"SELECT status, retention_mode FROM {schema}.documents "
                "WHERE id = ANY(:ids)"
            ),
            {"ids": [ids["released"], ids["missing"]]},
        )).fetchall()

    assert len(rows) == 2
    assert all(r.status == "processed" for r in rows), "a failed view changed a document's status"


# --- Startup registration (Risk 2) ----------------------------------------------------


def test_constructing_the_app_registers_the_pull_source_adapter():
    """The registry is filled as an import side effect. This process never imported the
    adapter before this change, so every source-only document — which is every document
    the Azure sync produces — reported as unreadable, looking like a viewer bug."""
    from src.document_service import content_resolution
    from src.document_service.main import _register_source_adapters

    _register_source_adapters()
    assert content_resolution.has_source_reopener("azure_blob")


def test_registration_is_guarded_so_a_missing_sdk_does_not_stop_startup(monkeypatch):
    """Degrading to 'this source cannot be re-read' is correct in a deployment without
    pull sources; refusing to start the document service is not."""
    import builtins

    from src.document_service.main import _register_source_adapters

    real_import = builtins.__import__

    def _explode(name, *args, **kwargs):
        if "blob_sync.reopen" in name:
            raise ImportError("azure sdk absent")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _explode)
    _register_source_adapters()  # must not raise
