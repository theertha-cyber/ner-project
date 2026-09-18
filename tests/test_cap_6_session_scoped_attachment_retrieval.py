"""CAP-6 / ADR-014 — a conversation's attachment answers that conversation and no other.

The driving case is HR screening: a recruiter attaches a job description in one chat
session and asks about it there; the same question in a different session must not reach
it, while the tenant's own document library stays visible from everywhere.

Both retrieval channels are covered, because scoping only the vector path would leave the
generated-SQL path able to select the same text straight out of `document_chunks`.
"""

import uuid

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker

from src.shared.retrieval.retriever import DenseRetriever, HybridRetriever, SparseRetriever

pytestmark = [pytest.mark.verification]


CONV_A = "conv-a"
CONV_B = "conv-b"

# The job description and the library resume both talk about the same role, so every
# assertion below is about visibility rather than about relevance: a query that matches
# one matches the other.
JD_TEXT = "senior platform engineer job description kubernetes postgres ownership"
LIBRARY_TEXT = "senior platform engineer resume kubernetes postgres ownership"


def _fake_vector(primary: list[float]) -> list[float]:
    vec = primary + [0.0] * (1536 - len(primary))
    return vec[:1536]


class FakeEmbeddingService:
    """Returns the same vector the seeded rows carry, so ranking is decided by the
    predicate under test and not by an embedding model's opinion."""

    def __init__(self, vector: list[float]):
        self._vector = vector

    async def embed(self, text_value: str) -> list[float]:
        return self._vector


