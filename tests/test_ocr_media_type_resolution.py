"""Verification for media-type resolution — part of verification.md rows 72-81.

The extractor used to be chosen by splitting the MinIO object key. It is now chosen from
the document's resolved media type, in a fixed order: declared type, then filename
extension, then a content sniff. The order is the whole safety property — dropping the
filename fallback would reroute every `application/octet-stream` upload, which is common
in practice.
"""

import inspect
import os

import pytest

os.environ.setdefault("NER_JWT_SECRET", "test-secret-do-not-use-in-prod")

from src.document_service.services.ocr_worker import (
    IMAGE_MEDIA_TYPES,
    MEDIA_TYPE_PDF,
    resolve_media_type,
)

PDF_BYTES = b"%PDF-1.4 fixture"
PNG_BYTES = b"\x89PNG\r\n\x1a\nfixture"
JPEG_BYTES = b"\xff\xd8\xff\xe0fixture"
TIFF_BYTES = b"II*\x00fixture"


# --- Step 1: a specific declared type wins ---------------------------------------------


def test_declared_media_type_selects_the_extractor():
    # The reference ends in `.bin`; it is not consulted, and must not be.
    assert resolve_media_type("image/png", "object.bin", PDF_BYTES) == "image/png"


def test_declared_type_survives_a_charset_parameter():
    assert resolve_media_type("application/pdf; charset=binary", None, None) == MEDIA_TYPE_PDF


@pytest.mark.parametrize(
    "declared,expected",
    [("image/jpg", "image/jpeg"), ("image/pjpeg", "image/jpeg"), ("image/tif", "image/tiff")],
)
def test_common_client_aliases_resolve(declared, expected):
    assert resolve_media_type(declared, None, None) == expected


# --- Step 2: the filename extension is the fallback ------------------------------------


@pytest.mark.parametrize("generic", ["application/octet-stream", "", None, "*/*"])
def test_generic_declared_type_falls_back_to_the_filename(generic):
    """This is today's behaviour, preserved exactly."""
    assert resolve_media_type(generic, "report.pdf", None) == MEDIA_TYPE_PDF
    assert resolve_media_type(generic, "scan.PNG", None) == "image/png"


def test_an_unknown_declared_type_falls_back_rather_than_failing():
    assert resolve_media_type("text/plain", "report.pdf", None) == MEDIA_TYPE_PDF


# --- Step 3: content sniff is the last resort ------------------------------------------


@pytest.mark.parametrize(
    "data,expected",
    [
        (PDF_BYTES, MEDIA_TYPE_PDF),
        (PNG_BYTES, "image/png"),
        (JPEG_BYTES, "image/jpeg"),
        (TIFF_BYTES, "image/tiff"),
    ],
)
def test_content_sniff_resolves_when_nothing_is_declared_or_named(data, expected):
    assert resolve_media_type(None, "object", data) == expected


def test_unresolvable_media_type_is_none_not_a_guess():
    assert resolve_media_type(None, "object", b"not a known magic number") is None


# --- The order itself -------------------------------------------------------------------


def test_resolution_order_is_declared_then_filename_then_content():
    # All three disagree: the declared type must win.
    assert resolve_media_type("image/png", "report.pdf", PDF_BYTES) == "image/png"
    # Declared is generic: the filename wins over the content.
    assert resolve_media_type("application/octet-stream", "scan.png", PDF_BYTES) == "image/png"
    # Neither declared nor named: the content decides.
    assert resolve_media_type(None, "object", PNG_BYTES) == "image/png"


def test_the_image_media_types_are_the_ones_the_image_extractor_handles():
    assert IMAGE_MEDIA_TYPES == frozenset({"image/jpeg", "image/png", "image/tiff"})


# --- The reference is never parsed -------------------------------------------------------


def test_resolution_never_receives_or_consults_a_storage_reference():
    from src.document_service.services import ocr_worker

    signature = inspect.signature(resolve_media_type)
    assert list(signature.parameters) == ["declared", "filename", "data"]

    body = inspect.getsource(ocr_worker.process_document)
    # The old implementation was `blob_path.split(".")`.
    assert "blob_path.split" not in body
    assert ".split(\".\")" not in body


# =========================================================================================
# Worker behaviour against a real schema — verification.md rows 75-81 and 41-42.
# =========================================================================================

from sqlalchemy import text  # noqa: E402

from src.document_service.ingestion import (  # noqa: E402
    ContentAccess,
    DocumentIngestionService,
    RecordingDispatcher,
)
from src.document_service.services import ocr_worker  # noqa: E402
from src.shared.document_retention import RETENTION_EPHEMERAL  # noqa: E402

from tests.test_ingestion_boundary import (  # noqa: E402
    PDF_CONTENT,
    FakeStore,
    normalized,
    session_factory,  # noqa: F401
    set_retention,
    tenant,  # noqa: F401
)

PAGE_TEXT = "Worker behaviour fixture text. " * 5


