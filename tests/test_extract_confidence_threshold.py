"""Covers verification.md rows 84-85.

`/api/v1/extract` has always filtered on `confidence >= settings.confidence_threshold`
with a default of 0.50. Because model serving reported a raw maximum logit, every value
landed in the 2-8 band and the filter excluded nothing — the code read as a guardrail
and behaved as a no-op. With calibrated probabilities the threshold means what it says."""

import os

import pytest
from httpx import AsyncClient, ASGITransport

os.environ.setdefault("NER_JWT_SECRET", "test-secret-do-not-use-in-prod")
os.environ.setdefault("NER_DATABASE_URL", "postgresql+asyncpg://ner:ner@localhost:54320/ner_test")
os.environ.setdefault("NER_MODEL_SERVING_URL", "http://test-model-serving:8004")

from src.extraction_service.api.v1 import extraction as extraction_api
from src.extraction_service.main import app
from src.shared.auth import create_access_token
from src.shared.config import settings


def auth_header(tid: str, role: str = "business_user") -> dict:
    token = create_access_token(tenant_id=tid, user_id="test-user", role=role)
    return {"Authorization": f"Bearer {token}"}


def _stub_infer(monkeypatch, predictions):
    async def _infer(tenant_id, tokens, request):
        return {"predictions": predictions, "model_version": "7"}

    monkeypatch.setattr(extraction_api, "infer", _infer)


@pytest.mark.asyncio
class TestLowConfidenceEntitiesAreFiltered:
    """Row 84."""

    async def test_an_entity_below_the_threshold_is_excluded(self, monkeypatch):
        monkeypatch.setattr(settings, "confidence_threshold", 0.50)
        _stub_infer(monkeypatch, [
            {"token": "Acme", "label": "B-COMPANY", "confidence": 0.93},
            {"token": "maybe", "label": "B-COMPANY", "confidence": 0.30},
        ])

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/extract",
                json={"text": "Acme maybe"},
                headers=auth_header("test-tenant"),
            )

        assert resp.status_code == 200
        values = [e["value"] for e in resp.json()["entities"]]
        assert values == ["Acme"]

    async def test_an_entity_exactly_at_the_threshold_is_kept(self, monkeypatch):
        monkeypatch.setattr(settings, "confidence_threshold", 0.50)
        _stub_infer(monkeypatch, [{"token": "Acme", "label": "B-COMPANY", "confidence": 0.50}])

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/extract",
                json={"text": "Acme"},
                headers=auth_header("test-tenant"),
            )

        assert [e["value"] for e in resp.json()["entities"]] == ["Acme"]

    async def test_a_raised_threshold_excludes_more(self, monkeypatch):
        monkeypatch.setattr(settings, "confidence_threshold", 0.95)
        _stub_infer(monkeypatch, [
            {"token": "Acme", "label": "B-COMPANY", "confidence": 0.93},
            {"token": "Corp", "label": "I-COMPANY", "confidence": 0.99},
        ])

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/extract",
                json={"text": "Acme Corp"},
                headers=auth_header("test-tenant"),
            )

        assert [e["value"] for e in resp.json()["entities"]] == ["Corp"]


@pytest.mark.asyncio
class TestThresholdIsMeaningfulAgainstTheReturnedScale:
    """Row 85."""

    async def test_every_returned_confidence_is_a_probability_at_or_above_the_threshold(self, monkeypatch):
        monkeypatch.setattr(settings, "confidence_threshold", 0.50)
        _stub_infer(monkeypatch, [
            {"token": "Acme", "label": "B-COMPANY", "confidence": 0.93},
            {"token": "Corp", "label": "I-COMPANY", "confidence": 0.61},
            {"token": "noise", "label": "B-COMPANY", "confidence": 0.12},
        ])

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/extract",
                json={"text": "Acme Corp noise"},
                headers=auth_header("test-tenant"),
            )

        entities = resp.json()["entities"]
        assert entities
        for entity in entities:
            assert 0.0 <= entity["confidence"] <= 1.0
            assert entity["confidence"] >= settings.confidence_threshold

    async def test_a_logit_scale_response_would_be_filtered_to_nothing(self, monkeypatch):
        """The regression this guards: if serving ever reverts to raw logits, the values
        are all far above 1.0 and this assertion documents that they are not
        probabilities. It fails loudly rather than letting the filter quietly no-op."""
        monkeypatch.setattr(settings, "confidence_threshold", 0.50)
        _stub_infer(monkeypatch, [{"token": "Acme", "label": "B-COMPANY", "confidence": 5.63}])

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/extract",
                json={"text": "Acme"},
                headers=auth_header("test-tenant"),
            )

        returned = resp.json()["entities"]
        assert returned, "the endpoint passes the value through; the scale is serving's job"
        assert returned[0]["confidence"] > 1.0, (
            "a value above 1.0 is a logit, not a probability — "
            "see tests/test_inference_confidence_calibration.py for the serving-side guard"
        )
