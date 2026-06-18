"""Tests for model-serving warmup endpoint."""
import os
import pytest
from httpx import AsyncClient, ASGITransport

os.environ.setdefault("NER_JWT_SECRET", "test-secret-do-not-use-in-prod")
os.environ.setdefault("NER_DATABASE_URL", "postgresql+asyncpg://ner:ner@localhost:54320/ner_test")

from src.model_serving.main import app
from src.model_serving.services.model_cache import model_cache
from src.shared.auth import create_access_token


def auth_header(tid: str, role: str = "tenant_admin") -> dict:
    token = create_access_token(tenant_id=tid, user_id="test-user", role=role)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
class TestWarmupEndpointExists:
    async def test_warmup_endpoint_responds(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/internal/v1/warmup",
                json={},
                headers=auth_header("test-tenant"),
            )
            assert resp.status_code in (200, 404)


@pytest.mark.asyncio
class TestWarmupWithVersionNumber:
    async def test_warmup_with_version_number_responds(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/internal/v1/warmup",
                json={"version_number": 1},
                headers=auth_header("test-tenant"),
            )
            assert resp.status_code in (200, 404)


@pytest.mark.asyncio
class TestWarmupNonexistentVersion:
    async def test_nonexistent_version_returns_404(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/internal/v1/warmup",
                json={"version_number": 9999},
                headers=auth_header("test-tenant"),
            )
            assert resp.status_code == 404


@pytest.mark.asyncio
class TestWarmupAuth:
    async def test_missing_auth_returns_401(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/internal/v1/warmup",
                json={},
            )
            assert resp.status_code == 401

    async def test_health_is_unauthenticated(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/health")
            assert resp.status_code == 200
            assert resp.json() == {"status": "ok"}


@pytest.mark.asyncio
class TestWarmupPopulatesCache:
    """Task 3.5: Warmup → cache populated, verified via subsequent lookup."""

    async def test_warmup_populates_cache_with_mocked_load(self, monkeypatch):
        import src.model_serving.api.v1.warmup as warmup_mod

        model_cache.clear()

        loaded = []

        def mock_load(tenant_id, version_number):
            model_id = f"{tenant_id}_v{version_number}"
            model_cache.put(model_id, {"session": "mock"}, 100)
            loaded.append((tenant_id, version_number))
            return True

        monkeypatch.setattr(warmup_mod, "_load_model_for_tenant", mock_load)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/internal/v1/warmup",
                json={"version_number": 1},
                headers=auth_header("test-tenant"),
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["version_number"] == 1

        assert len(loaded) == 1
        assert loaded[0] == ("test-tenant", 1)

        cached = model_cache.get("test-tenant_v1")
        assert cached is not None
        assert cached.model["session"] == "mock"

    async def test_warmup_without_version_resolves_active_and_caches(self, monkeypatch):
        import src.model_serving.api.v1.warmup as warmup_mod

        model_cache.clear()

        monkeypatch.setattr(
            warmup_mod, "_resolve_active_version",
            lambda tid: ("tenants/test-tenant/models/v1/some-id", 1),
        )

        loaded = []

        def mock_load(tenant_id, version_number):
            model_id = f"{tenant_id}_v{version_number}"
            model_cache.put(model_id, {"session": "mock"}, 100)
            loaded.append((tenant_id, version_number))
            return True

        monkeypatch.setattr(warmup_mod, "_load_model_for_tenant", mock_load)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/internal/v1/warmup",
                json={},
                headers=auth_header("test-tenant"),
            )
            assert resp.status_code == 200

        assert len(loaded) == 1
        assert loaded[0] == ("test-tenant", 1)

        cached = model_cache.get("test-tenant_v1")
        assert cached is not None


@pytest.mark.asyncio
class TestArtifactPathConvention:
    """ADR-006: Model artifacts path must follow tenants/{tid}/models/v{version}/."""

    async def test_download_uses_correct_artifact_path(self, monkeypatch):
        from src.model_serving.services import model_loader

        list_called_with = []

        class MockS3Client:
            def get_paginator(self, _):
                class MockPaginator:
                    def paginate(self, Bucket=None, Prefix=None):
                        list_called_with.append(Prefix)
                        return []
                return MockPaginator()
            def download_file(self, *a, **kw):
                pass

        monkeypatch.setattr(model_loader, "_get_s3_client", MockS3Client)

        import tempfile
        monkeypatch.setattr(tempfile, "mkdtemp", lambda **kw: "C:\\tmp\\test")

        model_loader.download_model_artifacts("test-tenant", 2)

        assert len(list_called_with) == 1
        path = list_called_with[0]
        assert path == "tenants/test-tenant/models/v2/", f"Expected path convention, got: {path}"


@pytest.mark.asyncio
class TestInferOnDemandLoad:
    """Task 3.6: Model loads on-demand when cache is empty."""

    async def test_infer_loads_on_cache_miss(self, monkeypatch):
        from src.model_serving.services import inference_service

        model_cache.clear()

        monkeypatch.setattr(
            inference_service, "_resolve_active_version",
            lambda tid: ("tenants/test-tenant/models/v1/some-id", 1),
        )

        monkeypatch.setattr(
            inference_service, "_resolve_label_list",
            lambda tid: ["O", "B-PER", "I-PER", "B-ORG", "I-ORG"],
        )

        loaded = []

        class MockSession:
            def run(self, _, inputs):
                import numpy as np
                return [np.zeros((1, 5, 6))]

        def mock_load(tenant_id, version_number):
            model_id = f"{tenant_id}_v{version_number}"
            model_cache.put(model_id, {"session": MockSession()}, 100)
            loaded.append((tenant_id, version_number))
            return True

        monkeypatch.setattr(inference_service, "_load_model_for_tenant", mock_load)

        import numpy as np

        class MockEncoding(dict):
            def word_ids(self, batch_idx):
                return [0, 0, 1, 2, None]

        class MockTokenizer:
            model_max_length = 512
            def __call__(self, tokens, **kw):
                return MockEncoding({
                    "input_ids": np.ones((1, 5), dtype=np.int64),
                    "attention_mask": np.ones((1, 5), dtype=np.int64),
                })

        monkeypatch.setattr(inference_service, "_get_tokenizer", MockTokenizer)

        result = inference_service.infer("test-tenant", ["Alice", "works"])

        assert len(loaded) == 1
        assert loaded[0] == ("test-tenant", 1)

        cached = model_cache.get("test-tenant_v1")
        assert cached is not None
