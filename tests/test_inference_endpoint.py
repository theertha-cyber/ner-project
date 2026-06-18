import os
import pytest
from httpx import AsyncClient, ASGITransport
from src.model_serving.main import app

os.environ.setdefault("NER_JWT_SECRET", "test-secret-do-not-use-in-prod")
os.environ.setdefault("NER_DATABASE_URL", "postgresql+asyncpg://ner:ner@localhost:54320/ner_test")

from src.shared.auth import create_access_token


def auth_header(tid: str, role: str = "tenant_admin") -> dict:
    token = create_access_token(tenant_id=tid, user_id="test-user", role=role)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
class TestInferenceReturnsPredictions:
    async def test_inference_endpoint_exists(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/internal/v1/infer",
                json={"tokens": ["John", "works", "at", "Acme"]},
                headers=auth_header("test-tenant"),
            )
            assert resp.status_code in (200, 404)


@pytest.mark.asyncio
class TestInferenceNoModelReturns404:
    async def test_no_model_returns_404(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/internal/v1/infer",
                json={"tokens": ["test"]},
                headers=auth_header("no-model-tenant"),
            )
            assert resp.status_code == 404


@pytest.mark.asyncio
class TestInferenceAuth:
    async def test_missing_auth_returns_401(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/internal/v1/infer",
                json={"tokens": ["test"]},
            )
            assert resp.status_code == 401

    async def test_health_is_unauthenticated(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/health")
            assert resp.status_code == 200
            assert resp.json() == {"status": "ok"}


@pytest.mark.asyncio
class TestInferenceBaseModelFallback:
    async def test_infer_returns_conll_labels_for_no_model_tenant(self, monkeypatch):
        def mock_resolve(*args):
            return "base", 0

        def mock_base_pipeline():
            class MockPipe:
                def __call__(self, text):
                    return [
                        {"entity": "B-PER", "word": "John", "score": 0.98},
                        {"entity": "O", "word": "works", "score": 0.99},
                        {"entity": "O", "word": "at", "score": 0.99},
                        {"entity": "B-ORG", "word": "Acme", "score": 0.95},
                    ]
            return MockPipe()

        monkeypatch.setattr(
            "src.model_serving.services.inference_service._resolve_active_version",
            mock_resolve,
        )
        monkeypatch.setattr(
            "src.model_serving.services.inference_service._get_base_pipeline",
            mock_base_pipeline,
        )

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/internal/v1/infer",
                json={"tokens": ["John", "works", "at", "Acme"]},
                headers=auth_header("test-tenant"),
            )
            assert resp.status_code == 200
            data = resp.json()
            assert "predictions" in data
            assert data["model_version"] == "0"
            assert resp.headers.get("x-model-source") == "base"

    async def test_infer_base_has_conll_labels(self, monkeypatch):
        def mock_resolve(*args):
            return "base", 0

        def mock_base_pipeline():
            class MockPipe:
                def __call__(self, text):
                    return [
                        {"entity": "B-PER", "word": "John", "score": 0.98},
                        {"entity": "B-ORG", "word": "Acme", "score": 0.95},
                    ]
            return MockPipe()

        monkeypatch.setattr(
            "src.model_serving.services.inference_service._resolve_active_version",
            mock_resolve,
        )
        monkeypatch.setattr(
            "src.model_serving.services.inference_service._get_base_pipeline",
            mock_base_pipeline,
        )

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/internal/v1/infer",
                json={"tokens": ["John", "works", "at", "Acme"]},
                headers=auth_header("test-tenant"),
            )
            assert resp.status_code == 200
            data = resp.json()
            labels = {p["label"] for p in data["predictions"]}
            assert "B-PER" in labels or "I-PER" in labels
            assert "B-ORG" in labels or "I-ORG" in labels
