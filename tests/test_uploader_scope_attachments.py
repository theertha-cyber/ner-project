"""Attachments under both rules — verification.md rows 15-16.

A chat attachment is a `documents` row owned by one conversation (ADR-011) and ingested
with `ActorKind.HUMAN` and the attaching user's id. So it is subject to both rules at
once, and the two must compose as a conjunction: the user's own attachment is retrievable
in its own conversation and nowhere else.

The regression this guards against is a fix to one rule that quietly relaxes the other —
for instance an uploader predicate written as an `OR` beside the conversation predicate,
which would make every attachment visible to its uploader in every conversation.
"""

import uuid

import pytest
import pytest_asyncio
from sqlalchemy import text

from src.shared.document_visibility import RequestingUser
from src.shared.retrieval.retriever import DenseRetriever

pytestmark = [pytest.mark.verification, pytest.mark.integration]

OWNER = RequestingUser(user_id="recruiter-1", role="business_user")
OTHER = RequestingUser(user_id="recruiter-2", role="business_user")

CONV_A = "attach-conv-a"
CONV_B = "attach-conv-b"


def _fake_vector(primary):
    vec = list(primary) + [0.0] * (1536 - len(primary))
    return vec[:1536]


class FakeEmbeddingService:
    def __init__(self, vector):
        self._vector = vector

    async def embed(self, _text):
        return self._vector


@pytest_asyncio.fixture
async def seeded_attachment(tenant_schema, engine):
    """One conversation-owned attachment and one tenant-library document, both uploaded
    by the same user and both matching the same query."""
    tenant_id, schema = tenant_schema
    from sqlalchemy.ext.asyncio import async_sessionmaker

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    attachment_id = f"doc-attach-{uuid.uuid4()}"
    library_id = f"doc-library-{uuid.uuid4()}"

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
                    uploaded_by VARCHAR,
                    ingested_by_kind VARCHAR(32)
                )
            """)
        )
        for conv in (CONV_A, CONV_B):
            await session.execute(
                text(
                    f"INSERT INTO {schema}.conversations (id, tenant_id, user_id, title) "
                    "VALUES (:id, :tid, 'recruiter-1', 'T') ON CONFLICT (id) DO NOTHING"
                ),
                {"id": conv, "tid": tenant_id},
            )

        emb = "[" + ",".join(str(v) for v in _fake_vector([0.9, 0.1, 0.0])) + "]"
        for doc_id, conv, body in (
            (attachment_id, CONV_A, "attached job description python django"),
            (library_id, None, "library document python django"),
        ):
            await session.execute(
                text(f"""
                    INSERT INTO {schema}.documents
                        (id, tenant_id, filename, status, purpose, uploaded_by,
                         ingested_by_kind, conversation_id)
                    VALUES (:id, :tid, :fn, 'processed', 'query', 'recruiter-1', 'human', :conv)
                """),
                {"id": doc_id, "tid": tenant_id, "fn": f"{doc_id}.pdf", "conv": conv},
            )
            await session.execute(
                text(f"""
                    INSERT INTO {schema}.document_chunks
                        (id, document_id, chunk_index, chunk_text, embedding, purpose,
                         conversation_id, uploaded_by, ingested_by_kind)
                    VALUES (:id, :doc, 0, :txt, '{emb}'::vector, 'query', :conv,
                            'recruiter-1', 'human')
                """),
                {"id": str(uuid.uuid4()), "doc": doc_id, "txt": body, "conv": conv},
            )
        await session.commit()

    yield tenant_id, schema, attachment_id, library_id, session_factory


async def _retrieve(session_factory, schema, user, conversation_id):
    retriever = DenseRetriever(FakeEmbeddingService(_fake_vector([0.9, 0.1, 0.0])))
    async with session_factory() as session:
        results = await retriever.retrieve(
            "python django", session, schema, top_k=10,
            conversation_id=conversation_id, requesting_user=user,
        )
    return {r.document_id for r in results}


async def test_own_attachment_is_retrievable_in_its_own_conversation(seeded_attachment):
    """Row 15. Both rules admit it: the user uploaded it, and this is its conversation."""
    _tid, schema, attachment_id, _library, factory = seeded_attachment
    assert attachment_id in await _retrieve(factory, schema, OWNER, CONV_A)


async def test_own_attachment_is_not_retrievable_in_another_conversation(seeded_attachment):
    """Row 16. The uploader rule admits it and the conversation rule denies it; a
    conjunction denies it. An `OR` here would be the regression."""
    _tid, schema, attachment_id, _library, factory = seeded_attachment
    assert attachment_id not in await _retrieve(factory, schema, OWNER, CONV_B)


async def test_own_attachment_is_not_retrievable_with_no_conversation(seeded_attachment):
    _tid, schema, attachment_id, _library, factory = seeded_attachment
    assert attachment_id not in await _retrieve(factory, schema, OWNER, None)


async def test_another_user_cannot_reach_the_attachment_even_in_its_conversation(
    seeded_attachment,
):
    """The conversation rule alone would admit this — the conversation matches. The
    uploader rule is what denies it, which is the conjunction in the other direction."""
    _tid, schema, attachment_id, _library, factory = seeded_attachment
    assert attachment_id not in await _retrieve(factory, schema, OTHER, CONV_A)


async def test_library_content_stays_visible_from_inside_a_conversation(seeded_attachment):
    """The rules must narrow attachments without hiding the tenant library."""
    _tid, schema, _attachment, library_id, factory = seeded_attachment
    assert library_id in await _retrieve(factory, schema, OWNER, CONV_A)


async def test_the_two_rules_narrow_to_the_intersection(seeded_attachment):
    """Stated as the property rather than as four separate cases."""
    _tid, schema, attachment_id, library_id, factory = seeded_attachment

    assert await _retrieve(factory, schema, OWNER, CONV_A) == {attachment_id, library_id}
    assert await _retrieve(factory, schema, OWNER, CONV_B) == {library_id}
    assert await _retrieve(factory, schema, OTHER, CONV_A) == set()
