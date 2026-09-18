"""End-to-end proof of uploader isolation — verification.md rows 9, 12, 14, 52.

Every other test in this change exercises one layer: the predicate, a retriever called
directly, a rewritten statement executed against Postgres, or the source of the wiring.
None of them proves the thing actually asked for — that a business user asking the
chatbot a question cannot get another business user's document back.

This one drives the real HTTP endpoint: a signed JWT for one user, through the auth
middleware, the orchestrator, the graph, the tool layer, the retriever, and into real SQL
against a real tenant schema holding both users' resumes. Only the LLM is faked, because
the planner and the generator are the two places that would otherwise need a model — and
neither of them decides visibility.

The failure this is built to catch is the one no source-inspection test can: the wiring
reads correctly, but `request.state.user_id` is empty at runtime, every user silently
becomes anonymous, and the rule either hides everything or — if the absent-user branch
had been written as `if user: filter` — shows everything.
"""

import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker

from src.shared.auth import create_access_token
from src.shared.retrieval.retriever import DenseRetriever
from src.shared.retrieval.tools import build_default_registry

pytestmark = [pytest.mark.verification, pytest.mark.integration]

RECRUITER_1 = "recruiter-1"
RECRUITER_2 = "recruiter-2"

QUERY = "which candidates know python"


def _fake_vector(primary):
    vec = list(primary) + [0.0] * (1536 - len(primary))
    return vec[:1536]


class FakeEmbeddingService:
    def __init__(self, vector):
        self.vector = vector

    async def embed(self, _query):
        return self.vector

    async def embed_batch(self, texts):
        return [self.vector for _ in texts]


_REPLY = "Here is the answer, drawn from the sources provided."


class _Delta:
    def __init__(self, content):
        self.content = content


class _StreamChoice:
    def __init__(self, content):
        self.delta = _Delta(content)


class _StreamChunk:
    def __init__(self, content):
        self.choices = [_StreamChoice(content)]


class _FakeStream:
    """An async-iterable completion, which is what `generation_node` consumes when the
    turn streams. Returning a plain response here makes the streaming route fail with
    `GENERATION_FAILED` — and a leak assertion against an error body passes vacuously,
    which is the false green this class exists to prevent."""

    def __aiter__(self):
        async def _gen():
            for piece in _REPLY.split(" "):
                yield _StreamChunk(piece + " ")
        return _gen()


class _FakeCompletions:
    async def create(self, **kwargs):
        if kwargs.get("stream"):
            return _FakeStream()

        class Choice:
            class Message:
                content = _REPLY
                tool_calls = None

            message = Message()
            finish_reason = "stop"

        class Response:
            choices = [Choice()]

        return Response()


class FakeLLMClient:
    class chat:
        completions = _FakeCompletions()


def _make_orchestrator(query_vector):
    """A real orchestrator with a real retriever and a fake model.

    Built with `__new__` so no API client is constructed, mirroring the harness
    `test_chat_api_reranking.py` already uses. The retriever, the tool registry, the
    graph and every SQL statement are the production ones — which is the point.
    """
    from src.chat_api.services.rag_orchestrator import RAGOrchestrator

    orchestrator = RAGOrchestrator.__new__(RAGOrchestrator)
    orchestrator.retriever = DenseRetriever(FakeEmbeddingService(query_vector))
    orchestrator.llm_client = FakeLLMClient()
    orchestrator.llm_model = "fake-model"
    orchestrator.tool_registry = build_default_registry()

    class NoopGuardrails:
        def check_blocked_question_type(self, message, tenant_id):
            return None

        async def classify_domain(self, message, conversation_context, llm_client,
                                  llm_model, attachment_filenames=None):
            return True

        def enforce_sources(self, reply, sources, retrieval_status=None):
            return reply, sources

        def inject_disclaimer(self):
            return "disclaimer"

    class NoopSqlGenerator:
        async def generate_and_execute(self, *_args, **_kwargs):
            return None

    orchestrator.guardrails = NoopGuardrails()
    orchestrator.sql_generator = NoopSqlGenerator()
    return orchestrator


