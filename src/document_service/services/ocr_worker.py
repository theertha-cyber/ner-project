import asyncio
import traceback
import uuid
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker
from src.shared.database import get_engine
from src.shared.retrieval import Chunk, chunk_text as _shared_chunk_text
from src.shared.tenant_schema import schema_for_tenant as _schema
from src.shared.document_retention import (
    RETENTION_EPHEMERAL,
    RETENTION_PLATFORM_BLOB,
    RETENTION_SOURCE_ONLY,
)


async def _embed_chunks(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    from src.chat_api.services.embedding_service import EmbeddingService
    return await EmbeddingService().embed_batch(texts)


async def _store_chunks(document_id: str, tenant_id: str, chunks: list[Chunk], embeddings: list[list[float]], purpose: str):
    engine = get_engine()
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    schema = _schema(tenant_id)
    async with session_factory() as session:
        for i, chunk in enumerate(chunks):
            emb_str = "[" + ",".join(str(v) for v in embeddings[i]) + "]" if i < len(embeddings) else None
            await session.execute(
                text(f"""
                    INSERT INTO {schema}.document_chunks
                        (id, document_id, chunk_index, chunk_text, embedding, page_number, char_start, char_end, purpose)
                    VALUES (:id, :doc_id, :chunk_index, :chunk_text, CAST(:embedding AS vector), :page_number, :char_start, :char_end, :purpose)
                """),
                {
                    "id": str(uuid.uuid4()),
                    "doc_id": document_id,
                    "chunk_index": chunk.chunk_index,
                    "chunk_text": chunk.chunk_text,
                    "embedding": emb_str,
                    "page_number": chunk.page_number,
                    "char_start": chunk.char_start,
                    "char_end": chunk.char_end,
                    "purpose": purpose,
                },
            )
        await session.commit()


ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".tif", ".tiff"}

# Rasterisation resolution for scanned PDFs; 200 DPI is the accuracy/speed knee
# for tesseract on typical document scans.
OCR_DPI = 200


def get_extension(filename: str) -> str:
    dot = filename.rfind(".")
    if dot == -1:
        return ""
    return filename[dot:].lower()


def is_allowed_file(filename: str) -> bool:
    return get_extension(filename) in ALLOWED_EXTENSIONS


def extract_text_pdf(file_bytes: bytes) -> list[dict]:
    import fitz
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    spans = []
    char_offset = 0
    for page_num, page in enumerate(doc):
        text = page.get_text()
        spans.append({
            "span_index": page_num,
            "text": text,
            "char_start": char_offset,
            "char_end": char_offset + len(text),
            "page_number": page_num,
        })
        char_offset += len(text) + 1
    doc.close()
    return spans


_TESSERACT_HINT = (
    "OCR engine unavailable. The 'tesseract' binary and the pytesseract "
    "package are both required for image and scanned-PDF text extraction."
)


def _ocr_image(image) -> str:
    """Run tesseract on a single PIL image, normalising it first."""
    try:
        import pytesseract
    except ImportError as exc:  # pragma: no cover - depends on runtime image
        raise RuntimeError(_TESSERACT_HINT) from exc

    from pytesseract import TesseractNotFoundError

    if image.mode not in ("L", "RGB"):
        image = image.convert("RGB")
    try:
        return pytesseract.image_to_string(image)
    except TesseractNotFoundError as exc:
        raise RuntimeError(_TESSERACT_HINT) from exc


def extract_text_image(file_bytes: bytes) -> list[dict]:
    """OCR a raster image. Multi-frame TIFFs yield one span per frame."""
    from PIL import Image, ImageSequence
    import io

    image = Image.open(io.BytesIO(file_bytes))
    spans = []
    char_offset = 0
    for frame_num, frame in enumerate(ImageSequence.Iterator(image)):
        text = _ocr_image(frame)
        spans.append({
            "span_index": frame_num,
            "text": text,
            "char_start": char_offset,
            "char_end": char_offset + len(text),
            "page_number": frame_num,
        })
        char_offset += len(text) + 1
    image.close()
    return spans


