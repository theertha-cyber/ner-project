import subprocess
import uuid
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import text

from src.shared.retrieval.models import Chunk, RetrievalResult
from src.shared.retrieval.chunking import chunk_text
from src.shared.retrieval.retriever import DenseRetriever
from src.chat_api.api.v1.schemas import Source, Citation
from src.chat_api.services.rag_orchestrator import RAGOrchestrator

pytestmark = [pytest.mark.verification]

REPO_ROOT = Path(__file__).resolve().parents[1]


def _fake_vector(primary: list[float]) -> list[float]:
    vec = primary + [0.0] * (1536 - len(primary))
    return vec[:1536]


class FakeEmbeddingService:
    def __init__(self, query_vector: list[float]):
        self.query_vector = query_vector

    async def embed(self, query: str) -> list[float]:
        return self.query_vector


class TestChunkPageMetadata:
    def test_chunk_carries_page_metadata_within_span_range(self):
        span_text = " ".join(f"token{i}" for i in range(50))
        chunks = chunk_text(span_text, page_number=2, char_start=100)
        assert len(chunks) >= 1
        span_char_end = 100 + len(span_text)
        for c in chunks:
            assert c.page_number == 2
            assert 100 <= c.char_start <= span_char_end
            assert 100 <= c.char_end <= span_char_end

    def test_empty_span_produces_no_chunks(self):
        assert chunk_text("", page_number=1, char_start=0) == []
        assert chunk_text("   \n\t  ", page_number=1, char_start=0) == []

    def test_chunk_without_span_offset_has_none_metadata(self):
        chunks = chunk_text("hello world")
        assert chunks[0].page_number is None
        assert chunks[0].char_start is None
        assert chunks[0].char_end is None


class TestDenseRetrieverSqlDiff:
    def test_dense_retriever_select_only_adds_page_columns(self):
        # src/shared/retrieval was introduced (uncommitted) by retrieval-foundation;
        # there's no prior committed revision to diff against, so this asserts the
        # non-SELECT clauses match retrieval-foundation's documented/tested SQL
        # (see TestDenseRetrieverParity in test_retrieval_foundation.py) and that
        # only the SELECT column list gained the new fields.
        current_source = (REPO_ROOT / "src" / "shared" / "retrieval" / "retriever.py").read_text()

        for clause in ("WHERE embedding IS NOT NULL", "ORDER BY embedding <=> :query_emb", "LIMIT :top_k"):
            assert clause in current_source

        assert "page_number, char_start, char_end" in current_source


class TestOcrWorkerSpanInsertUnchanged:
    def test_document_text_spans_insert_matches_prior(self):
        result = subprocess.run(
            ["git", "show", "HEAD:src/document_service/services/ocr_worker.py"],
            cwd=REPO_ROOT, capture_output=True, text=True,
        )
        prior_source = result.stdout
        current_source = (REPO_ROOT / "src" / "document_service" / "services" / "ocr_worker.py").read_text()

        def _extract_insert(src: str) -> str:
            start = src.index("INSERT INTO {schema}.document_text_spans")
            end = src.index(")", src.index("VALUES", start)) + 1
            return src[start:end]

        assert _extract_insert(prior_source) == _extract_insert(current_source)


class TestCitationPageNumber:
    @pytest.mark.asyncio
    async def test_enrich_citations_populates_page_number_when_present(self):
        orchestrator = RAGOrchestrator.__new__(RAGOrchestrator)
        source = Source(
            source_type="document_chunk", document_id="doc-1", chunk_text="snippet",
            relevance_score=0.9, page_number=3,
        )

        class FakeResult:
            def fetchall(self):
                return []

        class FakeSession:
            async def execute(self, stmt, params):
                return FakeResult()

        enriched = await orchestrator._enrich_citations([source], FakeSession(), "tenant_test", "tenant-1")
        assert len(enriched) == 1
        assert isinstance(enriched[0], Citation)
        assert enriched[0].page_number == 3

    @pytest.mark.asyncio
    async def test_enrich_citations_page_number_none_when_absent(self):
        orchestrator = RAGOrchestrator.__new__(RAGOrchestrator)
        source = Source(source_type="document_chunk", document_id="doc-1", chunk_text="snippet", relevance_score=0.9)

        class FakeResult:
            def fetchall(self):
                return []

        class FakeSession:
            async def execute(self, stmt, params):
                return FakeResult()

        enriched = await orchestrator._enrich_citations([source], FakeSession(), "tenant_test", "tenant-1")
        assert len(enriched) == 1
        assert enriched[0].page_number is None