@pytest_asyncio.fixture
async def seeded_conversation_chunks(tenant_schema, engine):
    """One conversation-owned document (conversation A) and one library document with no
    conversation, each with a single matching chunk."""
    tenant_id, schema = tenant_schema
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    jd_doc_id = f"doc-jd-{uuid.uuid4()}"
    library_doc_id = f"doc-lib-{uuid.uuid4()}"
    vector = _fake_vector([0.9, 0.1, 0.0])
    emb = "[" + ",".join(str(v) for v in vector) + "]"

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
                    purpose VARCHAR(20),
                    conversation_id VARCHAR,
                    chunk_tsv tsvector GENERATED ALWAYS AS (to_tsvector('english', chunk_text)) STORED
                )
            """)
        )
        for conv_id in (CONV_A, CONV_B):
            await session.execute(
                text(
                    f"INSERT INTO {schema}.conversations (id, tenant_id, user_id, title) "
                    "VALUES (:cid, :tid, 'test-user', 'T')"
                ),
                {"cid": conv_id, "tid": tenant_id},
            )

        for doc_id, filename, conv in (
            (jd_doc_id, "job-description.pdf", CONV_A),
            (library_doc_id, "resume.pdf", None),
        ):
            await session.execute(
                text(
                    f"INSERT INTO {schema}.documents (id, tenant_id, filename, status, purpose, conversation_id) "
                    "VALUES (:id, :tid, :fn, 'processed', 'query', :cid)"
                ),
                {"id": doc_id, "tid": tenant_id, "fn": filename, "cid": conv},
            )

        for doc_id, body, conv in (
            (jd_doc_id, JD_TEXT, CONV_A),
            (library_doc_id, LIBRARY_TEXT, None),
        ):
            await session.execute(
                text(f"""
                    INSERT INTO {schema}.document_chunks
                        (id, document_id, chunk_index, chunk_text, embedding, purpose, conversation_id)
                    VALUES (:id, :doc_id, 0, :txt, '{emb}'::vector, 'query', :cid)
                """),
                {"id": str(uuid.uuid4()), "doc_id": doc_id, "txt": body, "cid": conv},
            )
        await session.commit()

    async with session_factory() as session:
        yield tenant_id, schema, jd_doc_id, library_doc_id, vector, session


@pytest.mark.asyncio
class TestConversationVisibilityInVectorRetrieval:
    """verification.md rows 1-4, 12-15, 17."""

    async def test_attachment_is_retrievable_in_its_own_conversation(self, seeded_conversation_chunks):
        tenant_id, schema, jd_doc_id, _lib, vector, session = seeded_conversation_chunks
        retriever = DenseRetriever(embedding_service=FakeEmbeddingService(vector))

        results = await retriever.retrieve(
            JD_TEXT, session, schema, top_k=10, conversation_id=CONV_A
        )

        assert jd_doc_id in {r.document_id for r in results}

    async def test_attachment_is_invisible_in_another_conversation(self, seeded_conversation_chunks):
        tenant_id, schema, jd_doc_id, library_doc_id, vector, session = seeded_conversation_chunks
        retriever = DenseRetriever(embedding_service=FakeEmbeddingService(vector))

        results = await retriever.retrieve(
            JD_TEXT, session, schema, top_k=10, conversation_id=CONV_B
        )

        document_ids = {r.document_id for r in results}
        assert jd_doc_id not in document_ids
        # Not vacuous: the same query still finds the library document in conversation B,
        # so the exclusion is the conversation rule and not an empty result set.
        assert library_doc_id in document_ids

    async def test_library_document_is_visible_from_every_conversation(self, seeded_conversation_chunks):
        tenant_id, schema, _jd, library_doc_id, vector, session = seeded_conversation_chunks
        retriever = DenseRetriever(embedding_service=FakeEmbeddingService(vector))

        in_a = await retriever.retrieve(LIBRARY_TEXT, session, schema, top_k=10, conversation_id=CONV_A)
        in_b = await retriever.retrieve(LIBRARY_TEXT, session, schema, top_k=10, conversation_id=CONV_B)

        assert library_doc_id in {r.document_id for r in in_a}
        assert library_doc_id in {r.document_id for r in in_b}

    async def test_no_conversation_admits_only_unowned_chunks(self, seeded_conversation_chunks):
        tenant_id, schema, jd_doc_id, library_doc_id, vector, session = seeded_conversation_chunks
        retriever = DenseRetriever(embedding_service=FakeEmbeddingService(vector))

        results = await retriever.retrieve(JD_TEXT, session, schema, top_k=10)

        document_ids = {r.document_id for r in results}
        assert jd_doc_id not in document_ids
        assert library_doc_id in document_ids

    async def test_metadata_filter_cannot_widen_conversation_visibility(self, seeded_conversation_chunks):
        """The `scope` argument the model chooses becomes `metadata_filter`. Naming the
        other conversation's document there must narrow to nothing, never reach it."""
        tenant_id, schema, jd_doc_id, _lib, vector, session = seeded_conversation_chunks
        retriever = DenseRetriever(embedding_service=FakeEmbeddingService(vector))

        results = await retriever.retrieve(
            JD_TEXT, session, schema, top_k=10,
            metadata_filter={"document_ids": [jd_doc_id]},
            conversation_id=CONV_B,
        )

        assert results == []

    async def test_sparse_retriever_applies_the_same_rule(self, seeded_conversation_chunks):
        tenant_id, schema, jd_doc_id, library_doc_id, _vector, session = seeded_conversation_chunks
        retriever = SparseRetriever()

        in_b = await retriever.retrieve("kubernetes postgres", session, schema, top_k=10, conversation_id=CONV_B)
        in_a = await retriever.retrieve("kubernetes postgres", session, schema, top_k=10, conversation_id=CONV_A)

        assert jd_doc_id not in {r.document_id for r in in_b}
        assert library_doc_id in {r.document_id for r in in_b}
        assert jd_doc_id in {r.document_id for r in in_a}

    async def test_hybrid_retriever_applies_the_same_rule(self, seeded_conversation_chunks):
        tenant_id, schema, jd_doc_id, library_doc_id, vector, session = seeded_conversation_chunks
        retriever = HybridRetriever(
            DenseRetriever(embedding_service=FakeEmbeddingService(vector)), SparseRetriever()
        )

        results = await retriever.retrieve(
            "kubernetes postgres", session, schema, top_k=10, conversation_id=CONV_B
        )

        document_ids = {r.document_id for r in results}
        assert jd_doc_id not in document_ids
        assert library_doc_id in document_ids