def extract_text_pdf_as_image(file_bytes: bytes) -> list[dict]:
    """OCR a scanned PDF by rasterising pages with PyMuPDF (no poppler needed)."""
    import fitz
    from PIL import Image
    import io

    doc = fitz.open(stream=file_bytes, filetype="pdf")
    spans = []
    char_offset = 0
    try:
        for page_num, page in enumerate(doc):
            pixmap = page.get_pixmap(dpi=OCR_DPI)
            image = Image.open(io.BytesIO(pixmap.tobytes("png")))
            text = _ocr_image(image)
            image.close()
            spans.append({
                "span_index": page_num,
                "text": text,
                "char_start": char_offset,
                "char_end": char_offset + len(text),
                "page_number": page_num,
            })
            char_offset += len(text) + 1
    finally:
        doc.close()
    return spans


# --- Media-type resolution -------------------------------------------------------------

MEDIA_TYPE_PDF = "application/pdf"
IMAGE_MEDIA_TYPES = frozenset({"image/jpeg", "image/png", "image/tiff"})

# Types a client sends when it does not know or does not care. Treating one of these as
# authoritative would reroute real documents, so they fall through to the next step.
_UNINFORMATIVE_MEDIA_TYPES = frozenset(
    {"", "application/octet-stream", "binary/octet-stream", "*/*"}
)

_EXTENSION_MEDIA_TYPES = {
    ".pdf": MEDIA_TYPE_PDF,
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".tif": "image/tiff",
    ".tiff": "image/tiff",
}

_MAGIC_PREFIXES = (
    (b"%PDF", MEDIA_TYPE_PDF),
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"II*\x00", "image/tiff"),
    (b"MM\x00*", "image/tiff"),
)


def _media_type_from_declaration(declared: str | None) -> str | None:
    if not declared:
        return None
    value = declared.split(";")[0].strip().lower()
    if value in _UNINFORMATIVE_MEDIA_TYPES:
        return None
    if value == MEDIA_TYPE_PDF or value in IMAGE_MEDIA_TYPES:
        return value
    # Aliases real clients send.
    if value in ("image/jpg", "image/pjpeg"):
        return "image/jpeg"
    if value in ("image/x-tiff", "image/tif"):
        return "image/tiff"
    return None


def _media_type_from_filename(filename: str | None) -> str | None:
    return _EXTENSION_MEDIA_TYPES.get(get_extension(filename or ""))


def _media_type_from_content(data: bytes | None) -> str | None:
    if not data:
        return None
    for prefix, media_type in _MAGIC_PREFIXES:
        if data.startswith(prefix):
            return media_type
    return None


def resolve_media_type(
    declared: str | None, filename: str | None, data: bytes | None
) -> str | None:
    """Declared type, then filename extension, then a content sniff.

    Never the storage reference. The extension remains the fallback, which is what the
    worker used before this change, so a PDF uploaded as `application/octet-stream`
    resolves exactly as it always did.
    """
    for candidate in (
        _media_type_from_declaration(declared),
        _media_type_from_filename(filename),
        _media_type_from_content(data),
    ):
        if candidate:
            return candidate
    return None


# --- Content resolution ----------------------------------------------------------------


class ContentUnresolvable(Exception):
    """The document's bytes cannot be obtained under its recorded retention mode."""


class SourceOnlyNotSupported(ContentUnresolvable):
    """`source_only` resolution needs a reopenable source adapter.

    None exists yet; the pull-side contract arrives with `external-document-sources`.
    Raised explicitly rather than silently treated as "the bytes are gone", because the
    two are different facts and an operator needs to tell them apart.
    """