def _stub_extraction(monkeypatch, store, *, raises=False):
    """Replace the extractors and the store lookup; record whether the image path ran."""

    def extract(data):
        if raises:
            raise ValueError("corrupt document")
        return [
            {
                "span_index": 0,
                "text": PAGE_TEXT,
                "char_start": 0,
                "char_end": len(PAGE_TEXT),
                "page_number": 0,
            }
        ]

    image_calls = []

    def extract_image(data):
        image_calls.append(data)
        return extract(data)

    monkeypatch.setattr(ocr_worker, "extract_text_pdf", extract)
    monkeypatch.setattr(ocr_worker, "extract_text_pdf_as_image", extract)
    monkeypatch.setattr(ocr_worker, "extract_text_image", extract_image)
    monkeypatch.setattr(ocr_worker, "_store_for", lambda mode: store)

    async def fake_embed(texts):
        return [[0.0] * 4 for _ in texts]

    monkeypatch.setattr(ocr_worker, "_embed_chunks", fake_embed)
    return image_calls


async def _ingest(session_factory, tenant_id, store, **overrides):
    service = DocumentIngestionService(
        dispatcher=RecordingDispatcher(), durable_store=store, working_store=store
    )
    async with session_factory() as session:
        return await service.ingest(session, normalized(tenant_id, **overrides))


async def _counts(session_factory, schema, document_id):
    async with session_factory() as session:
        spans = (
            await session.execute(
                text(
                    f"SELECT COUNT(*) FROM {schema}.document_text_spans "
                    f"WHERE document_id = :id"
                ),
                {"id": document_id},
            )
        ).scalar()
        chunks = (
            await session.execute(
                text(
                    f"SELECT COUNT(*) FROM {schema}.document_chunks WHERE document_id = :id"
                ),
                {"id": document_id},
            )
        ).scalar()
    return spans, chunks


async def _status(session_factory, schema, document_id):
    async with session_factory() as session:
        return (
            await session.execute(
                text(f"SELECT status FROM {schema}.documents WHERE id = :id"),
                {"id": document_id},
            )
        ).scalar()


# --- Row 75: the worker resolves bytes from persisted state alone ----------------------


@pytest.mark.asyncio
async def test_row_75_the_worker_resolves_from_persisted_state(
    tenant, session_factory, monkeypatch
):
    # Dispatch carries identity; `reprocess` is a caller's explicit intent, never part of
    # a dispatched job.
    parameters = list(inspect.signature(ocr_worker.process_document).parameters)
    assert parameters == ["document_id", "tenant_id", "reprocess"]

    store = FakeStore()
    _stub_extraction(monkeypatch, store)
    result = await _ingest(session_factory, tenant["tenant_id"], store)

    await ocr_worker.process_document(result.document_id, tenant["tenant_id"])

    assert await _status(session_factory, tenant["schema"], result.document_id) == "processed"
    assert store.opens == [result.storage_reference]


# --- Rows 76 and 77: the extractor follows the resolved media type ---------------------


@pytest.mark.asyncio
async def test_row_76_declared_media_type_selects_the_image_extractor(
    tenant, session_factory, monkeypatch
):
    store = FakeStore()
    image_calls = _stub_extraction(monkeypatch, store)
    result = await _ingest(
        session_factory,
        tenant["tenant_id"],
        store,
        filename="scan.png",
        declared_media_type="image/png",
        content=ContentAccess.from_bytes(b"\x89PNG\r\n\x1a\nfixture bytes"),
    )

    await ocr_worker.process_document(result.document_id, tenant["tenant_id"])

    assert image_calls, "the image extractor was not selected"
    assert await _status(session_factory, tenant["schema"], result.document_id) == "processed"


@pytest.mark.asyncio
async def test_row_77_octet_stream_falls_back_to_the_filename(
    tenant, session_factory, monkeypatch
):
    """The common real case: a PDF uploaded as `application/octet-stream`."""
    store = FakeStore()
    image_calls = _stub_extraction(monkeypatch, store)
    result = await _ingest(
        session_factory,
        tenant["tenant_id"],
        store,
        filename="report.pdf",
        declared_media_type="application/octet-stream",
    )

    await ocr_worker.process_document(result.document_id, tenant["tenant_id"])

    assert image_calls == [], "an octet-stream PDF was routed to the image extractor"
    assert await _status(session_factory, tenant["schema"], result.document_id) == "processed"
    spans, _ = await _counts(session_factory, tenant["schema"], result.document_id)
    assert spans > 0


# --- Row 78: a repeated dispatch performs no second extraction -------------------------


@pytest.mark.asyncio
async def test_row_78_repeated_dispatch_performs_no_second_extraction(
    tenant, session_factory, monkeypatch
):
    store = FakeStore()
    _stub_extraction(monkeypatch, store)
    result = await _ingest(session_factory, tenant["tenant_id"], store)

    await ocr_worker.process_document(result.document_id, tenant["tenant_id"])
    before = await _counts(session_factory, tenant["schema"], result.document_id)
    opens_before = len(store.opens)

    # The same job delivered again. The document is no longer `pending`, so the
    # conditional claim matches nothing and no work runs.
    await ocr_worker.process_document(result.document_id, tenant["tenant_id"])

    after = await _counts(session_factory, tenant["schema"], result.document_id)
    assert after == before, "a repeated dispatch duplicated derived data"
    assert len(store.opens) == opens_before, "a repeated dispatch re-read the bytes"


