"""Verification for the source-neutrality invariant — verification.md rows 21-22.

The whole point of an ingestion boundary is that nothing downstream can tell an upload
from a fetch. Row 21 is a static check over the modules that must stay neutral; row 22
puts two documents of different source types through the same pipeline and compares what
comes out.
"""

import ast
import os
import pathlib
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

os.environ.setdefault(
    "NER_DATABASE_URL", "postgresql+asyncpg://ner:ner@localhost:5432/ner_test"
)
os.environ.setdefault("NER_JWT_SECRET", "test-secret-do-not-use-in-prod")

from src.document_service.ingestion import (
    DocumentIngestionService,
    RecordingDispatcher,
    SourceReference,
)
from src.shared.config import settings

from tests.test_ingestion_boundary import (  # reuse the schema fixture and helpers
    FakeStore,
    normalized,
    session_factory,  # noqa: F401
    tenant,  # noqa: F401
)

SRC_ROOT = pathlib.Path(__file__).resolve().parents[1] / "src"

# The modules that must not know where a document came from.
NEUTRAL_MODULES = [
    "document_service/services/ocr_worker.py",
    "shared/retrieval",
    "chat_api",
    "extraction_service",
]

# Names that would mean a decision was taken on provenance rather than on the recorded
# retention mode or the resolved media type.
FORBIDDEN_NAMES = ("source_type", "source_id")

# The values a *document* source type can hold. The check compares against these rather
# than firing on the name alone, because `Source.source_type` in the chat citation model
# is an unrelated concept with its own value set (`ner`, `document_chunk`) — a name
# collision, not a provenance branch. Widening the name check to cover it would make this
# row fail on code it does not govern, which is worse than useless.
DOCUMENT_SOURCE_VALUES = frozenset(
    {
        "platform_upload",
        "platform-upload",
        "keka",
        "s3",
        "azure_blob",
        "sharepoint",
    }
)

# The ingestion package is where provenance is *set*, so it is not part of the downstream
# surface this row constrains.
EXEMPT = {
    os.path.join("document_service", "ingestion"),
}


def _neutral_files() -> list[pathlib.Path]:
    files: list[pathlib.Path] = []
    for entry in NEUTRAL_MODULES:
        target = SRC_ROOT / entry
        if target.is_dir():
            files.extend(target.rglob("*.py"))
        elif target.exists():
            files.append(target)
    return [
        f
        for f in files
        if not any(part in str(f) for part in EXEMPT)
    ]


def _branch_conditions(tree: ast.AST):
    """Every expression a control-flow decision is actually taken on."""
    for node in ast.walk(tree):
        if isinstance(node, (ast.If, ast.IfExp, ast.While)):
            yield node.test
        elif isinstance(node, ast.Match):
            yield node.subject


def test_row_21_no_downstream_module_branches_on_source_or_adapter_kind():
    offenders = []
    for path in _neutral_files():
        source = path.read_text(encoding="utf-8", errors="ignore")
        try:
            tree = ast.parse(source)
        except SyntaxError:  # pragma: no cover - would be a broken source file
            continue
        for condition in _branch_conditions(tree):
            rendered = ast.dump(condition)
            names_present = any(
                f"'{name}'" in rendered or f"attr='{name}'" in rendered
                for name in FORBIDDEN_NAMES
            )
            literals = {
                node.value
                for node in ast.walk(condition)
                if isinstance(node, ast.Constant) and isinstance(node.value, str)
            }
            if names_present and literals & DOCUMENT_SOURCE_VALUES:
                offenders.append(
                    f"{path.relative_to(SRC_ROOT)}:{condition.lineno} branches on document source"
                )
            # A storage-adapter kind is the same mistake wearing a different name.
            if "content_store_adapter" in rendered or "storage_adapter" in rendered:
                offenders.append(
                    f"{path.relative_to(SRC_ROOT)}:{condition.lineno} branches on adapter kind"
                )
    assert offenders == [], offenders


@pytest.mark.asyncio
async def test_row_22_two_source_types_produce_equivalent_results(
    tenant, session_factory
):
    """Same bytes, same purpose, different source types: one path, one outcome."""
    from src.document_service.services import ocr_worker

    store = FakeStore()
    service = DocumentIngestionService(
        dispatcher=RecordingDispatcher(), durable_store=store
    )

    upload_source = SourceReference(
        source_type="platform_upload", source_id="platform-upload"
    )
    fetched_source = SourceReference(source_type="keka", source_id="keka-prod")

    ids = []
    async with session_factory() as session:
        for source in (upload_source, fetched_source):
            result = await service.ingest(
                session, normalized(tenant["tenant_id"], source=source)
            )
            ids.append(result.document_id)

    page_text = "Neutral pipeline content. " * 6
    spans_by_document = {}
    chunk_counts = {}

    original_extract = ocr_worker.extract_text_pdf
    ocr_worker.extract_text_pdf = lambda data: [
        {
            "span_index": 0,
            "text": page_text,
            "char_start": 0,
            "char_end": len(page_text),
            "page_number": 0,
        }
    ]
    original_store_for = ocr_worker._store_for
    original_embed = ocr_worker._embed_chunks
    ocr_worker._store_for = lambda mode: store

    async def fake_embed(texts):
        return [[0.0] * 4 for _ in texts]

    ocr_worker._embed_chunks = fake_embed
    try:
        for document_id in ids:
            await ocr_worker.process_document(document_id, tenant["tenant_id"])
    finally:
        ocr_worker.extract_text_pdf = original_extract
        ocr_worker._store_for = original_store_for
        ocr_worker._embed_chunks = original_embed

    async with session_factory() as session:
        for document_id in ids:
            rows = (
                await session.execute(
                    text(
                        f"SELECT text, char_start, char_end, page_number "
                        f"FROM {tenant['schema']}.document_text_spans "
                        f"WHERE document_id = :id ORDER BY span_index"
                    ),
                    {"id": document_id},
                )
            ).fetchall()
            spans_by_document[document_id] = [tuple(r) for r in rows]
            chunk_counts[document_id] = (
                await session.execute(
                    text(
                        f"SELECT COUNT(*) FROM {tenant['schema']}.document_chunks "
                        f"WHERE document_id = :id"
                    ),
                    {"id": document_id},
                )
            ).scalar()

    first, second = ids
    assert spans_by_document[first], "no spans were produced"
    assert spans_by_document[first] == spans_by_document[second]
    assert chunk_counts[first] == chunk_counts[second]