def _store_for(retention_mode: str):
    # Imported at call time so the worker and the content store can depend on each other's
    # packages without an import cycle at module load.
    from src.document_service.content_store import get_durable_store, get_working_store

    if retention_mode == RETENTION_EPHEMERAL:
        return get_working_store()
    return get_durable_store()


def resolve_content(document) -> bytes | None:
    """Obtain the bytes implied by the document's recorded retention mode.

    The recorded value decides — never a re-derivation, and never the shape of the
    reference. Returns None when the resolution is well defined but the bytes are gone.
    """
    retention_mode = getattr(document, "retention_mode", None) or RETENTION_PLATFORM_BLOB
    if retention_mode == RETENTION_SOURCE_ONLY:
        raise SourceOnlyNotSupported(
            "source_only retention requires a reopenable source adapter, "
            "which this change does not implement"
        )
    reference = getattr(document, "blob_path", None)
    if not reference:
        return None
    return _store_for(retention_mode).open(reference)


# --- Processing ------------------------------------------------------------------------

_DOCUMENT_COLUMNS = "id, purpose, status, content_type, filename, blob_path, retention_mode"


async def _load_document(session, schema: str, document_id: str):
    result = await session.execute(
        text(f"SELECT {_DOCUMENT_COLUMNS} FROM {schema}.documents WHERE id = :id"),
        {"id": document_id},
    )
    return result.fetchone()


async def _release_working_copy(session_factory, schema: str, document) -> None:
    """At a terminal state an ephemeral document's working copy goes, and the row stops
    naming it in the same step, so the reference and the object cannot disagree."""
    if (getattr(document, "retention_mode", None) or "") != RETENTION_EPHEMERAL:
        return
    reference = getattr(document, "blob_path", None)
    if reference:
        try:
            _store_for(RETENTION_EPHEMERAL).delete(reference)
        except Exception:
            # The working store's own expiry is the backstop. A failed delete must not
            # turn a processed document into a failed one.
            traceback.print_exc()
    async with session_factory() as session:
        await session.execute(
            text(f"UPDATE {schema}.documents SET blob_path = NULL WHERE id = :id"),
            {"id": document.id},
        )
        await session.commit()


async def _purge_derived_data(session_factory, schema: str, document_id: str) -> None:
    """Scoped by document id only, so reprocessing one document cannot touch another."""
    async with session_factory() as session:
        await session.execute(
            text(f"DELETE FROM {schema}.document_chunks WHERE document_id = :id"),
            {"id": document_id},
        )
        await session.execute(
            text(f"DELETE FROM {schema}.document_text_spans WHERE document_id = :id"),
            {"id": document_id},
        )
        await session.commit()


