import subprocess
import sys
import uuid
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import text

from src.shared.retrieval.models import Chunk, RetrievalResult
from src.shared.retrieval.chunking import chunk_text, TOKENIZER
from src.shared.retrieval.retriever import DenseRetriever
from src.chat_api.api.v1.schemas import Source, Citation
from src.chat_api.services.embedding_service import EmbeddingService
from src.chat_api.services.rag_orchestrator import RAGOrchestrator

pytestmark = [pytest.mark.verification]

REPO_ROOT = Path(__file__).resolve().parents[1]


def _fake_vector(primary: list[float]) -> list[float]:
    vec = primary + [0.0] * (1536 - len(primary))
    return vec[:1536]


class FakeEmbeddingService:
    """Deterministic stand-in for EmbeddingService.embed — avoids a live OpenAI call."""

    def __init__(self, query_vector: list[float]):
        self.query_vector = query_vector

    async def embed(self, query: str) -> list[float]:
        return self.query_vector


async def _old_similarity_search(query_embedding: list[float], session, schema: str, top_k: int) -> list[dict]:
    """Verbatim copy of the pre-refactor EmbeddingService.similarity_search SQL,
    kept only in this test to prove DenseRetriever is a byte-identical port."""
    embedding_str = "[" + ",".join(str(v) for v in query_embedding) + "]"
    result = await session.execute(
        text(f"""
            SELECT id, document_id, chunk_index, chunk_text,
                   1 - (embedding <=> :query_emb) AS similarity_score
            FROM {schema}.document_chunks
            WHERE embedding IS NOT NULL
            ORDER BY embedding <=> :query_emb
            LIMIT :top_k
        """),
        {"query_emb": embedding_str, "top_k": top_k},
    )
    rows = result.fetchall()
    return [
        {
            "document_id": r.document_id,
            "chunk_index": r.chunk_index,
            "chunk_text": r.chunk_text,
            "similarity_score": float(r.similarity_score),
        }
        for r in rows
    ]


@pytest_asyncio.fixture
async def seeded_chunks(tenant_schema, engine):
    tenant_id, schema = tenant_schema
    from sqlalchemy.ext.asyncio import async_sessionmaker
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    doc_id = f"doc-{uuid.uuid4()}"
    chunks = [
        ("chunk closely matching the query", _fake_vector([0.9, 0.1, 0.0])),
        ("chunk somewhat related to the query", _fake_vector([0.1, 0.9, 0.0])),
        ("chunk unrelated to the query", _fake_vector([0.0, 0.0, 1.0])),
    ]

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
        for i, (chunk_text_val, vec) in enumerate(chunks):
            emb_str = "[" + ",".join(str(v) for v in vec) + "]"
            await session.execute(
                text(f"""
                    INSERT INTO {schema}.document_chunks (id, document_id, chunk_index, chunk_text, embedding, purpose)
                    VALUES (:id, :doc_id, :idx, :txt, '{emb_str}'::vector, 'query')
                """),
                {"id": str(uuid.uuid4()), "doc_id": doc_id, "idx": i, "txt": chunk_text_val},
            )
        await session.commit()

    yield tenant_id, schema, doc_id


class TestRetrievalConfigDefaults:
    def test_defaults_match_prior_hardcoded_values(self, monkeypatch):
        for var in ("NER_CHUNK_SIZE", "NER_CHUNK_OVERLAP", "NER_RETRIEVAL_TOP_K", "NER_EMBEDDING_MODEL"):
            monkeypatch.delenv(var, raising=False)
        from src.shared.config import Settings
        s = Settings(jwt_secret="x", minio_access_key="x", minio_secret_key="x", openai_api_key="x")
        assert s.chunk_size == 512
        assert s.chunk_overlap == 128
        assert s.retrieval_top_k == 5
        assert s.embedding_model == "text-embedding-3-small"

    def test_top_k_overridable_via_env(self, monkeypatch):
        monkeypatch.setenv("NER_RETRIEVAL_TOP_K", "8")
        from src.shared.config import Settings
        s = Settings(jwt_secret="x", minio_access_key="x", minio_secret_key="x", openai_api_key="x")
        assert s.retrieval_top_k == 8


