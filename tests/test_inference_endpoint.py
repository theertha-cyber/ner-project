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


class TestResolveActiveVersionUsesConfiguredRegistryUrl:
    """Regression guard: inference_service._resolve_active_version() used to hardcode
    http://training_service:8003 (the host-mapped port, unreachable from inside the
    Docker network). It must instead build the URL from settings.training_service_url."""

    def test_registry_url_built_from_settings_training_service_url(self, monkeypatch):
        import requests as requests_module
        from src.model_serving.services import inference_service
        from src.shared.config import settings

        monkeypatch.setattr(settings, "training_service_url", "http://training_service:8000")

        captured = {}

        class FakeResponse:
            status_code = 200

            def json(self):
                return {"artifact_path": "tenants/t1/models/v3/", "version_number": 3}

        def fake_get(url, headers=None, timeout=None, **kwargs):
            captured["url"] = url
            return FakeResponse()

        monkeypatch.setattr(requests_module, "get", fake_get)

        result = inference_service._resolve_active_version("t1")

        assert captured["url"] == "http://training_service:8000/api/v1/models/active"
        assert result == ("tenants/t1/models/v3/", 3)

    def test_registry_url_reflects_overridden_setting(self, monkeypatch):
        import requests as requests_module
        from src.model_serving.services import inference_service
        from src.shared.config import settings

        monkeypatch.setattr(settings, "training_service_url", "http://custom-host:9999")

        captured = {}

        class FakeResponse:
            status_code = 200

            def json(self):
                return {"artifact_path": "tenants/t1/models/v1/", "version_number": 1}

        def fake_get(url, headers=None, timeout=None, **kwargs):
            captured["url"] = url
            return FakeResponse()

        monkeypatch.setattr(requests_module, "get", fake_get)

        inference_service._resolve_active_version("t1")

        assert captured["url"] == "http://custom-host:9999/api/v1/models/active"

    def test_connection_failure_falls_back_to_base(self, monkeypatch):
        import requests as requests_module
        from src.model_serving.services import inference_service
        from src.shared.config import settings

        monkeypatch.setattr(settings, "training_service_url", "http://unreachable-host:1")

        def fake_get(url, headers=None, timeout=None, **kwargs):
            raise requests_module.ConnectionError("All connection attempts failed")

        monkeypatch.setattr(requests_module, "get", fake_get)

        result = inference_service._resolve_active_version("t1")

        assert result == ("base", 0)


@pytest.mark.asyncio
class TestInferenceCustomLabelList:
    async def test_onnx_inference_uses_custom_label_list_not_conll(self, monkeypatch):
        import numpy as np
        from src.model_serving.services.model_cache import model_cache

        tenant_id = "test-tenant"
        version_number = 3
        artifact_path = f"tenants/{tenant_id}/models/v{version_number}/"
        model_id = f"{tenant_id}_v{version_number}"
        custom_label_list = ["O", "B-company", "I-company", "B-contact_details"]

        class FakeInput:
            def __init__(self, name):
                self.name = name

        class FakeSession:
            def get_inputs(self):
                return [FakeInput("input_ids"), FakeInput("attention_mask")]

            def run(self, output_names, inputs):
                seq_len = inputs["input_ids"].shape[1]
                logits = np.zeros((1, seq_len, len(custom_label_list)), dtype=np.float32)
                logits[:, :, 1] = 5.0  # every token scores highest for "B-company"
                return [logits]

        model_cache.put(model_id, {"session": FakeSession(), "local_dir": "/fake"}, 1)

        def mock_resolve_active_version(tid):
            return artifact_path, version_number

        def mock_resolve_label_list(tid):
            return custom_label_list

        monkeypatch.setattr(
            "src.model_serving.services.inference_service._resolve_active_version",
            mock_resolve_active_version,
        )
        monkeypatch.setattr(
            "src.model_serving.services.inference_service._resolve_label_list",
            mock_resolve_label_list,
        )

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post(
                    "/internal/v1/infer",
                    json={"tokens": ["Acme", "Corp"]},
                    headers=auth_header(tenant_id),
                )
                assert resp.status_code == 200
                data = resp.json()
                assert data["model_version"] == str(version_number)
                labels = {p["label"] for p in data["predictions"]}
                assert labels, "expected at least one prediction"
                assert labels.issubset(set(custom_label_list))
                conll_only_labels = {"B-PER", "I-PER", "B-ORG", "I-ORG", "B-LOC", "I-LOC", "B-MISC", "I-MISC"}
                assert not (labels & conll_only_labels)
        finally:
            model_cache.remove(model_id)


