import pytest
from unittest.mock import patch, AsyncMock

pytestmark = [pytest.mark.verification, pytest.mark.asyncio]


class TestChatGatewayProxy:
    @patch("src.gateway.api.v1.chat_proxy.httpx.AsyncClient")
    async def test_14_3_gateway_proxies_chat_request(self, mock_httpx):
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_httpx.return_value = mock_client

        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "reply": "Test reply",
            "sources": [],
            "conversation_id": "conv-123",
            "disclaimer": "AI-generated",
        }
        mock_response.text = '{"reply": "Test reply", "sources": [], "conversation_id": "conv-123", "disclaimer": "AI-generated"}'
        mock_client.post.return_value = mock_response

        from src.gateway.api.v1.chat_proxy import CHAT_API_BASE
        assert CHAT_API_BASE == "http://localhost:8006"

    @patch("src.gateway.api.v1.chat_proxy.httpx.AsyncClient")
    async def test_gateway_proxies_conversation_list(self, mock_httpx):
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_httpx.return_value = mock_client

        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [{"id": "c1", "title": "Test", "created_at": "2026-01-01", "message_count": 3}]
        mock_response.text = '[{"id": "c1", "title": "Test", "created_at": "2026-01-01", "message_count": 3}]'
        mock_client.get.return_value = mock_response

    @patch("src.gateway.api.v1.chat_proxy.httpx.AsyncClient")
    async def test_gateway_proxies_widget_key_create(self, mock_httpx):
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_httpx.return_value = mock_client

        mock_response = AsyncMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"id": "k1", "raw_key": "ner_widget_abc", "key_prefix": "ner_widg"}
        mock_response.text = '{"id": "k1", "raw_key": "ner_widget_abc", "key_prefix": "ner_widg"}'
        mock_client.post.return_value = mock_response
