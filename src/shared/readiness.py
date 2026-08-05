"""Shared dependency probes used to build per-service /health readiness responses."""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine


async def check_database(engine: AsyncEngine) -> tuple[bool, str]:
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True, "reachable"
    except Exception as exc:
        return False, str(exc)


async def check_minio(endpoint: str, access_key: str, secret_key: str, bucket: str) -> tuple[bool, str]:
    import boto3
    from botocore.exceptions import ClientError

    try:
        client = boto3.client(
            "s3",
            endpoint_url=f"http://{endpoint}",
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            config=boto3.session.Config(signature_version="s3v4", connect_timeout=2, read_timeout=2),
        )
        client.head_bucket(Bucket=bucket)
        return True, "reachable"
    except ClientError as exc:
        return False, str(exc)
    except Exception as exc:
        return False, str(exc)


async def check_redis(redis_url: str) -> tuple[bool, str]:
    import redis.asyncio as aioredis

    client = aioredis.from_url(redis_url, socket_connect_timeout=2, socket_timeout=2)
    try:
        await client.ping()
        return True, "reachable"
    except Exception as exc:
        return False, str(exc)
    finally:
        await client.aclose()


async def check_http_dependency(url: str, path: str = "/health") -> tuple[bool, str]:
    import httpx

    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            response = await client.get(f"{url.rstrip('/')}{path}")
        if response.status_code < 500:
            return True, "reachable"
        return False, f"status={response.status_code}"
    except Exception as exc:
        return False, str(exc)


def build_readiness_body(checks: dict[str, tuple[bool, str]]) -> tuple[int, dict]:
    all_healthy = all(ok for ok, _ in checks.values())
    body = {
        "status": "ok" if all_healthy else "unavailable",
        "dependencies": {
            name: {"status": "healthy" if ok else "unhealthy", "detail": detail}
            for name, (ok, detail) in checks.items()
        },
    }
    return (200 if all_healthy else 503), body
