import pytest
from src.chat_api.api.v1.schemas import ChatRequest, ChatResponse, ConversationSummary, ConversationDetail, MessageResponse, Source, Citation, ConversationCreateResponse

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
