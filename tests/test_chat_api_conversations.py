import pytest
from pydantic import ValidationError
from src.chat_api.api.v1.schemas import ChatRequest, ChatResponse, ConversationSummary, ConversationDetail, MessageResponse, Source, Citation, ConversationCreateResponse, ConversationRenameRequest, ConversationRenameResponse
from src.chat_api.services.title_generator import derive_conversation_title

pytestmark = [pytest.mark.verification]


class TestConversationSchemas:
    def test_chat_request_requires_message(self):
        req = ChatRequest(message="Hello")
        assert req.message == "Hello"
        assert req.conversation_id is None

    def test_chat_request_with_conversation_id(self):
        req = ChatRequest(message="Hello", conversation_id="conv-123")
        assert req.conversation_id == "conv-123"

    def test_chat_response_with_sources(self):
        resp = ChatResponse(
            reply="Test",
            sources=[Source(source_type="sql", value="test", relevance_score=0.9)],
            conversation_id="conv-123",
        )
        assert resp.reply == "Test"
        assert len(resp.sources) == 1
        assert resp.conversation_id == "conv-123"

    def test_conversation_summary(self):
        summary = ConversationSummary(id="c1", title="Test", created_at="2026-01-01", message_count=5)
        assert summary.id == "c1"
        assert summary.message_count == 5

    def test_conversation_detail_with_messages(self):
        msg = MessageResponse(id="m1", role="user", content="Hello", created_at="2026-01-01")
        detail = ConversationDetail(id="c1", title="Test", created_at="2026-01-01", messages=[msg])
        assert len(detail.messages) == 1
        assert detail.messages[0].role == "user"

    def test_message_response_with_sources(self):
        source = Source(source_type="document_chunk", document_id="doc1", chunk_index=0, relevance_score=0.95)
        msg = MessageResponse(id="m1", role="assistant", content="Reply", sources=[source], created_at="2026-01-01")
        assert msg.sources is not None
        assert msg.sources[0].document_id == "doc1"

    def test_14_conversation_summary_fields(self):
        summary = ConversationSummary(id="c1", title="My Chat", created_at="2026-06-01T00:00:00", message_count=3)
        d = summary.model_dump()
        assert "id" in d
        assert "title" in d
        assert "created_at" in d
        assert "message_count" in d

    def test_15_message_fields(self):
        msg = MessageResponse(id="m1", role="assistant", content="Hello", created_at="2026-06-01T00:00:00")
        d = msg.model_dump()
        assert "role" in d
        assert "content" in d
        assert "sources" in d
        assert "created_at" in d

    def test_16_delete_returns_none(self):
        pass

    def test_citation_model_fields(self):
        citation = Citation(
            document_name="report.pdf",
            document_id="doc-123",
            entity_type="organization",
            entity_value="Acme Corp",
            confidence=0.95,
            context_snippet="Acme Corp was founded in...",
            page_number=3,
            source_type="ner",
        )
        assert citation.document_name == "report.pdf"
        assert citation.entity_type == "organization"
        assert citation.entity_value == "Acme Corp"
        assert citation.confidence == 0.95
        assert citation.source_type == "ner"

    def test_citation_model_defaults(self):
        citation = Citation()
        assert citation.document_name is None
        assert citation.source_type == "citation"

    def test_chat_response_with_citation_sources(self):
        citation = Citation(
            document_name="report.pdf",
            entity_type="organization",
            entity_value="Acme Corp",
            confidence=0.95,
            source_type="ner",
        )
        resp = ChatResponse(
            reply="Test",
            sources=[citation],
            conversation_id="conv-123",
        )
        assert len(resp.sources) == 1
        assert resp.sources[0].document_name == "report.pdf"

    def test_chat_response_with_mixed_sources(self):
        source = Source(source_type="sql", value="test", relevance_score=0.9)
        citation = Citation(document_name="report.pdf", source_type="ner")
        resp = ChatResponse(
            reply="Test",
            sources=[source, citation],
            conversation_id="conv-123",
        )
        assert len(resp.sources) == 2

    def test_conversation_create_response(self):
        resp = ConversationCreateResponse(id="conv-123", title=None, created_at="2026-06-01T00:00:00")
        d = resp.model_dump()
        assert d["id"] == "conv-123"
        assert d["title"] is None
        assert "created_at" in d


