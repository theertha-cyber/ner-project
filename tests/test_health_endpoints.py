import pytest
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient, ASGITransport


async def _get(app, path):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        return await ac.get(path)


@pytest.mark.asyncio
async def test_chat_api_health_200_when_all_dependencies_healthy():
    from src.chat_api import main as chat_main
    with patch.object(chat_main, "check_database", AsyncMock(return_value=(True, "reachable"))), \
         patch.object(chat_main, "check_http_dependency", AsyncMock(return_value=(True, "reachable"))):
        resp = await _get(chat_main.app, "/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["dependencies"]["database"]["status"] == "healthy"
    assert body["dependencies"]["model_serving"]["status"] == "healthy"


@pytest.mark.asyncio
async def test_chat_api_health_503_when_database_unhealthy():
    from src.chat_api import main as chat_main
    with patch.object(chat_main, "check_database", AsyncMock(return_value=(False, "connection refused"))), \
         patch.object(chat_main, "check_http_dependency", AsyncMock(return_value=(True, "reachable"))):
        resp = await _get(chat_main.app, "/health")
    assert resp.status_code == 503
    body = resp.json()
    assert body["dependencies"]["database"]["status"] == "unhealthy"
    assert body["dependencies"]["model_serving"]["status"] == "healthy"


@pytest.mark.asyncio
async def test_chat_api_health_stays_healthy_when_only_base_model_reachable():
    """chat_api readiness checks base model_serving reachability only — it must
    not depend on any tenant-specific model being configured (ADR-008)."""
    from src.chat_api import main as chat_main
    with patch.object(chat_main, "check_database", AsyncMock(return_value=(True, "reachable"))), \
         patch.object(chat_main, "check_http_dependency", AsyncMock(return_value=(True, "reachable"))):
        resp = await _get(chat_main.app, "/health")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_chat_api_health_live_returns_200_regardless_of_dependencies():
    from src.chat_api import main as chat_main
    resp = await _get(chat_main.app, "/health/live")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_extraction_service_health_200_when_healthy():
    from src.extraction_service import main as extraction_main
    with patch.object(extraction_main, "check_database", AsyncMock(return_value=(True, "reachable"))), \
         patch.object(extraction_main, "check_http_dependency", AsyncMock(return_value=(True, "reachable"))):
        resp = await _get(extraction_main.app, "/health")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_extraction_service_health_live_independent_of_dependencies():
    from src.extraction_service import main as extraction_main
    with patch.object(extraction_main, "check_database", AsyncMock(return_value=(False, "down"))):
        health_resp = await _get(extraction_main.app, "/health")
        live_resp = await _get(extraction_main.app, "/health/live")
    assert health_resp.status_code == 503
    assert live_resp.status_code == 200


@pytest.mark.asyncio
async def test_gateway_health_reflects_database_state():
    from src.gateway import main as gateway_main
    with patch.object(gateway_main, "check_database", AsyncMock(return_value=(True, "reachable"))):
        resp = await _get(gateway_main.app, "/health")
    assert resp.status_code == 200

    with patch.object(gateway_main, "check_database", AsyncMock(return_value=(False, "down"))):
        resp = await _get(gateway_main.app, "/health")
    assert resp.status_code == 503


@pytest.mark.asyncio
async def test_document_service_health_checks_database_and_minio():
    from src.document_service import main as document_main
    with patch.object(document_main, "check_database", AsyncMock(return_value=(True, "reachable"))), \
         patch.object(document_main, "check_minio", AsyncMock(return_value=(True, "reachable"))):
        resp = await _get(document_main.app, "/health")
    assert resp.status_code == 200
    body = resp.json()
    assert "minio" in body["dependencies"]

    with patch.object(document_main, "check_database", AsyncMock(return_value=(True, "reachable"))), \
         patch.object(document_main, "check_minio", AsyncMock(return_value=(False, "unreachable"))):
        resp = await _get(document_main.app, "/health")
    assert resp.status_code == 503


@pytest.mark.asyncio
async def test_training_service_health_checks_database_and_celery_broker():
    from src.training_service import main as training_main
    with patch.object(training_main, "check_database", AsyncMock(return_value=(True, "reachable"))), \
         patch.object(training_main, "check_redis", AsyncMock(return_value=(True, "reachable"))):
        resp = await _get(training_main.app, "/health")
    assert resp.status_code == 200
    body = resp.json()
    assert "celery_broker" in body["dependencies"]

    with patch.object(training_main, "check_database", AsyncMock(return_value=(True, "reachable"))), \
         patch.object(training_main, "check_redis", AsyncMock(return_value=(False, "unreachable"))):
        resp = await _get(training_main.app, "/health")
    assert resp.status_code == 503