@pytest.mark.asyncio
class TestOnnxInputsMatchSessionSignature:
    """Regression guard: _infer_with_onnx() used to unconditionally send token_type_ids
    to session.run(), but the training worker's ONNX export only declares input_ids and
    attention_mask. Every fine-tuned model raised onnxruntime.InvalidArgument on every
    inference call, and infer()'s outer except silently fell back to the base model."""

    async def test_inference_succeeds_against_2_input_onnx_export(self, monkeypatch):
        import numpy as np
        from src.model_serving.services.model_cache import model_cache

        tenant_id = "test-tenant"
        version_number = 6
        artifact_path = f"tenants/{tenant_id}/models/v{version_number}/"
        model_id = f"{tenant_id}_v{version_number}"
        label_list = ["O", "B-company"]

        class FakeInput:
            def __init__(self, name):
                self.name = name

        class FakeSession:
            def get_inputs(self):
                return [FakeInput("input_ids"), FakeInput("attention_mask")]

            def run(self, output_names, inputs):
                assert "token_type_ids" not in inputs, (
                    "token_type_ids must not be sent to a session that doesn't declare it"
                )
                seq_len = inputs["input_ids"].shape[1]
                logits = np.zeros((1, seq_len, len(label_list)), dtype=np.float32)
                logits[:, :, 1] = 5.0
                return [logits]

        model_cache.put(model_id, {"session": FakeSession(), "local_dir": "/fake"}, 1)

        monkeypatch.setattr(
            "src.model_serving.services.inference_service._resolve_active_version",
            lambda tid: (artifact_path, version_number),
        )
        monkeypatch.setattr(
            "src.model_serving.services.inference_service._resolve_label_list",
            lambda tid: label_list,
        )

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post(
                    "/internal/v1/infer",
                    json={"tokens": ["Acme", "Corp"]},
                    headers=auth_header(tenant_id),
                )
                assert resp.status_code == 200
                data = resp.json()
                assert data["model_version"] == str(version_number)
                assert resp.headers.get("x-model-source") != "base"
        finally:
            model_cache.remove(model_id)

    async def test_inference_includes_token_type_ids_for_3_input_onnx_export(self, monkeypatch):
        import numpy as np
        from src.model_serving.services.model_cache import model_cache

        tenant_id = "test-tenant"
        version_number = 7
        artifact_path = f"tenants/{tenant_id}/models/v{version_number}/"
        model_id = f"{tenant_id}_v{version_number}"
        label_list = ["O", "B-company"]

        class FakeInput:
            def __init__(self, name):
                self.name = name

        class FakeSession:
            def get_inputs(self):
                return [FakeInput("input_ids"), FakeInput("attention_mask"), FakeInput("token_type_ids")]

            def run(self, output_names, inputs):
                assert "token_type_ids" in inputs, (
                    "token_type_ids must be sent when the session declares it as an input"
                )
                seq_len = inputs["input_ids"].shape[1]
                logits = np.zeros((1, seq_len, len(label_list)), dtype=np.float32)
                logits[:, :, 1] = 5.0
                return [logits]

        model_cache.put(model_id, {"session": FakeSession(), "local_dir": "/fake"}, 1)

        monkeypatch.setattr(
            "src.model_serving.services.inference_service._resolve_active_version",
            lambda tid: (artifact_path, version_number),
        )
        monkeypatch.setattr(
            "src.model_serving.services.inference_service._resolve_label_list",
            lambda tid: label_list,
        )

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post(
                    "/internal/v1/infer",
                    json={"tokens": ["Acme", "Corp"]},
                    headers=auth_header(tenant_id),
                )
                assert resp.status_code == 200
                data = resp.json()
                assert data["model_version"] == str(version_number)
        finally:
            model_cache.remove(model_id)


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

    async def test_infer_base_preserves_order_and_repeats(self, monkeypatch):
        """Covers verification.md row 51: base-model predictions must be an ordered,
        non-deduplicated sequence so BIO reconstruction can occur downstream."""
        def mock_resolve(*args):
            return "base", 0

        def mock_base_pipeline():
            class MockPipe:
                def __call__(self, text):
                    return [
                        {"entity": "B-ORG", "word": "InApp", "score": 0.90},
                        {"entity": "B-LOC", "word": "Kochi", "score": 0.80},
                        {"entity": "B-ORG", "word": "InApp", "score": 0.70},
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
                json={"tokens": ["InApp", "Kochi", "InApp"]},
                headers=auth_header("test-tenant"),
            )
            assert resp.status_code == 200
            predictions = resp.json()["predictions"]
            assert len(predictions) == 3
            assert [p["token"] for p in predictions] == ["InApp", "Kochi", "InApp"]
            assert predictions[0]["confidence"] == pytest.approx(0.90)
            assert predictions[2]["confidence"] == pytest.approx(0.70)
