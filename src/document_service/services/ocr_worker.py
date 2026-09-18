import asyncio
import logging
import uuid
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker
from src.shared.database import get_engine, get_resolver
from src.shared.retrieval import Chunk, chunk_text as _shared_chunk_text
from src.shared.tenant_schema import schema_for_tenant as _schema
from src.shared.document_retention import (
    RETENTION_EPHEMERAL,
    RETENTION_PLATFORM_BLOB,
    RETENTION_SOURCE_ONLY,
)

logger = logging.getLogger(__name__)


# --- Safe structured processing-error classes (CAP-3) ----------------------------------
#
# Failure records (log lines, document error fields, metrics, traces) carry only
# these finite classes plus correlation metadata. No stack-trace printing, no
# interpolated exception message, no exception object: a driver error quotes the
# offending literal back, so the message itself is untrusted content.

PROCESSING_ERROR_CONTENT_UNRESOLVABLE = "content_unresolvable"
PROCESSING_ERROR_UNSUPPORTED_MEDIA = "unsupported_media"
PROCESSING_ERROR_CHUNKING_FAILED = "chunking_failed"
PROCESSING_ERROR_PROCESSING_FAILED = "processing_failed"

PROCESSING_ERROR_CLASSES = frozenset({
    PROCESSING_ERROR_CONTENT_UNRESOLVABLE,
    PROCESSING_ERROR_UNSUPPORTED_MEDIA,
    PROCESSING_ERROR_CHUNKING_FAILED,
    PROCESSING_ERROR_PROCESSING_FAILED,
})


class UnsupportedMediaType(ValueError):
    """The resolved media type has no extraction path. A ValueError subclass so
    existing handlers keep working; classified to a finite class at the edge."""


def classify_processing_error(exc: BaseException) -> str:
    if isinstance(exc, ContentUnresolvable):
        return PROCESSING_ERROR_CONTENT_UNRESOLVABLE
    if isinstance(exc, UnsupportedMediaType):
        return PROCESSING_ERROR_UNSUPPORTED_MEDIA
    return PROCESSING_ERROR_PROCESSING_FAILED


# --- Source-content reopeners (CAP-3) ---------------------------------------------------
#
# `source_only` retention stores no bytes, so processing re-acquires them through
# a registered per-source-type reopener. The registry (not imports) connects the
# worker to source runtimes: `blob_sync.reopen` registers the Azure Blob
# reopener, and with none registered the worker raises exactly as before.

_SOURCE_REOPENERS: dict = {}


def register_source_reopener(source_type: str, reopen) -> None:
    _SOURCE_REOPENERS[source_type] = reopen


async def _reopen_source_content(document, tenant_id: str):
    source_type = getattr(document, "source_type", None)
    reopen = _SOURCE_REOPENERS.get(source_type)
    if reopen is None:
        return None
    try:
        return await reopen(
            tenant_id,
            getattr(document, "source_id", None),
            getattr(document, "external_id", None),
        )
    except Exception as exc:
        logger.info(
            "source_reopen_failed",
            extra={"error_class": classify_processing_error(exc)},
        )
        return None


async def _resolve_content_for_processing(document, tenant_id: str):
    """Resolve bytes, re-acquiring source-only content through its reopener.

    Anything unresolvable raises `ContentUnresolvable`, exactly as
    `resolve_content` does when no reopener can supply the bytes.
    """
    retention_mode = getattr(document, "retention_mode", None) or RETENTION_PLATFORM_BLOB
    if retention_mode == RETENTION_SOURCE_ONLY:
        reopened = await _reopen_source_content(document, tenant_id)
        if reopened is not None:
            return reopened
    return resolve_content(document)


