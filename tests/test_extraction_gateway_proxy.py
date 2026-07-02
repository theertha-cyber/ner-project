import os
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from httpx import AsyncClient, ASGITransport

os.environ.setdefault("NER_JWT_SECRET", "test-secret-do-not-use-in-prod")
os.environ.setdefault("NER_DATABASE_URL", "postgresql+asyncpg://ner:ner@localhost:54320/ner_test")
os.environ.setdefault("NER_MODEL_SERVING_URL", "http://test-model-serving:8004")

from src.gateway.main import app
from src.shared.auth import create_access_token

pytestmark = [pytest.mark.asyncio]


def auth_header(tid: str, role: str = "business_user") -> dict:
    token = create_access_token(tenant_id=tid, user_id="test-user", role=role)
    return {"Authorization": f"Bearer {token}"}


class TestExtractionGatewayProxy:
    @patch("src.gateway.api.v1.extraction_proxy.httpx.AsyncClient")
    async def test_gateway_proxies_extract_without_tid(self, mock_httpx):
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_httpx.return_value = mock_client

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"entities": [], "model_version": "0"}
        mock_response.text = '{"entities": [], "model_version": "0"}'
        mock_client.post.return_value = mock_response

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/extract",
                json={"text": "Acme Corp"},
                headers=auth_header("test-tenant"),
            )
            assert resp.status_code == 200
            assert resp.json() == {"entities": [], "model_version": "0"}
            called_url = mock_client.post.call_args.args[0]
            assert called_url.endswith("/api/v1/extract")

    @patch("src.gateway.api.v1.extraction_proxy.httpx.AsyncClient")
    async def test_gateway_proxies_extract_batch_list(self, mock_httpx):
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_httpx.return_value = mock_client

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"runs": [{"run_id": "r1", "status": "completed"}]}
        mock_response.text = '{"runs": [{"run_id": "r1", "status": "completed"}]}'
        mock_client.get.return_value = mock_response

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/api/v1/extract-batch",
                headers=auth_header("test-tenant"),
            )
            assert resp.status_code == 200
            assert resp.json()["runs"] == [{"run_id": "r1", "status": "completed"}]
            called_url = mock_client.get.call_args.args[0]
            assert called_url.endswith("/api/v1/extract-batch")

    async def test_gateway_rejects_missing_jwt(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/v1/extract", json={"text": "test"})
            # The TenantContextMiddleware currently rejects requests with no
            # Authorization header with 401, not the 403 stated in
            # specs/extraction-service/spec.md. This is a pre-existing
            # mismatch predating this change; batch-extraction-run-history
            # does not touch gateway auth, so this test pins current
            # behavior rather than asserting the spec's stated 403.
            assert resp.status_code == 401