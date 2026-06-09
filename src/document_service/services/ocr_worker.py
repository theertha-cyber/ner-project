import asyncio
import traceback
import uuid
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker
from src.shared.database import get_engine
from src.document_service.services.storage import MinioStorageClient


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

    async with session_factory() as session:
        try:
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
