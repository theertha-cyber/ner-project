import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.shared.readiness import (
    check_database,
    check_minio,
    check_redis,
    check_http_dependency,
    build_readiness_body,
)


@pytest.mark.asyncio
async def test_check_database_healthy():
    conn = AsyncMock()
    conn.execute = AsyncMock()
    cm = AsyncMock()
    cm.__aenter__.return_value = conn
    cm.__aexit__.return_value = False
    engine = MagicMock()
    engine.connect.return_value = cm

    ok, detail = await check_database(engine)

    assert ok is True
    assert detail == "reachable"


@pytest.mark.asyncio
async def test_check_database_unhealthy_on_exception():
    engine = MagicMock()
    engine.connect.side_effect = ConnectionError("connection refused")

    ok, detail = await check_database(engine)

    assert ok is False
    assert "connection refused" in detail


@pytest.mark.asyncio
async def test_check_minio_healthy():
    mock_client = MagicMock()
    mock_client.head_bucket.return_value = {}
    with patch("boto3.client", return_value=mock_client):
        ok, detail = await check_minio("minio:9000", "key", "secret", "bucket")
    assert ok is True


@pytest.mark.asyncio
async def test_check_minio_unhealthy_on_client_error():
    from botocore.exceptions import ClientError

    mock_client = MagicMock()
    mock_client.head_bucket.side_effect = ClientError(
        {"Error": {"Code": "500", "Message": "Down"}}, "HeadBucket"
    )
    with patch("boto3.client", return_value=mock_client):
        ok, detail = await check_minio("minio:9000", "key", "secret", "bucket")
    assert ok is False


@pytest.mark.asyncio
async def test_check_redis_healthy():
    mock_client = AsyncMock()
    mock_client.ping = AsyncMock(return_value=True)
    mock_client.aclose = AsyncMock()
    with patch("redis.asyncio.from_url", return_value=mock_client):
        ok, detail = await check_redis("redis://localhost:6379/0")
    assert ok is True


@pytest.mark.asyncio
async def test_check_redis_unhealthy_on_exception():
    mock_client = AsyncMock()
    mock_client.ping = AsyncMock(side_effect=ConnectionError("refused"))
    mock_client.aclose = AsyncMock()
    with patch("redis.asyncio.from_url", return_value=mock_client):
        ok, detail = await check_redis("redis://localhost:6379/0")
    assert ok is False


@pytest.mark.asyncio
async def test_check_http_dependency_healthy():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_async_client = AsyncMock()
    mock_async_client.get = AsyncMock(return_value=mock_response)
    mock_async_client.__aenter__.return_value = mock_async_client
    mock_async_client.__aexit__.return_value = False
    with patch("httpx.AsyncClient", return_value=mock_async_client):
        ok, detail = await check_http_dependency("http://model_serving:8000")
    assert ok is True


@pytest.mark.asyncio
async def test_check_http_dependency_unhealthy_on_5xx():
    mock_response = MagicMock()
    mock_response.status_code = 503
    mock_async_client = AsyncMock()
    mock_async_client.get = AsyncMock(return_value=mock_response)
    mock_async_client.__aenter__.return_value = mock_async_client
    mock_async_client.__aexit__.return_value = False
    with patch("httpx.AsyncClient", return_value=mock_async_client):
        ok, detail = await check_http_dependency("http://model_serving:8000")
    assert ok is False


def test_build_readiness_body_all_healthy_returns_200():
    status_code, body = build_readiness_body({"database": (True, "reachable")})
    assert status_code == 200
    assert body["status"] == "ok"
    assert body["dependencies"]["database"]["status"] == "healthy"


def test_build_readiness_body_one_unhealthy_returns_503_with_full_breakdown():
    status_code, body = build_readiness_body(
        {"database": (False, "connection refused"), "minio": (True, "reachable")}
    )
    assert status_code == 503
    assert body["status"] == "unavailable"
    assert body["dependencies"]["database"]["status"] == "unhealthy"
    assert body["dependencies"]["minio"]["status"] == "healthy"