@pytest_asyncio.fixture
async def seeded_chunks_with_metadata(tenant_schema, engine):
    tenant_id, schema = tenant_schema
    from sqlalchemy.ext.asyncio import async_sessionmaker
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    doc_id = f"doc-{uuid.uuid4()}"

    async with session_factory() as session:
        await session.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await session.execute(
            text(f"""
                CREATE TABLE IF NOT EXISTS {schema}.document_chunks (
                    id VARCHAR PRIMARY KEY,
                    document_id VARCHAR NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    chunk_text TEXT NOT NULL,
                    embedding vector(1536),
                    page_number INTEGER,
                    char_start INTEGER,
                    char_end INTEGER,
                    purpose VARCHAR(20)
                )
            """)
        )
        await session.execute(
            text(f"""
                INSERT INTO {schema}.documents (id, tenant_id, filename, status, purpose)
                VALUES (:id, :tid, :fn, 'processed', 'query')
            """),
            {"id": doc_id, "tid": tenant_id, "fn": "seed.pdf"},
        )
        emb_str = "[" + ",".join(str(v) for v in _fake_vector([1.0, 0.0, 0.0])) + "]"
        await session.execute(
            text(f"""
                INSERT INTO {schema}.document_chunks
                    (id, document_id, chunk_index, chunk_text, embedding, page_number, char_start, char_end, purpose)
                VALUES (:id, :doc_id, 0, 'chunk with page metadata', '{emb_str}'::vector, 2, 100, 250, 'query')
            """),
            {"id": str(uuid.uuid4()), "doc_id": doc_id},
        )
        await session.execute(
            text(f"""
                INSERT INTO {schema}.document_chunks
                    (id, document_id, chunk_index, chunk_text, embedding, page_number, char_start, char_end, purpose)
                VALUES (:id, :doc_id, 1, 'chunk without page metadata', '{emb_str}'::vector, NULL, NULL, NULL, 'query')
            """),
            {"id": str(uuid.uuid4()), "doc_id": doc_id},
        )
        await session.commit()

    yield tenant_id, schema, doc_id


@pytest.mark.integration
class TestDenseRetrieverPageMetadata:
    @pytest.mark.asyncio
    async def test_retrieve_returns_page_metadata_when_present(self, seeded_chunks_with_metadata, engine):
        tenant_id, schema, doc_id = seeded_chunks_with_metadata
        from sqlalchemy.ext.asyncio import async_sessionmaker
        session_factory = async_sessionmaker(engine, expire_on_commit=False)

        retriever = DenseRetriever(FakeEmbeddingService(_fake_vector([1.0, 0.0, 0.0])))
        async with session_factory() as session:
            results = await retriever.retrieve("query", session, schema, top_k=5)

        by_index = {r.chunk_index: r for r in results}
        assert isinstance(by_index[0], RetrievalResult)
        assert by_index[0].page_number == 2
        assert by_index[0].char_start == 100
        assert by_index[0].char_end == 250

    @pytest.mark.asyncio
    async def test_retrieve_returns_none_metadata_when_null(self, seeded_chunks_with_metadata, engine):
        tenant_id, schema, doc_id = seeded_chunks_with_metadata
        from sqlalchemy.ext.asyncio import async_sessionmaker
        session_factory = async_sessionmaker(engine, expire_on_commit=False)

        retriever = DenseRetriever(FakeEmbeddingService(_fake_vector([1.0, 0.0, 0.0])))
        async with session_factory() as session:
            results = await retriever.retrieve("query", session, schema, top_k=5)

        by_index = {r.chunk_index: r for r in results}
        assert by_index[1].page_number is None
        assert by_index[1].char_start is None
        assert by_index[1].char_end is None


