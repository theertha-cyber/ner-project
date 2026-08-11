import asyncio
import traceback
import uuid
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker
from src.shared.database import get_engine
from src.shared.retrieval import Chunk, chunk_text as _shared_chunk_text
from src.document_service.services.storage import MinioStorageClient


async def _embed_chunks(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    from src.chat_api.services.embedding_service import EmbeddingService
    return await EmbeddingService().embed_batch(texts)


async def _store_chunks(document_id: str, tenant_id: str, chunks: list[Chunk], embeddings: list[list[float]], purpose: str):
    engine = get_engine()
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    schema = f"tenant_{tenant_id.replace('-', '_')}"
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


def extract_text_image(file_bytes: bytes) -> list[dict]:
    from PIL import Image
    import io
    import pytesseract
    image = Image.open(io.BytesIO(file_bytes))
    text = pytesseract.image_to_string(image)
    return [{
        "span_index": 0,
        "text": text,
        "char_start": 0,
        "char_end": len(text),
        "page_number": 0,
    }]


def extract_text_pdf_as_image(file_bytes: bytes) -> list[dict]:
    from pdf2image import convert_from_bytes
    import pytesseract
    images = convert_from_bytes(file_bytes)
    spans = []
    char_offset = 0
    for page_num, image in enumerate(images):
        text = pytesseract.image_to_string(image)
        spans.append({
            "span_index": page_num,
            "text": text,
            "char_start": char_offset,
            "char_end": char_offset + len(text),
            "page_number": page_num,
        })
        char_offset += len(text) + 1
    return spans


def _schema(tid: str) -> str:
    return f"tenant_{tid.replace('-', '_')}"


async def process_document(document_id: str, tenant_id: str, blob_path: str, content_type: str):
    engine = get_engine()
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    schema = _schema(tenant_id)

    purpose = "query"
    async with session_factory() as session:
        try:
            result = await session.execute(
                text(f"SELECT purpose FROM {schema}.documents WHERE id = :id"),
                {"id": document_id},
            )
            row = result.fetchone()
            if row is not None and row.purpose:
                purpose = row.purpose

            await session.execute(
                text(f"UPDATE {schema}.documents SET status = 'processing' WHERE id = :id"),
                {"id": document_id},
            )
            await session.commit()
        except Exception:
            await session.rollback()
            return

    storage = MinioStorageClient()
    file_data = storage.get_file(blob_path)
    if file_data is None:
        async with session_factory() as session:
            await session.execute(
                text(f"UPDATE {schema}.documents SET status = 'failed', error_message = :msg WHERE id = :id"),
                {"id": document_id, "msg": "File not found in storage"},
            )
            await session.commit()
        return

    try:
        ext = blob_path.split(".")[-1].lower() if "." in blob_path else ""
        if ext == "pdf":
            spans = extract_text_pdf(file_data)
            if not spans or all(not s["text"].strip() for s in spans):
                spans = extract_text_pdf_as_image(file_data)
        elif ext in ("jpg", "jpeg", "png", "tif", "tiff"):
            spans = extract_text_image(file_data)
        else:
            raise ValueError(f"Unsupported file extension: {ext}")

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

    except Exception as exc:
        error_msg = f"{type(exc).__name__}: {str(exc)}"
        traceback.print_exc()
        async with session_factory() as session:
            await session.execute(
                text(f"UPDATE {schema}.documents SET status = 'failed', error_message = :msg WHERE id = :id"),
                {"id": document_id, "msg": error_msg},
            )
            await session.commit()


def trigger_ocr(document_id: str, tenant_id: str, blob_path: str, content_type: str):
    asyncio.create_task(process_document(document_id, tenant_id, blob_path, content_type))