# --- Row 79: reprocessing does not duplicate ------------------------------------------


@pytest.mark.asyncio
async def test_row_79_reprocessing_does_not_duplicate_spans_or_chunks(
    tenant, session_factory, monkeypatch
):
    store = FakeStore()
    _stub_extraction(monkeypatch, store)
    result = await _ingest(session_factory, tenant["tenant_id"], store, purpose="query")

    await ocr_worker.process_document(result.document_id, tenant["tenant_id"])
    single_run = await _counts(session_factory, tenant["schema"], result.document_id)
    assert single_run[0] > 0 and single_run[1] > 0

    await ocr_worker.process_document(
        result.document_id, tenant["tenant_id"], reprocess=True
    )
    assert await _counts(session_factory, tenant["schema"], result.document_id) == single_run


# --- Row 80: reprocessing one document does not affect another -------------------------


@pytest.mark.asyncio
async def test_row_80_reprocessing_one_document_leaves_the_other_untouched(
    tenant, session_factory, monkeypatch
):
    store = FakeStore()
    _stub_extraction(monkeypatch, store)
    first = await _ingest(session_factory, tenant["tenant_id"], store, purpose="query")
    second = await _ingest(
        session_factory,
        tenant["tenant_id"],
        store,
        purpose="query",
        content=ContentAccess.from_bytes(PDF_CONTENT + b" second document"),
    )

    for result in (first, second):
        await ocr_worker.process_document(result.document_id, tenant["tenant_id"])

    untouched_before = await _counts(session_factory, tenant["schema"], second.document_id)
    assert untouched_before[0] > 0

    await ocr_worker.process_document(
        first.document_id, tenant["tenant_id"], reprocess=True
    )

    untouched_after = await _counts(session_factory, tenant["schema"], second.document_id)
    assert untouched_after == untouched_before
    assert await _status(session_factory, tenant["schema"], second.document_id) == "processed"


# --- Row 81: derived data survives an unresolvable reprocess ---------------------------


@pytest.mark.asyncio
async def test_row_81_derived_data_is_not_deleted_when_bytes_cannot_be_resolved(
    tenant, session_factory, monkeypatch
):
    """Purge-then-fetch would turn a recoverable state into permanent loss. The ordering
    is the whole mitigation, so this asserts the purge never happened."""
    store = FakeStore()
    _stub_extraction(monkeypatch, store)
    result = await _ingest(session_factory, tenant["tenant_id"], store, purpose="query")
    await ocr_worker.process_document(result.document_id, tenant["tenant_id"])

    before = await _counts(session_factory, tenant["schema"], result.document_id)
    assert before[0] > 0

    # The bytes go; the row still names them.
    store.objects.clear()

    with pytest.raises(ocr_worker.ContentUnresolvable):
        await ocr_worker.process_document(
            result.document_id, tenant["tenant_id"], reprocess=True
        )

    assert await _counts(session_factory, tenant["schema"], result.document_id) == before
    assert await _status(session_factory, tenant["schema"], result.document_id) == "processed"


# --- Rows 41-42 (task 4.8): the storage reference is opaque ----------------------------


def test_row_41_ocr_never_parses_the_storage_reference():
    source = inspect.getsource(ocr_worker)
    for forbidden in (
        "blob_path.split",
        "reference.split",
        "blob_path.endswith",
        "reference.endswith",
        "blob_path.rfind",
    ):
        assert forbidden not in source, f"the worker parses the reference: {forbidden}"

    # Extractor selection derives from the resolved media type and from nothing else.
    body = inspect.getsource(ocr_worker.process_document)
    assert "resolve_media_type(" in body
    assert "media_type == MEDIA_TYPE_PDF" in body


@pytest.mark.asyncio
async def test_row_42_processing_succeeds_for_a_document_with_no_durable_reference(
    tenant, session_factory, monkeypatch
):
    """An `ephemeral` document has no durable original at all; it processes from the
    working copy that the recorded resolution names."""
    await set_retention(session_factory, tenant["tenant_id"], RETENTION_EPHEMERAL)
    durable, working = FakeStore(), FakeStore()
    _stub_extraction(monkeypatch, working)
    monkeypatch.setattr(
        ocr_worker,
        "_store_for",
        lambda mode: working if mode == RETENTION_EPHEMERAL else durable,
    )

    service = DocumentIngestionService(
        dispatcher=RecordingDispatcher(), durable_store=durable, working_store=working
    )
    async with session_factory() as session:
        result = await service.ingest(session, normalized(tenant["tenant_id"]))

    assert durable.puts == [], "an ephemeral document reached the durable store"
    await ocr_worker.process_document(result.document_id, tenant["tenant_id"])

    assert await _status(session_factory, tenant["schema"], result.document_id) == "processed"
    assert durable.opens == []
