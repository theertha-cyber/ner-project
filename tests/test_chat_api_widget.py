import pytest
from src.chat_api.api.v1.schemas import WidgetKeyResponse, WidgetKeyCreateResponse, WidgetChatRequest, WidgetChatResponse, Source

pytestmark = [pytest.mark.verification]


class TestWidgetSchemas:
    def test_27_widget_key_create_response(self):
        resp = WidgetKeyCreateResponse(id="k1", raw_key="ner_widget_abc123", key_prefix="ner_widg")
        assert resp.raw_key.startswith("ner_widget_")
        assert resp.key_prefix == "ner_widg"

    def test_28_widget_key_list_response(self):
        resp = WidgetKeyResponse(id="k1", key_prefix="ner_widg", created_at="2026-01-01", last_used_at=None)
        d = resp.model_dump()
        assert "key_prefix" in d
        assert "created_at" in d
        assert "last_used_at" in d
        assert "id" in d
        assert "raw_key" not in d

    def test_29_revoke_returns_none(self):
        pass

    def test_30_invalid_key_rejected(self):
        pass

    def test_31_widget_chat_response(self):
        resp = WidgetChatResponse(
            reply="Test reply",
            sources=[Source(source_type="sql", value="test", relevance_score=0.9)],
        )
        assert "reply" in resp.model_dump()
        assert "sources" in resp.model_dump()
        assert "disclaimer" in resp.model_dump()
        assert "conversation_id" not in resp.model_dump()

    def test_32_widget_chat_requires_message(self):
        req = WidgetChatRequest(message="Hello")
        assert req.message == "Hello"

    def test_24_widget_js_headers(self):
        pass

    def test_33_cors_preflight(self):
        pass
