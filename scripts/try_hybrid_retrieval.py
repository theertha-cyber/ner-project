"""Manual playground for HybridRetriever/SparseRetriever/DenseRetriever — no LLM/OpenAI
required. Seeds a few chunks into a scratch schema on NER_DATABASE_URL, then lets you
run repeated queries against dense/sparse/hybrid and see the ranked results.

Usage:
    NER_DATABASE_URL="postgresql+asyncpg://ner:ner@localhost:54320/ner_test" \\
    NER_DATABASE_URL_SYNC="postgresql://ner:ner@localhost:54320/ner_test" \\
    NER_JWT_SECRET=x NER_MINIO_ACCESS_KEY=x NER_MINIO_SECRET_KEY=x NER_OPENAI_API_KEY=x \\
        python scripts/try_hybrid_retrieval.py "your query here"

Run with no argument for an interactive prompt loop.
"""
import asyncio
import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool

from src.shared.config import settings
from src.shared.retrieval.retriever import DenseRetriever, SparseRetriever, HybridRetriever

SCHEMA = "tenant_try_hybrid"

# (chunk_text, fake_embedding_direction) — direction is a small vector, padded to 1536.
SEED_CHUNKS = [
    ("Invoice number QX4471 is past due by 30 days.", [1.0, 0.0, 0.0]),
    ("Please review the attached quarterly financial report.", [0.9, 0.1, 0.0]),
    ("The purchase order references identifier ZR8823 for the shipment.", [0.0, 0.0, 1.0]),
    ("General notes about office relocation plans for next year.", [0.0, 1.0, 0.0]),
    ("Contract clause 7.2 covers termination for convenience.", [0.2, 0.8, 0.1]),
]


def _fake_vector(primary: list[float]) -> list[float]:
    vec = list(primary) + [0.0] * (1536 - len(primary))
    return vec[:1536]


class FakeEmbeddingService:
    """Returns a fixed query vector — swap for the real EmbeddingService if you have
    an OpenAI key and want true semantic similarity instead of a canned direction."""

    def __init__(self, vec: list[float]):
        self.vec = vec

    async def embed(self, query: str) -> list[float]:
        return self.vec


async def setup(session_factory) -> str:
    doc_id = f"doc-{uuid.uuid4()}"
    async with session_factory() as session:
        await session.execute(text(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE"))
        await session.execute(text(f"CREATE SCHEMA {SCHEMA}"))
        await session.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await session.execute(text(f"""
            CREATE TABLE {SCHEMA}.document_chunks (
                id VARCHAR PRIMARY KEY,
                document_id VARCHAR NOT NULL,
                chunk_index INTEGER NOT NULL,
                chunk_text TEXT NOT NULL,
                embedding vector(1536),
                page_number INTEGER,
                char_start INTEGER,
                char_end INTEGER,
                purpose VARCHAR(20),
                chunk_tsv tsvector GENERATED ALWAYS AS (to_tsvector('english', chunk_text)) STORED
            )
        """))
        await session.execute(text(f"""
            CREATE TABLE {SCHEMA}.documents (
                id VARCHAR PRIMARY KEY, tenant_id VARCHAR, filename VARCHAR, status VARCHAR, purpose VARCHAR
            )
        """))
        await session.execute(
            text(f"INSERT INTO {SCHEMA}.documents (id, tenant_id, filename, status, purpose) VALUES (:id, 'try-tenant', 'seed.pdf', 'processed', 'query')"),
            {"id": doc_id},
        )
        for idx, (chunk_text, direction) in enumerate(SEED_CHUNKS):
            emb_str = "[" + ",".join(str(v) for v in _fake_vector(direction)) + "]"
            await session.execute(
                text(f"""
                    INSERT INTO {SCHEMA}.document_chunks (id, document_id, chunk_index, chunk_text, embedding, purpose)
                    VALUES (:id, :doc_id, :idx, :txt, '{emb_str}'::vector, 'query')
                """),
                {"id": str(uuid.uuid4()), "doc_id": doc_id, "idx": idx, "txt": chunk_text},
            )
        await session.commit()
    print(f"Seeded {len(SEED_CHUNKS)} chunks into {SCHEMA}.")
    for i, (t, _) in enumerate(SEED_CHUNKS):
        print(f"  [{i}] {t}")
    print()
    return doc_id


async def run_query(session_factory, query: str) -> None:
    # Query embedding direction picked to loosely resemble chunk 0/1's cluster —
    # this is a canned stand-in, not real semantic similarity (no OpenAI call).
    query_vec = _fake_vector([0.85, 0.15, 0.0])
    dense = DenseRetriever(FakeEmbeddingService(query_vec))
    sparse = SparseRetriever()
    hybrid = HybridRetriever(dense, sparse)

    print(f"=== query: {query!r} ===")
    for label, retriever in [("dense", dense), ("sparse", sparse), ("hybrid", hybrid)]:
        async with session_factory() as session:
            results = await retriever.retrieve(query, session, SCHEMA, top_k=5)
        print(f"-- {label} --")
        if not results:
            print("   (no results)")
        for r in results:
            print(f"   [{r.chunk_index}] score={r.similarity_score:.4f}  {r.chunk_text}")
    print()


async def main():
    engine = create_async_engine(settings.database_url, isolation_level="AUTOCOMMIT", poolclass=NullPool)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    await setup(session_factory)

    args_query = " ".join(sys.argv[1:]).strip()
    if args_query:
        await run_query(session_factory, args_query)
    else:
        print("Interactive mode — type a query, empty line to quit.")
        while True:
            try:
                q = input("query> ").strip()
            except EOFError:
                break
            if not q:
                break
            await run_query(session_factory, q)

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
