"""Measures top-k recall when the uploader predicate is selective — design Risk 7.

`hnsw` is an approximate index. It returns its nearest neighbours and the `WHERE` clause
then removes some, so a user who owns a small fraction of a tenant's matching chunks can
receive fewer than `top_k` results even though far more visible matches exist. Nothing
errors; the answer is just quietly thinner.

This is the one risk in the change that cannot be settled by reading the code, so it is
measured rather than assumed. The test fails if a minority uploader gets a short result
set, which is the signal to raise the dense candidate count rather than to drop the
predicate.
"""

import os
import uuid

import pytest
import pytest_asyncio
from sqlalchemy import text

from src.shared.document_visibility import RequestingUser
from src.shared.retrieval.retriever import DenseRetriever

os.environ.setdefault(
    "NER_DATABASE_URL", "postgresql+asyncpg://ner:ner@localhost:55432/ner_test"
)

pytestmark = [pytest.mark.verification, pytest.mark.integration]

# The requesting user owns this fraction of matching chunks; the rest belong to other
# humans and are invisible. A tenth is the shape the risk describes.
TOTAL_CHUNKS = 300
MINORITY_SHARE = 0.1
TOP_K = 10


def _vector(seed: int) -> list[float]:
    """A deterministic unit-ish vector. Nearby seeds give nearby vectors, so ranking is
    stable across runs and the visible chunks are spread through the ranking rather than
    conveniently clustered at the top."""
    vec = [0.0] * 1536
    vec[0] = 1.0
    vec[1] = (seed % 100) / 1000.0
    vec[2] = (seed % 37) / 1000.0
    return vec


class FakeEmbeddingService:
    def __init__(self, vector):
        self._vector = vector

    async def embed(self, text_value):
        return self._vector


@pytest_asyncio.fixture
async def minority_uploader_corpus(tenant_schema, engine):
    tenant_id, schema = tenant_schema
    from sqlalchemy.ext.asyncio import async_sessionmaker

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    owner = "recruiter-minority"
    visible_ids = []

    async with session_factory() as session:
        await session.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await session.execute(text(f"DROP TABLE IF EXISTS {schema}.document_chunks CASCADE"))
        await session.execute(
            text(f"""
                CREATE TABLE {schema}.document_chunks (
                    id VARCHAR PRIMARY KEY,
                    document_id VARCHAR NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    chunk_text TEXT NOT NULL,
                    embedding vector(1536),
                    page_number INTEGER,
                    char_start INTEGER,
                    char_end INTEGER,
                    purpose VARCHAR(20),
                    conversation_id VARCHAR,
                    uploaded_by VARCHAR,
                    ingested_by_kind VARCHAR(32)
                )
            """)
        )
        await session.execute(
            text(f"ALTER TABLE {schema}.documents ADD COLUMN IF NOT EXISTS ingested_by_kind VARCHAR(32)")
        )

        for i in range(TOTAL_CHUNKS):
            mine = (i % int(1 / MINORITY_SHARE)) == 0
            uploader = owner if mine else f"recruiter-other-{i}"
            doc_id = f"doc-{uuid.uuid4()}"
            await session.execute(
                text(f"""
                    INSERT INTO {schema}.documents
                        (id, tenant_id, filename, status, purpose, uploaded_by, ingested_by_kind)
                    VALUES (:id, :tid, :fn, 'processed', 'query', :up, 'human')
                """),
                {"id": doc_id, "tid": tenant_id, "fn": f"cv-{i}.pdf", "up": uploader},
            )
            emb = "[" + ",".join(str(v) for v in _vector(i)) + "]"
            chunk_id = str(uuid.uuid4())
            await session.execute(
                text(f"""
                    INSERT INTO {schema}.document_chunks
                        (id, document_id, chunk_index, chunk_text, embedding, purpose,
                         uploaded_by, ingested_by_kind)
                    VALUES (:id, :doc, 0, :txt, '{emb}'::vector, 'query', :up, 'human')
                """),
                {
                    "id": chunk_id, "doc": doc_id, "up": uploader,
                    "txt": f"python django experience number {i}",
                },
            )
            if mine:
                visible_ids.append(chunk_id)
        await session.commit()

        # The real index. Without it the planner does an exact scan and the test proves
        # nothing about approximate recall.
        await session.execute(
            text(
                f"CREATE INDEX IF NOT EXISTS idx_recall_hnsw ON {schema}.document_chunks "
                "USING hnsw (embedding vector_cosine_ops)"
            )
        )
        await session.commit()

    yield tenant_id, schema, owner, visible_ids


async def test_minority_uploader_still_receives_a_full_result_set(
    minority_uploader_corpus, engine,
):
    """Risk 7. The requesting user owns ~10% of matching chunks — comfortably more than
    `TOP_K` of them — so a full page of results must come back."""
    tenant_id, schema, owner, visible_ids = minority_uploader_corpus
    from sqlalchemy.ext.asyncio import async_sessionmaker

    assert len(visible_ids) > TOP_K, "fixture must offer more visible matches than top_k"

    retriever = DenseRetriever(FakeEmbeddingService(_vector(0)))
    async with async_sessionmaker(engine, expire_on_commit=False)() as session:
        results = await retriever.retrieve(
            "python django experience", session, schema, top_k=TOP_K,
            requesting_user=RequestingUser(user_id=owner, role="business_user"),
        )

    assert len(results) == TOP_K, (
        f"minority uploader got {len(results)} of {TOP_K} results — the predicate is "
        "filtering the approximate candidate set down. Raise the dense candidate count "
        "rather than dropping the predicate."
    )


async def test_every_returned_chunk_is_actually_visible(minority_uploader_corpus, engine):
    """Recall is only interesting if correctness holds: a full page made up partly of
    other users' chunks would pass the test above and defeat the change."""
    tenant_id, schema, owner, visible_ids = minority_uploader_corpus
    from sqlalchemy.ext.asyncio import async_sessionmaker

    retriever = DenseRetriever(FakeEmbeddingService(_vector(0)))
    async with async_sessionmaker(engine, expire_on_commit=False)() as session:
        results = await retriever.retrieve(
            "python django experience", session, schema, top_k=TOP_K,
            requesting_user=RequestingUser(user_id=owner, role="business_user"),
        )

        rows = (await session.execute(
            text(
                f"SELECT DISTINCT uploaded_by FROM {schema}.document_chunks "
                "WHERE document_id = ANY(:ids)"
            ),
            {"ids": [r.document_id for r in results]},
        )).fetchall()

    assert rows, "no rows resolved for the returned documents"
    assert {r.uploaded_by for r in rows} == {owner}