@pytest.mark.integration
class TestPerSpanIngestionChunkBoundary:
    """Exercises the same per-span chunk-then-store logic process_document runs
    (chunk_text per span, then _store_chunks), without going through the
    document_text_spans INSERT — tests/conftest.py's local document_text_spans
    table uses different column names (page_no/block_no/start_offset/end_offset)
    than the real migration-defined schema ocr_worker.py writes to (span_index/
    char_start/char_end/page_number); this pre-existing drift is out of scope
    for this change (see design.md), so — like retrieval-foundation's own tests —
    this test seeds document_chunks directly instead."""

    @pytest.mark.asyncio
    async def test_ingest_two_page_document_chunks_never_mix_pages(self, tenant_schema, engine):
        tenant_id, schema = tenant_schema
        from sqlalchemy.ext.asyncio import async_sessionmaker
        from src.document_service.services.ocr_worker import _store_chunks

        session_factory = async_sessionmaker(engine, expire_on_commit=False)

        async with session_factory() as session:
            await session.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            await session.execute(
                text(f"""
                    CREATE TABLE IF NOT EXISTS {schema}.document_chunks (
                        id VARCHAR PRIMARY KEY,
                        document_id VARCHAR NOT NULL,
                        chunk_index INTEGER NOT NULL,
                        chunk_text TEXT NOT NULL,
                        embedding vector(1536),
                        page_number INTEGER,
                        char_start INTEGER,
                        char_end INTEGER,
                        purpose VARCHAR(20)
                    )
                """)
            )
            doc_id = f"doc-{uuid.uuid4()}"
            await session.execute(
                text(f"""
                    INSERT INTO {schema}.documents (id, tenant_id, filename, status, purpose)
                    VALUES (:id, :tid, :fn, 'uploaded', 'query')
                """),
                {"id": doc_id, "tid": tenant_id, "fn": "two-page.pdf"},
            )
            await session.commit()

        page0_text = "Alpha section content about page zero. " * 5
        page1_text = "Beta section content about page one. " * 5
        spans = [
            {"span_index": 0, "text": page0_text, "char_start": 0, "char_end": len(page0_text), "page_number": 0},
            {"span_index": 1, "text": page1_text, "char_start": len(page0_text) + 1,
             "char_end": len(page0_text) + 1 + len(page1_text), "page_number": 1},
        ]

        # Same per-span chunking loop process_document runs.
        chunks: list[Chunk] = []
        for span in spans:
            for c in chunk_text(span["text"], page_number=span["page_number"], char_start=span["char_start"]):
                chunks.append(Chunk(
                    chunk_index=len(chunks), chunk_text=c.chunk_text,
                    page_number=c.page_number, char_start=c.char_start, char_end=c.char_end,
                ))
        embeddings = [_fake_vector([0.1, 0.2, 0.3]) for _ in chunks]
        await _store_chunks(doc_id, tenant_id, chunks, embeddings, "query")

        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        async with session_factory() as session:
            result = await session.execute(
                text(f"SELECT chunk_text, page_number FROM {schema}.document_chunks WHERE document_id = :doc_id ORDER BY chunk_index"),
                {"doc_id": doc_id},
            )
            rows = result.fetchall()

        assert len(rows) >= 2
        for row in rows:
            chunk_text_val, page_number = row
            assert page_number in (0, 1)
            if page_number == 0:
                assert "Beta" not in chunk_text_val
            else:
                assert "Alpha" not in chunk_text_val


@pytest.mark.integration
class TestChunkPurposeDenormalization:
    """Covers Hallucination Risk 2: purpose is fetched from the parent document
    and denormalized onto every document_chunks row _store_chunks inserts."""

    @pytest.mark.asyncio
    async def test_store_chunks_persists_purpose_on_every_row(self, tenant_schema, engine):
        tenant_id, schema = tenant_schema
        from sqlalchemy.ext.asyncio import async_sessionmaker
        from src.document_service.services.ocr_worker import _store_chunks

        session_factory = async_sessionmaker(engine, expire_on_commit=False)

        async with session_factory() as session:
            await session.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            await session.execute(
                text(f"""
                    CREATE TABLE IF NOT EXISTS {schema}.document_chunks (
                        id VARCHAR PRIMARY KEY,
                        document_id VARCHAR NOT NULL,
                        chunk_index INTEGER NOT NULL,
                        chunk_text TEXT NOT NULL,
                        embedding vector(1536),
                        page_number INTEGER,
                        char_start INTEGER,
                        char_end INTEGER,
                        purpose VARCHAR(20)
                    )
                """)
            )
            doc_id = f"doc-{uuid.uuid4()}"
            await session.execute(
                text(f"""
                    INSERT INTO {schema}.documents (id, tenant_id, filename, status, purpose)
                    VALUES (:id, :tid, :fn, 'uploaded', 'training')
                """),
                {"id": doc_id, "tid": tenant_id, "fn": "training-doc.pdf"},
            )
            await session.commit()

        chunks = [Chunk(chunk_index=0, chunk_text="some training content", page_number=0, char_start=0, char_end=22)]
        embeddings = [_fake_vector([0.1, 0.2, 0.3])]
        await _store_chunks(doc_id, tenant_id, chunks, embeddings, "training")

        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        async with session_factory() as session:
            rows = (await session.execute(
                text(f"SELECT purpose FROM {schema}.document_chunks WHERE document_id = :doc_id"),
                {"doc_id": doc_id},
            )).fetchall()

        assert len(rows) == 1
        assert all(r.purpose == "training" for r in rows)


