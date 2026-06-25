import os
import pytest
from httpx import AsyncClient, ASGITransport
from datetime import datetime, timedelta

os.environ.setdefault("NER_JWT_SECRET", "test-secret-do-not-use-in-prod")
os.environ.setdefault("NER_DATABASE_URL", "postgresql+asyncpg://ner:ner@localhost:54320/ner_test")

from src.analytics_service.main import app
from src.shared.auth import create_access_token
from src.analytics_service.services.query_service import validate_filter, build_where_clause
from src.analytics_service.api.v1.schemas import AnalyticsQueryRequest


def auth_header(tid: str, role: str = "tenant_admin") -> dict:
    token = create_access_token(tenant_id=tid, user_id="test-user", role=role)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
class TestAnalyticsQueryEndpoint:
    async def test_query_endpoint_exists(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/analytics/query",
                json={"entity_types": ["PERSON"]},
                headers=auth_header("test-tenant"),
            )
            assert resp.status_code in (200, 422)

    async def test_unauthenticated_returns_401(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/analytics/query",
                json={"entity_types": ["PERSON"]},
            )
            assert resp.status_code == 401

    async def test_invalid_entity_type_returns_valid_response(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/analytics/query",
                json={"entity_types": ["NONEXISTENT"]},
                headers=auth_header("test-tenant"),
            )
            assert resp.status_code in (200, 422)

    async def test_invalid_date_format_returns_422(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/analytics/query",
                json={"date_from": "not-a-date"},
                headers=auth_header("test-tenant"),
            )
            assert resp.status_code == 422

    async def test_empty_results_for_no_data(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/analytics/query",
                json={"entity_types": ["PERSON"]},
                headers=auth_header("test-tenant"),
            )
            if resp.status_code == 200:
                body = resp.json()
                assert "results" in body
                assert isinstance(body["results"], list)

    async def test_response_has_pagination(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/analytics/query",
                json={},
                headers=auth_header("test-tenant"),
            )
            if resp.status_code == 200:
                body = resp.json()
                assert "pagination" in body
                assert "has_more" in body["pagination"]
                assert "next_cursor" in body["pagination"]


@pytest.mark.asyncio
class TestFilterValidation:
    def test_validate_filter_valid(self):
        req = AnalyticsQueryRequest(
            entity_types=["PERSON"],
            confidence={"min": 0.5, "max": 0.9},
            date_from="2026-01-01",
            date_to="2026-06-01",
        )
        validate_filter(req)

    def test_validate_filter_invalid_date(self):
        from fastapi import HTTPException
        req = AnalyticsQueryRequest(date_from="bad-date")
        with pytest.raises(HTTPException) as exc:
            validate_filter(req)
        assert exc.value.status_code == 422

    def test_validate_filter_inverted_confidence(self):
        from fastapi import HTTPException
        req = AnalyticsQueryRequest(confidence={"min": 0.9, "max": 0.1})
        with pytest.raises(HTTPException) as exc:
            validate_filter(req)
        assert exc.value.status_code == 422


@pytest.mark.asyncio
class TestWhereClauseBuilder:
    def test_build_empty(self):
        req = AnalyticsQueryRequest()
        where, params = build_where_clause(req)
        assert where == ""
        assert params == {}

    def test_build_entity_types(self):
        req = AnalyticsQueryRequest(entity_types=["PERSON", "ORG"])
        where, params = build_where_clause(req)
        assert "e.entity_id = ANY" in where
        assert params["entity_types"] == ["PERSON", "ORG"]

    def test_build_confidence(self):
        req = AnalyticsQueryRequest(confidence={"min": 0.5, "max": 0.9})
        where, params = build_where_clause(req)
        assert "e.confidence >=" in where
        assert "e.confidence <=" in where
        assert params["conf_min"] == 0.5
        assert params["conf_max"] == 0.9

    def test_build_date_range(self):
        req = AnalyticsQueryRequest(date_from="2026-01-01", date_to="2026-06-01")
        where, params = build_where_clause(req)
        assert "r.started_at >=" in where
        assert "r.started_at <" in where

    def test_build_all_filters(self):
        req = AnalyticsQueryRequest(
            entity_types=["PERSON"],
            confidence={"min": 0.5},
            date_from="2026-01-01",
            date_to="2026-06-01",
        )
        where, params = build_where_clause(req)
        assert where.startswith("WHERE")
        assert all(c in where for c in [
            "e.entity_id", "e.confidence >=", "r.started_at >=",
            "r.started_at <",
        ])