async def _embed_chunks(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    from src.chat_api.services.embedding_service import EmbeddingService
    return await EmbeddingService().embed_batch(texts)


async def _store_chunks(
    document_id: str,
    tenant_id: str,
    chunks: list[Chunk],
    embeddings: list[list[float]],
    purpose: str,
    conversation_id: str | None = None,
    uploaded_by: str | None = None,
    ingested_by_kind: str | None = None,
):
    engine = await get_resolver().resolve(tenant_id)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    schema = _schema(tenant_id)
    async with session_factory() as session:
        for i, chunk in enumerate(chunks):
            emb_str = "[" + ",".join(str(v) for v in embeddings[i]) + "]" if i < len(embeddings) else None
            await session.execute(
                text(f"""
                    INSERT INTO {schema}.document_chunks
                        (id, document_id, chunk_index, chunk_text, embedding, page_number, char_start, char_end, purpose, conversation_id, uploaded_by, ingested_by_kind)
                    VALUES (:id, :doc_id, :chunk_index, :chunk_text, CAST(:embedding AS vector), :page_number, :char_start, :char_end, :purpose, :conversation_id, :uploaded_by, :ingested_by_kind)
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
                    # Denormalized from the parent document so retrieval can decide
                    # conversation visibility from the chunk row alone (ADR-014).
                    "conversation_id": conversation_id,
                    # Denormalized for the same reason and on the same terms: every
                    # answer channel evaluates the uploader-visibility rule per chunk,
                    # and a join to `documents` would sit between the hnsw index scan
                    # and the vector ranking. Both values are immutable after
                    # ingestion, so the copy cannot drift. `ingested_by_kind` falls
                    # back to the source-system value rather than to 'human': an
                    # unknown actor must not be attributed to a person, because that
                    # person would be the only user who could then see it.
                    "uploaded_by": uploaded_by,
                    "ingested_by_kind": ingested_by_kind or "source_system",
                },
            )
        await session.commit()


ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".tif", ".tiff", ".doc", ".docx", ".csv"}

# Rasterisation resolution for scanned PDFs; 200 DPI is the accuracy/speed knee
# for tesseract on typical document scans.
OCR_DPI = 200

# Q&A-pair documents are guidance text, not scanned pages, so they additionally accept the
# text-bearing office formats a team is likely to have written one in. `.doc` (the legacy
# binary format) is deliberately excluded: it cannot be parsed without a heavyweight
# dependency, and asking for a re-save as .docx/.pdf/.txt is the honest failure.
QA_PAIR_EXTRA_EXTENSIONS = {".txt", ".docx"}
QA_PAIR_ALLOWED_EXTENSIONS = (ALLOWED_EXTENSIONS - {".doc"}) | QA_PAIR_EXTRA_EXTENSIONS


def get_extension(filename: str) -> str:
    dot = filename.rfind(".")
    if dot == -1:
        return ""
    return filename[dot:].lower()


def is_allowed_file(filename: str, purpose: str | None = None) -> bool:
    allowed = QA_PAIR_ALLOWED_EXTENSIONS if purpose == "qa_pair" else ALLOWED_EXTENSIONS
    return get_extension(filename) in allowed


def extract_text_pdf(file_bytes: bytes) -> list[dict]:
    """Rasterise every page and OCR it with Tesseract — one span per page.

    PyMuPDF's text-layer extraction is deliberately not used: its default reader inserts
    layout-driven whitespace and keeps line-break hyphenation, which breaks the exact-match
    grounding the automated-annotation and schema-proposal paths rely on. OCR of a clean
    300-DPI render gives text closer to what a reader sees.
    """
    from pdf2image import convert_from_bytes
    import pytesseract

    images = convert_from_bytes(file_bytes, dpi=300)
    spans = []
    char_offset = 0
    for page_num, image in enumerate(images):
        page_text = pytesseract.image_to_string(image)
        spans.append({
            "span_index": page_num,
            "text": page_text,
            "char_start": char_offset,
            "char_end": char_offset + len(page_text),
            "page_number": page_num,
        })
        char_offset += len(page_text) + 1
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


def extract_text_docx(file_bytes: bytes) -> list[dict]:
    """Extract paragraph text from a DOCX document."""
    import io
    from docx import Document

    document = Document(io.BytesIO(file_bytes))
    extracted = "\n".join(
        paragraph.text for paragraph in document.paragraphs if paragraph.text.strip()
    )
    return [{
        "span_index": 0,
        "text": extracted,
        "char_start": 0,
        "char_end": len(extracted),
        "page_number": 0,
    }]


def extract_text_doc(file_bytes: bytes) -> list[dict]:
    """Extract legacy DOC text through the optional antiword executable."""
    import os
    import subprocess
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".doc", delete=False) as temporary_file:
        temporary_file.write(file_bytes)
        temporary_path = temporary_file.name
    try:
        result = subprocess.run(
            ["antiword", temporary_path],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except FileNotFoundError as exc:
        raise RuntimeError("antiword is not installed") from exc
    finally:
        os.unlink(temporary_path)
    if result.returncode != 0:
        raise RuntimeError("antiword failed")
    extracted = result.stdout
    return [{
        "span_index": 0,
        "text": extracted,
        "char_start": 0,
        "char_end": len(extracted),
        "page_number": 0,
    }]


def extract_text_csv(file_bytes: bytes) -> list[dict]:
    """Parse CSV rows into normalized text spans, one span per row.

    The stdlib `csv` reader handles quoted delimiters, embedded commas and
    multi-line quoted fields; rows of differing column counts are tolerated by
    joining whatever cells a row has. Blank rows produce no span, matching how
    the DOCX extractor skips empty paragraphs.
    """
    import csv
    import io

    text = file_bytes.decode("utf-8-sig", errors="replace")
    spans = []
    char_offset = 0
    for span_index, row in enumerate(csv.reader(io.StringIO(text))):
        normalized = " ".join(cell.strip() for cell in row).strip()
        if not normalized:
            continue
        spans.append({
            "span_index": len(spans),
            "text": normalized,
            "char_start": char_offset,
            "char_end": char_offset + len(normalized),
            "page_number": 0,
        })
        char_offset += len(normalized) + 1
    return spans


def _single_span(text_value: str) -> list[dict]:
    return [{
        "span_index": 0,
        "text": text_value,
        "char_start": 0,
        "char_end": len(text_value),
        "page_number": 0,
    }]


def extract_text_plain(file_bytes: bytes) -> list[dict]:
    """A .txt Q&A-pair document. UTF-8 with a lenient fallback so a stray byte does not
    fail the whole upload."""
    try:
        text_value = file_bytes.decode("utf-8")
    except UnicodeDecodeError:
        text_value = file_bytes.decode("utf-8", errors="replace")
    return _single_span(text_value)


# extract_text_docx and extract_text_doc are defined above (python-docx / antiword) and
# cover the Q&A-pair .docx/.doc case too — no separate hand-rolled parser needed here.


def extract_text_pdf_as_image(file_bytes: bytes) -> list[dict]:
    """OCR a scanned PDF by rasterising pages with PyMuPDF (no poppler needed).

    Fallback for `extract_text_pdf`: a genuinely different rasterisation path (PyMuPDF
    instead of pdf2image/poppler), not a retry of the same one, so a PDF that defeats one
    approach has a real second chance rather than failing identically twice.
    """
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
MEDIA_TYPE_DOC = "application/msword"
MEDIA_TYPE_DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
MEDIA_TYPE_CSV = "text/csv"
MEDIA_TYPE_TXT = "text/plain"
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
    ".doc": MEDIA_TYPE_DOC,
    ".docx": MEDIA_TYPE_DOCX,
    ".csv": MEDIA_TYPE_CSV,
    ".txt": MEDIA_TYPE_TXT,
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
    if value in {MEDIA_TYPE_PDF, MEDIA_TYPE_DOC, MEDIA_TYPE_DOCX, MEDIA_TYPE_CSV, MEDIA_TYPE_TXT} or value in IMAGE_MEDIA_TYPES:
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

_DOCUMENT_COLUMNS = (
    "id, purpose, status, content_type, filename, blob_path, retention_mode, "
    "source_type, source_id, external_id, conversation_id, uploaded_by, ingested_by_kind"
)


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
        except Exception as exc:
            # The working store's own expiry is the backstop. A failed delete must not
            # turn a processed document into a failed one.
            logger.info(
                "working_copy_delete_failed",
                extra={"error_class": classify_processing_error(exc)},
            )
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
    engine = await get_resolver().resolve(tenant_id)
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
        file_data = await _resolve_content_for_processing(document, tenant_id)
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
                {"id": document_id, "msg": PROCESSING_ERROR_CONTENT_UNRESOLVABLE},
            )
            await session.commit()
        await _release_working_copy(session_factory, schema, document)
        return

    if reprocess:
        await _purge_derived_data(session_factory, schema, document_id)
        async with session_factory() as session:
            await session.execute(
                text(
                    f"UPDATE {schema}.documents SET status = 'processing', "
                    "error_message = NULL WHERE id = :id"
                ),
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
        elif media_type == MEDIA_TYPE_DOCX:
            spans = await asyncio.to_thread(extract_text_docx, file_data)
        elif media_type == MEDIA_TYPE_DOC:
            spans = await asyncio.to_thread(extract_text_doc, file_data)
        elif media_type == MEDIA_TYPE_CSV:
            spans = await asyncio.to_thread(extract_text_csv, file_data)
        elif media_type == MEDIA_TYPE_TXT:
            spans = await asyncio.to_thread(extract_text_plain, file_data)
        else:
            raise UnsupportedMediaType(f"Unsupported media type: {media_type or 'unresolved'}")

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
                text(
                    f"UPDATE {schema}.documents SET status = 'processed', "
                    "ocr_applied_flag = true, error_message = NULL WHERE id = :id"
                ),
                {"id": document_id},
            )
            await session.commit()
            await _record_registry_status(tenant_id, document_id, "processed")

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
                await _store_chunks(
                    document_id, tenant_id, chunks, embeddings, purpose,
                    conversation_id=getattr(document, "conversation_id", None),
                    uploaded_by=getattr(document, "uploaded_by", None),
                    ingested_by_kind=getattr(document, "ingested_by_kind", None),
                )
        except Exception:
            logger.info(
                "document_chunking_failed",
                extra={"error_class": PROCESSING_ERROR_CHUNKING_FAILED},
            )

        await _release_working_copy(session_factory, schema, document)

    except Exception as exc:
        error_class = classify_processing_error(exc)
        logger.info(
            "document_processing_failed", extra={"error_class": error_class}
        )
        async with session_factory() as session:
            await session.execute(
                text(
                    f"UPDATE {schema}.documents SET status = 'failed', "
                    "ocr_applied_flag = false, error_message = :msg WHERE id = :id"
                ),
                {"id": document_id, "msg": error_class},
            )
            await session.commit()
        await _record_registry_status(tenant_id, document_id, "failed")
        await _release_working_copy(session_factory, schema, document)


async def _record_registry_status(tenant_id: str, document_id: str, status: str) -> None:
    """Updates `public.tenant_document_registry` on a fresh *platform* session
    (Design D10) after an OCR terminal status transition — never the tenant
    session the transition itself committed on."""
    from src.shared import tenant_document_registry as registry

    platform_sessions = async_sessionmaker(get_engine(), expire_on_commit=False)
    async with platform_sessions() as platform_session:
        await registry.update_status(
            platform_session, tenant_id=tenant_id, document_id=document_id, status=status
        )


def trigger_ocr(document_id: str, tenant_id: str):
    """Dispatch by identity only. No bytes, no storage reference, no media type."""
    asyncio.create_task(process_document(document_id, tenant_id))