class TestSharedChunking:
    def test_chunk_text_returns_chunk_models(self):
        chunks = chunk_text("hello world, this is a short document.")
        assert len(chunks) == 1
        assert isinstance(chunks[0], Chunk)
        assert chunks[0].chunk_index == 0

    def test_chunking_preserves_512_128_boundaries_and_overlap(self):
        # Build text with a predictable, large token count.
        text = " ".join(f"token{i}" for i in range(2000))
        chunks = chunk_text(text, chunk_size=512, overlap=128)

        assert len(chunks) > 1
        for i, c in enumerate(chunks):
            token_count = len(TOKENIZER.encode(c.chunk_text))
            if i < len(chunks) - 1:
                assert token_count == 512
            else:
                assert token_count <= 512
            assert c.chunk_index == i

        # Consecutive chunks overlap by exactly `overlap` tokens.
        for i in range(len(chunks) - 1):
            prev_tokens = TOKENIZER.encode(chunks[i].chunk_text)
            next_tokens = TOKENIZER.encode(chunks[i + 1].chunk_text)
            assert prev_tokens[-128:] == next_tokens[:128]

    def test_single_chunking_implementation_in_codebase(self):
        pattern = "def " + "chunk_text" + r"\|def _" + "chunk_text"
        result = subprocess.run(
            ["git", "grep", "--untracked", "-l", pattern, "--", "src"],
            cwd=REPO_ROOT, capture_output=True, text=True,
        )
        matches = [line.replace("\\", "/") for line in result.stdout.splitlines() if line.strip()]
        assert matches == ["src/shared/retrieval/chunking.py"], (
            f"expected exactly one chunking implementation, found: {matches}"
        )

    def test_chunking_service_module_removed(self):
        assert not (REPO_ROOT / "src" / "chat_api" / "services" / "chunking_service.py").exists()


class TestDenseRetrieverConfig:
    @pytest.mark.asyncio
    async def test_retrieve_uses_configured_top_k_default(self, monkeypatch):
        monkeypatch.setenv("NER_RETRIEVAL_TOP_K", "8")
        import importlib
        from src.shared import config as config_module
        importlib.reload(config_module)

        captured = {}

        class FakeEmbeddingService:
            async def embed(self, query):
                return [0.0]

        class FakeResult:
            def fetchall(self):
                return []

        class FakeSession:
            async def execute(self, stmt, params):
                captured["top_k"] = params["top_k"]
                return FakeResult()

        retriever = DenseRetriever(FakeEmbeddingService())
        monkeypatch.setattr("src.shared.retrieval.retriever.settings", config_module.settings)
        await retriever.retrieve("query", FakeSession(), "tenant_test", top_k=None)
        assert captured["top_k"] == 8

        importlib.reload(config_module)


class TestCitationEnrichmentBugFix:
    @pytest.mark.asyncio
    async def test_enrich_citations_executes_without_nameerror(self):
        orchestrator = RAGOrchestrator.__new__(RAGOrchestrator)
        source = Source(source_type="document_chunk", document_id="doc-1", chunk_text="snippet", relevance_score=0.9)

        class FakeRow:
            def __init__(self, values):
                self._values = values

            def __getitem__(self, idx):
                return self._values[idx]

        class FakeResult:
            def __init__(self, rows):
                self._rows = rows

            def fetchall(self):
                return self._rows

        class FakeSession:
            async def execute(self, stmt, params):
                assert "documents" in str(stmt)
                return FakeResult([FakeRow(["doc-1", "report.pdf"])])

        enriched = await orchestrator._enrich_citations([source], FakeSession(), "tenant_test", "tenant-1")

        assert len(enriched) == 1
        assert isinstance(enriched[0], Citation)
        assert enriched[0].document_name == "report.pdf"


@pytest.mark.integration
class TestDenseRetrieverParity:
    """Covers scenario 3: DenseRetriever output must be identical to the
    pre-refactor EmbeddingService.similarity_search for the same query and
    seeded tenant data (document_id, chunk_index, chunk_text,
    similarity_score, ordering)."""

    @pytest.mark.asyncio
    async def test_dense_retriever_matches_prior_similarity_search_output(self, seeded_chunks, engine):
        tenant_id, schema, doc_id = seeded_chunks
        from sqlalchemy.ext.asyncio import async_sessionmaker
        session_factory = async_sessionmaker(engine, expire_on_commit=False)

        query_vector = _fake_vector([1.0, 0.0, 0.0])

        async with session_factory() as session:
            old_results = await _old_similarity_search(query_vector, session, schema, top_k=5)

        retriever = DenseRetriever(FakeEmbeddingService(query_vector))
        async with session_factory() as session:
            new_results = await retriever.retrieve("closely matching query", session, schema, top_k=5)

        assert len(old_results) == len(new_results) == 3
        for old, new in zip(old_results, new_results):
            assert isinstance(new, RetrievalResult)
            assert old["document_id"] == new.document_id
            assert old["chunk_index"] == new.chunk_index
            assert old["chunk_text"] == new.chunk_text
            assert old["similarity_score"] == pytest.approx(new.similarity_score)

        # Highest-similarity chunk (closest to [1,0,0]) ranks first.
        assert new_results[0].chunk_index == 0


