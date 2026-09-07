"""A record emitted during a request carries that request's context, opaquely.

Verification rows 4, 15 and 17.

The three assertions are one property seen from three sides: telemetry has to say *which*
request, tenant and user, and must not say *who*. Tenant appears as the UUID that ADR-001
already uses as the schema discriminator — never the slug that appears in the URL. User
appears as a keyed hash. Neither the raw user id nor an email may occur anywhere in a
record.
"""

import io
import json
import logging

import httpx
import pytest
from fastapi import FastAPI
from starlette.middleware.base import BaseHTTPMiddleware

from src.shared.observability import (
    ObservabilityMiddleware,
    hash_user_id,
    set_tenant_id,
    set_user_hash,
)
from src.shared.observability.logging_config import build_handler

pytestmark = [pytest.mark.verification]

TENANT_UUID = "3f2a91c4-77bd-4f1e-9c2a-0e5b8d6a1f30"
TENANT_SLUG = "acme-recruiting"
USER_ID = "8f14e45f-ea1c-4b0a-9d3e-2b7c6a1f0d55"
USER_EMAIL = "priya.raman@example.com"


class _StubTenantMiddleware(BaseHTTPMiddleware):
    """Stands in for each service's real `TenantContextMiddleware`.

    Only the part this change touches is reproduced: binding the resolved identity into
    the ambient context. Token decoding and the tenant lookup stay in the per-service
    middleware and are exercised by the tenant-isolation suite, not here.
    """

    async def dispatch(self, request, call_next):
        set_tenant_id(TENANT_UUID)
        set_user_hash(hash_user_id(USER_ID))
        return await call_next(request)


@pytest.fixture
def app_and_log():
    buffer = io.StringIO()
    handler = build_handler("gateway", stream=buffer)
    logger = logging.getLogger("tests.observability.context")
    logger.handlers = [handler]
    logger.setLevel(logging.INFO)
    logger.propagate = False

    app = FastAPI()

    @app.get("/work")
    async def work():
        logger.info("work_done", extra={"rows": 2})
        return {"ok": True}

    # Tenant middleware inside, correlation middleware outside — the order every
    # service's `main.py` produces, since `init_observability` is called last.
    app.add_middleware(_StubTenantMiddleware)
    app.add_middleware(ObservabilityMiddleware)

    yield app, buffer
    logger.handlers = []


async def _get(app, path="/work", headers=None):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.get(path, headers=headers or {})


def _records(buffer):
    return [json.loads(line) for line in buffer.getvalue().splitlines() if line.strip()]


class TestContextMatchesTheRequest:
    """Row 4 — the four fields match the values resolved for that request."""

    async def test_request_id_matches_the_response_header(self, app_and_log):
        app, buffer = app_and_log
        response = await _get(app, headers={"X-Request-ID": "abc-123"})

        record = _records(buffer)[0]
        assert response.headers["X-Request-ID"] == "abc-123"
        assert record["request_id"] == "abc-123"

    async def test_tenant_and_user_are_bound(self, app_and_log):
        app, buffer = app_and_log
        await _get(app)

        record = _records(buffer)[0]
        assert record["tenant_id"] == TENANT_UUID
        assert record["user_hash"] == hash_user_id(USER_ID)

    async def test_all_four_keys_are_present(self, app_and_log):
        app, buffer = app_and_log
        await _get(app)

        record = _records(buffer)[0]
        for field in ("request_id", "tenant_id", "user_hash", "trace_id"):
            assert field in record

    async def test_two_requests_do_not_share_a_request_id(self, app_and_log):
        """A leaked contextvar would silently merge two users' work under one identifier."""
        app, buffer = app_and_log
        await _get(app, headers={"X-Request-ID": "first"})
        await _get(app, headers={"X-Request-ID": "second"})

        assert [record["request_id"] for record in _records(buffer)] == ["first", "second"]


class TestIdentityIsOpaque:
    """Rows 15 and 17 — a hash for the user, a UUID for the tenant, nothing else."""

    async def test_user_hash_is_present(self, app_and_log):
        app, buffer = app_and_log
        await _get(app)

        assert _records(buffer)[0]["user_hash"]

    async def test_no_raw_user_id_or_email_appears_anywhere(self, app_and_log):
        app, buffer = app_and_log
        await _get(app)

        emitted = buffer.getvalue()
        assert USER_ID not in emitted
        assert USER_EMAIL not in emitted
        assert "@" not in emitted, "an email address in a log record defeats the hash entirely"

    async def test_tenant_appears_as_a_uuid_and_not_a_slug(self, app_and_log):
        app, buffer = app_and_log
        await _get(app)

        emitted = buffer.getvalue()
        assert TENANT_UUID in emitted
        assert TENANT_SLUG not in emitted