async def process_document(document_id: str, tenant_id: str, *, reprocess: bool = False):
    """Process a document from its identity alone.

    Everything else — where the bytes are, what they are, what the document is for — is
    read from persisted state, so a dispatch is replayable after a restart or through a
    queue.
    """
    engine = get_engine()
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    schema = _schema(tenant_id)

    async with session_factory() as session:
        try:
            document = await _load_document(session, schema, document_id)
        except Exception:
            await session.rollback()
            return
    if document is None:
        return

    purpose = document.purpose or "query"

    if not reprocess:
        # Claim the document. A repeated dispatch finds it already out of `pending` and
        # does no work, so a second delivery cannot duplicate an extraction.
        async with session_factory() as session:
            try:
                claimed = await session.execute(
                    text(
                        f"UPDATE {schema}.documents SET status = 'processing' "
                        f"WHERE id = :id AND status = 'pending'"
                    ),
                    {"id": document_id},
                )
                await session.commit()
            except Exception:
                await session.rollback()
                return
        if claimed.rowcount == 0:
            return

    # Resolve before purging. Purge-then-fetch would destroy a document's derived data
    # whenever the bytes turn out to be gone, converting a recoverable state into
    # permanent loss.
    try:
        file_data = resolve_content(document)
    except ContentUnresolvable:
        if reprocess:
            raise
        file_data = None

    if file_data is None:
        if reprocess:
            # The document processed successfully once; its spans, chunks and citations
            # remain valid. Fail the request and change nothing.
            raise ContentUnresolvable(
                f"Document {document_id} cannot be reprocessed: its bytes are no longer "
                f"resolvable under '{document.retention_mode}' retention"
            )
        async with session_factory() as session:
            await session.execute(
                text(f"UPDATE {schema}.documents SET status = 'failed', error_message = :msg WHERE id = :id"),
                {"id": document_id, "msg": "File not found in storage"},
            )
            await session.commit()
        await _release_working_copy(session_factory, schema, document)
        return

    if reprocess:
        await _purge_derived_data(session_factory, schema, document_id)
        async with session_factory() as session:
            await session.execute(
                text(f"UPDATE {schema}.documents SET status = 'processing' WHERE id = :id"),
                {"id": document_id},
            )
            await session.commit()

    try:
        media_type = resolve_media_type(document.content_type, document.filename, file_data)
        if media_type == MEDIA_TYPE_PDF:
            spans = await asyncio.to_thread(extract_text_pdf, file_data)
            if not spans or all(not s["text"].strip() for s in spans):
                spans = await asyncio.to_thread(extract_text_pdf_as_image, file_data)
        elif media_type in IMAGE_MEDIA_TYPES:
            spans = await asyncio.to_thread(extract_text_image, file_data)
        else:
            raise ValueError(f"Unsupported media type: {media_type or 'unresolved'}")

        async with session_factory() as session:
            for span in spans:
                span_id = str(uuid.uuid4())
                await session.execute(
                    text(f"""
                        INSERT INTO {schema}.document_text_spans (id, document_id, span_index, text, char_start, char_end, page_number)
                        VALUES (:id, :doc_id, :span_index, :text, :char_start, :char_end, :page_number)
                    """),
                    {
                        "id": span_id,
                        "doc_id": document_id,
                        "span_index": span["span_index"],
                        "text": span["text"],
                        "char_start": span["char_start"],
                        "char_end": span["char_end"],
                        "page_number": span["page_number"],
                    },
                )

            await session.execute(
                text(f"UPDATE {schema}.documents SET status = 'processed' WHERE id = :id"),
                {"id": document_id},
            )
            await session.commit()

        # Only query documents feed retrieval. Training documents stop after text
        # spans are stored: they are annotated/extracted, never embedded.
        if purpose != "query":
            await _release_working_copy(session_factory, schema, document)
            return

        try:
            chunks: list[Chunk] = []
            for span in spans:
                span_chunks = _shared_chunk_text(
                    span["text"],
                    page_number=span["page_number"],
                    char_start=span["char_start"],
                )
                for c in span_chunks:
                    chunks.append(Chunk(
                        chunk_index=len(chunks),
                        chunk_text=c.chunk_text,
                        page_number=c.page_number,
                        char_start=c.char_start,
                        char_end=c.char_end,
                    ))
            if chunks:
                texts = [c.chunk_text for c in chunks]
                embeddings = await _embed_chunks(texts)
                await _store_chunks(document_id, tenant_id, chunks, embeddings, purpose)
        except Exception as chunk_err:
            traceback.print_exc()

        await _release_working_copy(session_factory, schema, document)

    except Exception as exc:
        error_msg = f"{type(exc).__name__}: {str(exc)}"
        traceback.print_exc()
        async with session_factory() as session:
            await session.execute(
                text(f"UPDATE {schema}.documents SET status = 'failed', error_message = :msg WHERE id = :id"),
                {"id": document_id, "msg": error_msg},
            )
            await session.commit()
        await _release_working_copy(session_factory, schema, document)


def trigger_ocr(document_id: str, tenant_id: str):
    """Dispatch by identity only. No bytes, no storage reference, no media type."""
    asyncio.create_task(process_document(document_id, tenant_id))
