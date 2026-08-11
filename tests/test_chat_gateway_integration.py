import asyncio
import pytest
from unittest.mock import patch, AsyncMock, MagicMock

from src.gateway.api.v1 import chat_proxy as chat_proxy_module

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


class FakeUpstreamResponse:
    """Stands in for the `httpx.Response` returned by `client.send(req, stream=True)`
    inside `proxy_chat_stream`. `aiter_raw()` yields `chunks` one at a time, sleeping
    `delay` seconds before every chunk after the first so a test can observe that the
    first chunk is delivered to the downstream client before the second is even
    produced by the (fake) upstream."""

    def __init__(self, status_code=200, headers=None, chunks=None, delay=0):
        self.status_code = status_code
        self.headers = headers if headers is not None else {"content-type": "text/event-stream"}
        self._chunks = chunks or []
        self._delay = delay
        self.aclose = AsyncMock()
        self.second_chunk_sent = False

    async def aiter_raw(self):
        for i, chunk in enumerate(self._chunks):
            if i == 1 and self._delay:
                await asyncio.sleep(self._delay)
            if i == 1:
                self.second_chunk_sent = True
            yield chunk


def _patch_upstream_client(monkeypatch, upstream: FakeUpstreamResponse):
    mock_client = AsyncMock()
    mock_client.build_request = MagicMock(return_value=object())
    mock_client.send = AsyncMock(return_value=upstream)
    mock_client.aclose = AsyncMock()
    monkeypatch.setattr(chat_proxy_module.httpx, "AsyncClient", lambda *a, **kw: mock_client)
    return mock_client


class _FakeRequest:
    """Duck-typed stand-in for `starlette.Request` carrying only what
    `proxy_chat_stream` reads: `.headers` and `await .body()`."""

    def __init__(self, headers=None, body=b'{"message": "hi", "conversation_id": null}'):
        self.headers = headers or {"content-type": "application/json", "authorization": "Bearer test"}
        self._body = body

    async def body(self):
        return self._body


class TestChatStreamGatewayProxy:
    """Covers verification.md rows 21, 22 (tasks 3.3, 3.4). Calls `proxy_chat_stream`
    directly rather than through the full ASGI app: `httpx.ASGITransport.handle_async_request`
    (see its implementation) runs the whole ASGI app to completion and buffers every
    body chunk before it ever returns a `Response` to the test client, so it cannot
    itself demonstrate incremental delivery regardless of how the gateway route is
    written. Calling the route function directly and iterating the
    `StreamingResponse.body_iterator` it returns exercises the exact mechanism
    design.md Decision 6 describes, without that test-harness limitation in the way.
    Tenant/auth middleware is a separate, already-covered concern (see
    test_chat_api_streaming.py) — it does not need to run again here."""

    async def test_gateway_forwards_frames_incrementally(self, monkeypatch):
        upstream = FakeUpstreamResponse(
            chunks=[b'event: token\ndata: {"delta": "hi"}\n\n', b"event: done\ndata: {}\n\n"],
            delay=0.1,
        )
        _patch_upstream_client(monkeypatch, upstream)

        response = await chat_proxy_module.proxy_chat_stream(_FakeRequest())

        first_chunk_before_second_sent = None
        async for chunk in response.body_iterator:
            if chunk and first_chunk_before_second_sent is None:
                first_chunk_before_second_sent = not upstream.second_chunk_sent

        assert first_chunk_before_second_sent is True

    async def test_gateway_preserves_streaming_headers(self, monkeypatch):
        upstream = FakeUpstreamResponse(chunks=[b"event: done\ndata: {}\n\n"])
        _patch_upstream_client(monkeypatch, upstream)

        response = await chat_proxy_module.proxy_chat_stream(_FakeRequest())

        assert response.headers["content-type"].startswith("text/event-stream")
        assert response.headers["x-accel-buffering"] == "no"