@pytest_asyncio.fixture
async def seeded_mixed_purpose_chunks(tenant_schema, engine):
    tenant_id, schema = tenant_schema
    from sqlalchemy.ext.asyncio import async_sessionmaker
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    query_doc_id = f"doc-{uuid.uuid4()}"
    training_doc_id = f"doc-{uuid.uuid4()}"
    vec = _fake_vector([0.9, 0.1, 0.0])
    emb_str = "[" + ",".join(str(v) for v in vec) + "]"

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
                VALUES (:qid, :tid, 'query.pdf', 'processed', 'query'),
                       (:trid, :tid, 'training.pdf', 'processed', 'training')
            """),
            {"qid": query_doc_id, "trid": training_doc_id, "tid": tenant_id},
        )
        await session.execute(
            text(f"""
                INSERT INTO {schema}.document_chunks (id, document_id, chunk_index, chunk_text, embedding, purpose)
                VALUES (:id, :doc_id, 0, 'query purpose chunk matching query', '{emb_str}'::vector, 'query')
            """),
            {"id": str(uuid.uuid4()), "doc_id": query_doc_id},
        )
        await session.execute(
            text(f"""
                INSERT INTO {schema}.document_chunks (id, document_id, chunk_index, chunk_text, embedding, purpose)
                VALUES (:id, :doc_id, 0, 'training purpose chunk matching query', '{emb_str}'::vector, 'training')
            """),
            {"id": str(uuid.uuid4()), "doc_id": training_doc_id},
        )
        await session.commit()

    yield tenant_id, schema, query_doc_id, training_doc_id


@pytest.mark.integration
class TestRetrievalPurposeScoping:
    """Covers scenarios 9-10: retrieval hard-excludes purpose='training' chunks,
    unconditionally, with no caller-supplied bypass."""

    @pytest.mark.asyncio
    async def test_retrieve_excludes_training_purpose_chunks(self, seeded_mixed_purpose_chunks, engine):
        tenant_id, schema, query_doc_id, training_doc_id = seeded_mixed_purpose_chunks
        from sqlalchemy.ext.asyncio import async_sessionmaker
        session_factory = async_sessionmaker(engine, expire_on_commit=False)

        retriever = DenseRetriever(FakeEmbeddingService(_fake_vector([0.9, 0.1, 0.0])))
        async with session_factory() as session:
            results = await retriever.retrieve("matching query", session, schema, top_k=5)

        assert len(results) == 1
        assert results[0].document_id == query_doc_id
        assert all(r.document_id != training_doc_id for r in results)

    @pytest.mark.asyncio
    async def test_vector_source_cannot_bypass_purpose_restriction(self, seeded_mixed_purpose_chunks, engine):
        tenant_id, schema, query_doc_id, training_doc_id = seeded_mixed_purpose_chunks
        from sqlalchemy.ext.asyncio import async_sessionmaker
        session_factory = async_sessionmaker(engine, expire_on_commit=False)

        retriever = DenseRetriever(FakeEmbeddingService(_fake_vector([0.9, 0.1, 0.0])))

        async with session_factory() as session:
            results = await retriever.retrieve("training.pdf matching query", session, schema)

        assert all(r.document_id != training_doc_id for r in results)

    def test_purpose_filter_is_unconditional_in_sql(self):
        current_source = (REPO_ROOT / "src" / "shared" / "retrieval" / "retriever.py").read_text()
        assert "purpose = 'query'" in current_source


@pytest.mark.integration
class TestOrchestratorVectorSourceIntegration:
    """Covers scenarios 1, 2, 4: the retriever returns RetrievalResult objects via
    the Retriever interface, end-to-end against a seeded tenant schema. Reached in
    production through the `semantic_retrieval` capability."""

    @pytest.mark.asyncio
    async def test_vector_source_returns_retrieval_results_via_retriever(self, seeded_chunks, engine):
        tenant_id, schema, doc_id = seeded_chunks
        from sqlalchemy.ext.asyncio import async_sessionmaker
        session_factory = async_sessionmaker(engine, expire_on_commit=False)

        retriever = DenseRetriever(FakeEmbeddingService(_fake_vector([1.0, 0.0, 0.0])))

        async with session_factory() as session:
            results = await retriever.retrieve("closely matching query", session, schema)

        assert len(results) == 3
        assert all(isinstance(r, RetrievalResult) for r in results)
        assert not hasattr(EmbeddingService, "similarity_search")
        assert results[0].document_id == doc_id