@pytest.mark.integration
class TestChunkingRestrictedToQueryPurpose:
    """Only purpose='query' documents feed retrieval. Training documents must still
    get their text spans extracted (annotation/extraction need them) but must never
    be chunked or embedded."""

    async def _run_process_document(self, tenant_schema, engine, purpose, monkeypatch):
        tenant_id, schema = tenant_schema
        from sqlalchemy.ext.asyncio import async_sessionmaker
        from src.document_service.services import ocr_worker

        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        doc_id = f"doc-{uuid.uuid4()}"

        async with session_factory() as session:
            await session.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            await session.execute(
                text(f"""
                    CREATE TABLE IF NOT EXISTS {schema}.document_chunks (
                        id VARCHAR PRIMARY KEY,
                        document_id VARCHAR NOT NULL,
                        chunk_index INTEGER NOT NULL,
                        chunk_text TEXT NOT NULL,
                        embedding vector(1536),
                        page_number INTEGER,
                        char_start INTEGER,
                        char_end INTEGER,
                        purpose VARCHAR(20)
                    )
                """)
            )
            # conftest's document_text_spans uses page_no/start_offset/end_offset;
            # ocr_worker writes the migration-defined columns, so rebuild it here.
            await session.execute(text(f"DROP TABLE IF EXISTS {schema}.document_text_spans CASCADE"))
            await session.execute(
                text(f"""
                    CREATE TABLE {schema}.document_text_spans (
                        id VARCHAR PRIMARY KEY,
                        document_id VARCHAR NOT NULL,
                        span_index INTEGER,
                        text TEXT,
                        char_start INTEGER,
                        char_end INTEGER,
                        page_number INTEGER
                    )
                """)
            )
            await session.execute(
                text(f"""
                    INSERT INTO {schema}.documents (id, tenant_id, filename, status, purpose)
                    VALUES (:id, :tid, :fn, 'uploaded', :purpose)
                """),
                {"id": doc_id, "tid": tenant_id, "fn": f"{purpose}-doc.pdf", "purpose": purpose},
            )
            await session.commit()

        page_text = "Alpha section content about page zero. " * 5

        class FakeStorage:
            def get_file(self, blob_path):
                return b"%PDF-1.4 fake"

        embed_calls = []

        async def fake_embed(texts):
            embed_calls.append(list(texts))
            return [_fake_vector([0.1, 0.2, 0.3]) for _ in texts]

        monkeypatch.setattr(ocr_worker, "MinioStorageClient", FakeStorage)
        monkeypatch.setattr(ocr_worker, "_embed_chunks", fake_embed)
        monkeypatch.setattr(
            ocr_worker, "extract_text_pdf",
            lambda data: [{"span_index": 0, "text": page_text, "char_start": 0,
                           "char_end": len(page_text), "page_number": 0}],
        )

        await ocr_worker.process_document(doc_id, tenant_id, "blob/path.pdf", "application/pdf")

        async with session_factory() as session:
            chunk_count = (await session.execute(
                text(f"SELECT COUNT(*) FROM {schema}.document_chunks WHERE document_id = :id"),
                {"id": doc_id},
            )).scalar()
            span_count = (await session.execute(
                text(f"SELECT COUNT(*) FROM {schema}.document_text_spans WHERE document_id = :id"),
                {"id": doc_id},
            )).scalar()
            status = (await session.execute(
                text(f"SELECT status FROM {schema}.documents WHERE id = :id"), {"id": doc_id},
            )).scalar()

        return chunk_count, span_count, status, embed_calls

    @pytest.mark.asyncio
    async def test_training_document_is_not_chunked_or_embedded(self, tenant_schema, engine, monkeypatch):
        chunk_count, span_count, status, embed_calls = await self._run_process_document(
            tenant_schema, engine, "training", monkeypatch
        )
        assert chunk_count == 0
        assert embed_calls == []
        # Text spans still extracted — annotation/extraction depend on them.
        assert span_count == 1
        assert status == "processed"

    @pytest.mark.asyncio
    async def test_query_document_is_chunked_and_embedded(self, tenant_schema, engine, monkeypatch):
        chunk_count, span_count, status, embed_calls = await self._run_process_document(
            tenant_schema, engine, "query", monkeypatch
        )
        assert chunk_count >= 1
        assert len(embed_calls) == 1
        assert span_count == 1
        assert status == "processed"