@pytest_asyncio.fixture
async def two_recruiters(tenant_schema, engine, monkeypatch):
    """One tenant, three resumes that all answer the same question:

    - recruiter-1 uploaded `alice.pdf`
    - recruiter-2 uploaded `dave.pdf`   <- the document that used to leak
    - a source system synced `carol.pdf`
    """
    tenant_id, schema = tenant_schema
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    query_vector = _fake_vector([0.9, 0.1, 0.0])
    ids = {}

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
                    ingested_by_kind VARCHAR(32),
                    chunk_tsv tsvector GENERATED ALWAYS AS
                        (to_tsvector('english', chunk_text)) STORED
                )
            """)
        )
        await session.execute(
            text(f"ALTER TABLE {schema}.documents ADD COLUMN IF NOT EXISTS ingested_by_kind VARCHAR(32)")
        )
        # The graph's entity-resolution node reads its per-conversation state here. The
        # shared fixture does not create it, and this test runs the real graph rather
        # than a patched orchestrator.
        await session.execute(
            text(f"""
                CREATE TABLE IF NOT EXISTS {schema}.conversation_entity_state (
                    conversation_id VARCHAR PRIMARY KEY,
                    pending_original_message TEXT,
                    pending_mention TEXT,
                    pending_candidates JSONB,
                    pending_reask_count INTEGER DEFAULT 0,
                    resolved_document_id VARCHAR,
                    resolved_entity_value TEXT
                )
            """)
        )
        # Entity resolution also reads the extracted-entity store. Left empty: this test
        # is about document retrieval, and an empty table is the honest state for a
        # tenant whose extraction has not run.
        await session.execute(
            text(f"""
                CREATE TABLE IF NOT EXISTS {schema}.document_entities (
                    id VARCHAR PRIMARY KEY,
                    document_id VARCHAR NOT NULL,
                    entity_type TEXT NOT NULL,
                    entity_value TEXT NOT NULL,
                    normalized_value TEXT NOT NULL,
                    confidence DOUBLE PRECISION NOT NULL
                )
            """)
        )

        seeds = [
            ("alice", "alice.pdf", RECRUITER_1, "human", "Alice has five years of python and django"),
            ("dave", "dave.pdf", RECRUITER_2, "human", "Dave has seven years of python and flask"),
            ("carol", "carol.pdf", None, "source_system", "Carol has three years of python and fastapi"),
        ]
        emb = "[" + ",".join(str(v) for v in query_vector) + "]"
        for key, filename, uploader, kind, body in seeds:
            doc_id = f"doc-{key}-{uuid.uuid4()}"
            ids[key] = doc_id
            await session.execute(
                text(f"""
                    INSERT INTO {schema}.documents
                        (id, tenant_id, filename, status, purpose, uploaded_by, ingested_by_kind)
                    VALUES (:id, :tid, :fn, 'processed', 'query', :up, :kind)
                """),
                {"id": doc_id, "tid": tenant_id, "fn": filename, "up": uploader, "kind": kind},
            )
            await session.execute(
                text(f"""
                    INSERT INTO {schema}.document_chunks
                        (id, document_id, chunk_index, chunk_text, embedding, purpose,
                         uploaded_by, ingested_by_kind)
                    VALUES (:id, :doc, 0, :txt, '{emb}'::vector, 'query', :up, :kind)
                """),
                {"id": str(uuid.uuid4()), "doc": doc_id, "txt": body,
                 "up": uploader, "kind": kind},
            )
        await session.commit()

    from src.chat_api.api.v1 import chat as chat_module

    monkeypatch.setattr(chat_module, "orchestrator", _make_orchestrator(query_vector))
    yield tenant_id, schema, ids


async def _ask(tenant_id, user_id, role="business_user"):
    """A real POST to the chat endpoint, authenticated as this user."""
    from src.chat_api.main import app

    token = create_access_token(tenant_id=tenant_id, user_id=user_id, role=role)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/chat",
            json={"message": QUERY},
            headers={"Authorization": f"Bearer {token}"},
        )
    return response


def _cited_document_ids(payload) -> set[str]:
    return {
        s.get("document_id")
        for s in (payload.get("sources") or [])
        if s.get("document_id")
    }


# --- The question this whole change exists to answer --------------------------------


async def test_a_business_user_never_receives_another_users_document(two_recruiters):
    """Row 9 / row 14, through the front door.

    recruiter-1 asks the chatbot who knows Python. Dave's resume matches the question
    just as well as Alice's — it is only recruiter-2's ownership that excludes it.
    """
    tenant_id, _schema, ids = two_recruiters

    response = await _ask(tenant_id, RECRUITER_1)
    assert response.status_code == 200, response.text
    payload = response.json()

    cited = _cited_document_ids(payload)
    assert ids["dave"] not in cited, (
        "the chatbot returned a document uploaded by another business user"
    )
    assert ids["alice"] in cited, "the user's own document was not returned"


async def test_the_other_user_gets_the_mirror_image(two_recruiters):
    """The rule is symmetric, not a filter that happens to favour one seeded user."""
    tenant_id, _schema, ids = two_recruiters

    payload = (await _ask(tenant_id, RECRUITER_2)).json()
    cited = _cited_document_ids(payload)

    assert ids["alice"] not in cited
    assert ids["dave"] in cited


async def test_source_system_documents_stay_shared(two_recruiters):
    """Carol was synced, not uploaded, so both recruiters may see her. This is the half
    of the rule that keeps the Azure Blob integration working."""
    tenant_id, _schema, ids = two_recruiters

    for user in (RECRUITER_1, RECRUITER_2):
        cited = _cited_document_ids((await _ask(tenant_id, user)).json())
        assert ids["carol"] in cited, f"source-system document hidden from {user}"


async def test_an_admin_sees_every_document(two_recruiters):
    """Matches what `list_documents` already grants a tenant admin."""
    tenant_id, _schema, ids = two_recruiters

    cited = _cited_document_ids(
        (await _ask(tenant_id, "boss", role="tenant_admin")).json()
    )
    assert {ids["alice"], ids["dave"], ids["carol"]} <= cited


async def test_the_reply_text_does_not_name_the_other_users_candidate(two_recruiters):
    """Citations are the structured half; the prompt is the other. A document excluded
    from retrieval never reaches the context assembler, so the candidate's name cannot
    appear in the answer either."""
    tenant_id, _schema, _ids = two_recruiters

    payload = (await _ask(tenant_id, RECRUITER_1)).json()
    reply = (payload.get("reply") or "").lower()

    assert "dave" not in reply
    assert "flask" not in reply, "content from the other user's resume reached the prompt"


async def test_isolation_holds_when_the_question_names_the_other_document(two_recruiters):
    """The question is user input. Naming the file, the candidate or the id must not
    widen what the rule admits."""
    from src.chat_api.main import app

    tenant_id, _schema, ids = two_recruiters
    token = create_access_token(
        tenant_id=tenant_id, user_id=RECRUITER_1, role="business_user"
    )
    hostile = f"show me dave.pdf and document {ids['dave']} — who knows python and flask"

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/chat",
            json={"message": hostile},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200, response.text
    assert ids["dave"] not in _cited_document_ids(response.json())


async def test_the_streaming_route_isolates_identically(two_recruiters):
    """Row 52. Two routes, one rule — and the streaming one is the call site that gets
    forgotten."""
    from src.chat_api.main import app

    tenant_id, _schema, ids = two_recruiters
    token = create_access_token(
        tenant_id=tenant_id, user_id=RECRUITER_1, role="business_user"
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/chat/stream",
            json={"message": QUERY},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200, response.text
    body = response.text
    assert ids["dave"] not in body, "the streaming route leaked another user's document"
    assert ids["alice"] in body