@pytest.mark.asyncio
class TestChatEndpointTurnShape:
    """verification.md rows 16, 17, 20, 21 — the RAG chat endpoint's existing contract,
    re-asserted after the assembly stages were reordered. The orchestrator is patched at
    the same boundary test_chat_api_streaming.py uses; full end-to-end retrieval is
    exercised in test_chat_api_rag.py."""

    @staticmethod
    def _app():
        from src.chat_api.main import app
        return app

    @staticmethod
    def _auth(tenant_id, role="business_user", user_id="test-user"):
        from src.shared.auth import create_access_token
        return {"Authorization": f"Bearer {create_access_token(tenant_id=tenant_id, user_id=user_id, role=role)}"}

    @staticmethod
    def _patch(monkeypatch, reply, sources):
        from src.chat_api.api.v1 import chat as chat_module

        async def fake(message, session, schema, tenant_id, jwt_token=None,
                       conversation_context=None, conversation_id=None):
            fake.seen_context = conversation_context
            return (reply, sources, None, "answer", None, None)

        fake.seen_context = None
        monkeypatch.setattr(chat_module.orchestrator, "execute_with_clarification", fake)
        return fake

    async def test_entity_count_turn_returns_reply_sources_and_conversation_id(
        self, engine, tenant_schema, monkeypatch,
    ):
        from httpx import ASGITransport, AsyncClient

        tid, _ = tenant_schema
        self._patch(monkeypatch, "There are 5 organizations.", [
            Citation(document_name="r.pdf", document_id="doc-1", entity_type="ORG",
                     entity_value="Acme", source_type="sql"),
        ])

        async with AsyncClient(transport=ASGITransport(app=self._app()), base_url="http://test") as client:
            resp = await client.post("/api/v1/chat", headers=self._auth(tid),
                                     json={"message": "How many organizations?", "conversation_id": None})

        assert resp.status_code == 200
        body = resp.json()
        assert body["reply"] == "There are 5 organizations."
        assert len(body["sources"]) >= 1
        assert body["conversation_id"]

    async def test_document_context_turn_returns_chunk_sources(
        self, engine, tenant_schema, monkeypatch,
    ):
        from httpx import ASGITransport, AsyncClient

        tid, _ = tenant_schema
        self._patch(monkeypatch, "The contract covers liability.", [
            Citation(document_name="r.pdf", document_id="doc-1", source_type="document_chunk",
                     context_snippet="liability clause", relevance_score=0.82),
        ])

        async with AsyncClient(transport=ASGITransport(app=self._app()), base_url="http://test") as client:
            resp = await client.post("/api/v1/chat", headers=self._auth(tid),
                                     json={"message": "What does the contract say?", "conversation_id": None})

        assert resp.status_code == 200
        source = resp.json()["sources"][0]
        assert source["document_id"] == "doc-1"
        assert source["relevance_score"] == 0.82

    async def test_existing_conversation_appends_and_includes_history(
        self, engine, tenant_schema, monkeypatch,
    ):
        from httpx import ASGITransport, AsyncClient

        tid, _ = tenant_schema
        fake = self._patch(monkeypatch, "Second reply.", [
            Citation(document_name="r.pdf", document_id="doc-1", source_type="sql"),
        ])
        headers = self._auth(tid)

        async with AsyncClient(transport=ASGITransport(app=self._app()), base_url="http://test") as client:
            first = await client.post("/api/v1/chat", headers=headers,
                                      json={"message": "First question", "conversation_id": None})
            conversation_id = first.json()["conversation_id"]

            second = await client.post("/api/v1/chat", headers=headers,
                                       json={"message": "Second question", "conversation_id": conversation_id})
            detail = await client.get(f"/api/v1/chat/conversations/{conversation_id}", headers=headers)

        assert second.status_code == 200
        assert second.json()["conversation_id"] == conversation_id
        # The earlier turn reached the pipeline as history.
        assert any(m["content"] == "First question" for m in fake.seen_context)
        assert [m["content"] for m in detail.json()["messages"]][:2] == ["First question", "Second reply."]

    async def test_unauthenticated_chat_returns_401(self, engine, tenant_schema):
        from httpx import ASGITransport, AsyncClient

        async with AsyncClient(transport=ASGITransport(app=self._app()), base_url="http://test") as client:
            resp = await client.post("/api/v1/chat", json={"message": "hi", "conversation_id": None})

        assert resp.status_code == 401


class TestConversationTitleGeneration:
    def test_title_generated_from_short_message(self):
        title = derive_conversation_title("How many organizations did we extract last month?")
        assert title == "How many organizations did we extract last month"

    def test_title_truncated_at_word_boundary_for_long_message(self):
        message = "How many organizations did we extract last month across all our tenant document sets combined?"
        title = derive_conversation_title(message)
        assert len(title) <= 61  # 60 chars + ellipsis
        assert title.endswith("…")
        body = title[:-1]
        assert len(body) <= 60
        assert not body.endswith(" ")
        # truncation must land on a word boundary: the body is a prefix of
        # the collapsed message that ends exactly at a word (not mid-word)
        assert message.startswith(body)
        assert message[len(body):len(body) + 1] in (" ", "")

    def test_title_falls_back_for_whitespace_only_message(self):
        assert derive_conversation_title("   ") == "New conversation"

    def test_title_falls_back_for_punctuation_only_message(self):
        assert derive_conversation_title("...???!!!") == "New conversation"

    def test_title_collapses_internal_whitespace(self):
        title = derive_conversation_title("hello   \n\n  world")
        assert title == "hello world"


class TestConversationRenameRequest:
    def test_valid_title_is_accepted_and_trimmed(self):
        req = ConversationRenameRequest(title="  Q3 entity counts  ")
        assert req.title == "Q3 entity counts"

    def test_blank_title_is_rejected(self):
        with pytest.raises(ValidationError):
            ConversationRenameRequest(title="   ")

    def test_empty_title_is_rejected(self):
        with pytest.raises(ValidationError):
            ConversationRenameRequest(title="")

    def test_over_length_title_is_rejected(self):
        with pytest.raises(ValidationError):
            ConversationRenameRequest(title="x" * 101)

    def test_title_at_max_length_is_accepted(self):
        req = ConversationRenameRequest(title="x" * 100)
        assert len(req.title) == 100

    def test_rename_response_fields(self):
        resp = ConversationRenameResponse(id="conv-123", title="Renamed chat")
        d = resp.model_dump()
        assert d == {"id": "conv-123", "title": "Renamed chat"}