@pytest.mark.asyncio
class TestConversationVisibilityInGeneratedSQL:
    """verification.md row 33, risk 2 — the relational channel carries the same rule.

    `document_chunks.chunk_text` and `documents.filename` are both whitelisted for the
    generated-SQL path, so a statement selecting them is a second route to the same bytes.
    """

    async def test_generated_sql_cannot_read_another_conversations_chunk_text(
        self, seeded_conversation_chunks,
    ):
        from src.chat_api.services.sql_generator import (
            apply_conversation_scope,
            conversation_scope_columns,
            CONVERSATION_SCOPE_PARAM,
        )

        tenant_id, schema, _jd, _lib, _vector, session = seeded_conversation_chunks
        statement = "SELECT chunk_text FROM document_chunks LIMIT 100"

        scoped, rewritten = apply_conversation_scope(
            statement, CONV_B, conversation_scope_columns()
        )
        assert rewritten == 1

        await session.execute(text(f"SET search_path TO {schema}"))
        rows = (await session.execute(
            text(scoped), {CONVERSATION_SCOPE_PARAM: CONV_B}
        )).fetchall()

        texts = {r.chunk_text for r in rows}
        assert JD_TEXT not in texts
        assert LIBRARY_TEXT in texts

    async def test_generated_sql_reaches_the_current_conversations_chunk_text(
        self, seeded_conversation_chunks,
    ):
        from src.chat_api.services.sql_generator import (
            apply_conversation_scope,
            conversation_scope_columns,
            CONVERSATION_SCOPE_PARAM,
        )

        tenant_id, schema, _jd, _lib, _vector, session = seeded_conversation_chunks
        scoped, _ = apply_conversation_scope(
            "SELECT chunk_text FROM document_chunks LIMIT 100", CONV_A, conversation_scope_columns()
        )

        await session.execute(text(f"SET search_path TO {schema}"))
        rows = (await session.execute(text(scoped), {CONVERSATION_SCOPE_PARAM: CONV_A})).fetchall()

        texts = {r.chunk_text for r in rows}
        assert JD_TEXT in texts
        assert LIBRARY_TEXT in texts

    async def test_a_relation_without_its_own_conversation_column_is_scoped_through_documents(
        self, seeded_conversation_chunks,
    ):
        """`document_text_spans` holds the attachment's extracted text and has no
        `conversation_id` of its own, so it is reached through `documents`."""
        from src.chat_api.services.sql_generator import (
            apply_conversation_scope,
            conversation_scope_columns,
            CONVERSATION_SCOPE_PARAM,
        )

        tenant_id, schema, jd_doc_id, library_doc_id, _vector, session = seeded_conversation_chunks
        for doc_id, body in ((jd_doc_id, JD_TEXT), (library_doc_id, LIBRARY_TEXT)):
            await session.execute(
                text(
                    f"INSERT INTO {schema}.document_text_spans (id, document_id, text) "
                    "VALUES (:id, :doc, :txt)"
                ),
                {"id": str(uuid.uuid4()), "doc": doc_id, "txt": body},
            )
        await session.commit()

        scoped, rewritten = apply_conversation_scope(
            "SELECT text FROM document_text_spans LIMIT 100", CONV_B, conversation_scope_columns()
        )
        assert rewritten == 1

        await session.execute(text(f"SET search_path TO {schema}"))
        rows = (await session.execute(text(scoped), {CONVERSATION_SCOPE_PARAM: CONV_B})).fetchall()

        texts = {r.text for r in rows}
        assert JD_TEXT not in texts
        assert LIBRARY_TEXT in texts


class TestScopeCoverageGuard:
    """risk 2 — a table added to the query whitelist must not quietly escape scoping."""

    def test_every_conversation_bearing_whitelisted_table_is_scopeable(self):
        from src.chat_api.services.sql_generator import (
            WHITELISTED_TABLES,
            conversation_scope_columns,
        )

        scopeable = conversation_scope_columns()
        missing = [t for t in WHITELISTED_TABLES if t not in scopeable]

        assert missing == [], (
            f"whitelisted but not conversation-scopeable: {missing}. A relation the "
            f"generated-SQL path can query and the conversation scope cannot narrow is a "
            f"cross-conversation read (ADR-014)."
        )

    def test_scope_is_not_reachable_from_the_model_facing_scope_argument(self):
        """The retrieval tool's `scope` may narrow within what is visible; it must not
        gain a conversation member, which would put the boundary in model-chosen data."""
        from src.shared.retrieval.tools.document_tools import SUPPORTED_SCOPE_TYPES

        assert SUPPORTED_SCOPE_TYPES == {"tenant", "document"}
