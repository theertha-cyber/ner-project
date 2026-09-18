"""Verification for the `require_data_plane_ready` circuit breaker (ADR-017,
task 11.3, tenant-data-plane-failure-isolation spec) — a `tenant_owned` tenant
already recorded unhealthy is refused without spending a real connection
attempt on the request.
"""

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from src.document_service.main import app as document_app
from src.shared.auth import create_access_token

pytestmark = [pytest.mark.asyncio]


def _bearer(tenant_id: str, role: str = "business_user") -> dict:
    token = create_access_token(tenant_id=tenant_id, user_id="breaker-test-user", role=role)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def ready_but_recorded_unreachable(engine, setup_database):
    """A `ready` `tenant_owned` tenant whose *recorded* health is `unreachable`
    (as a prior probe or resolver failure would leave it) but whose connection
    now points nowhere resolvable at all — proving the breaker fires from the
    cached record alone, not from a fresh (slow) connection attempt."""
    from src.shared.data_sources.providers import PROVIDER_AZURE_POSTGRESQL_DATA_PLANE

    tid = f"breaker-{uuid.uuid4().hex[:8]}"
    connection_id = str(uuid.uuid4())
    async with engine.begin() as conn:
        await conn.execute(
            text("INSERT INTO public.tenants (id, name, slug) VALUES (:id, :n, :s)"),
            {"id": tid, "n": "Breaker Fixture", "s": f"slug-{tid}"},
        )
        await conn.execute(
            text(
                "INSERT INTO public.tenant_data_source_connections "
                "(id, tenant_id, provider, configuration, secret_references, status) "
                "VALUES (:id, :tid, :provider, CAST(:config AS JSONB), CAST(:secrets AS JSONB), 'active')"
            ),
            {
                "id": connection_id, "tid": tid, "provider": PROVIDER_AZURE_POSTGRESQL_DATA_PLANE,
                "config": __import__("json").dumps(
                    {"host": "10.255.255.1", "port": 5432, "database": "d", "username": "u", "sslmode": "disable"}
                ),
                "secrets": __import__("json").dumps({"password_ref": "env://NER_BREAKER_TEST_PASSWORD"}),
            },
        )
        await conn.execute(
            text(
                "INSERT INTO public.tenant_data_planes "
                "(tenant_id, mode, status, connection_id, health_outcome, health_checked_at) "
                "VALUES (:tid, 'tenant_owned', 'ready', :cid, 'unreachable', NOW())"
            ),
            {"tid": tid, "cid": connection_id},
        )
    yield tid
    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM public.tenants WHERE id = :id"), {"id": tid})


async def test_circuit_breaker_refuses_a_recorded_unhealthy_tenant(ready_but_recorded_unreachable):
    """A `ready`-status tenant already recorded `unreachable` gets 503 straight
    from the readiness gate, not from a resolver connection attempt."""
    transport = ASGITransport(app=document_app)
    async with AsyncClient(transport=transport, base_url="http://test", timeout=5.0) as client:
        response = await client.get(
            "/api/v1/documents", headers=_bearer(ready_but_recorded_unreachable)
        )

    assert response.status_code == 503
    body = response.json()
    assert body["error"]["code"] == "TENANT_DATA_PLANE_UNAVAILABLE"
    assert body["error"]["reason_class"] == "unreachable"


async def test_circuit_breaker_does_not_apply_to_platform_tenants(engine, setup_database):
    """A `platform` tenant's row never carries a health outcome in practice
    (only `tenant_owned` rows are probed/recorded — `record_health`'s `WHERE
    mode = 'tenant_owned'` guard) — the breaker's own `is_platform` check must
    still refuse to fire for one even if a row somehow carried a value."""
    from fastapi import Request

    from src.shared.data_plane_gate import require_data_plane_ready

    tid = f"breaker-platform-{uuid.uuid4().hex[:8]}"
    async with engine.begin() as conn:
        await conn.execute(
            text("INSERT INTO public.tenants (id, name, slug) VALUES (:id, :n, :s)"),
            {"id": tid, "n": "Breaker Platform Fixture", "s": f"slug-{tid}"},
        )
        await conn.execute(
            text(
                "INSERT INTO public.tenant_data_planes "
                "(tenant_id, mode, status, health_outcome, health_checked_at) "
                "VALUES (:tid, 'platform', 'ready', 'unreachable', NOW())"
            ),
            {"tid": tid},
        )

    scope = {"type": "http", "headers": [], "method": "GET", "path": "/"}
    request = Request(scope)
    request.state.tenant_id = tid

    await require_data_plane_ready(request)  # must not raise

    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM public.tenants WHERE id = :id"), {"id": tid})
