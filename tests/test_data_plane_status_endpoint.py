"""Verification for `GET /api/v1/data-plane` and `POST /api/v1/data-plane/provision`
(ADR-017, task 10.2, design.md Decision 6).
"""

import os
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from src.gateway.main import app as gateway_app
from src.shared.auth import create_access_token

pytestmark = [pytest.mark.asyncio]

TENANT_STORE_PASSWORD_ENV = "NER_TEST_TENANT_STORE_PASSWORD"
os.environ.setdefault(TENANT_STORE_PASSWORD_ENV, os.environ.get("NER_TENANT_STORE_DB_PASSWORD", "ner_tenant_store"))


def _bearer(tenant_id: str, role: str = "tenant_admin") -> dict:
    token = create_access_token(tenant_id=tenant_id, user_id="dp-status-test-user", role=role)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def ready_platform_tenant(engine, setup_database):
    tid = f"dp-status-ready-{uuid.uuid4().hex[:8]}"
    async with engine.begin() as conn:
        await conn.execute(
            text("INSERT INTO public.tenants (id, name, slug) VALUES (:id, :n, :s)"),
            {"id": tid, "n": "DP Status Ready Fixture", "s": f"slug-{tid}"},
        )
    yield tid
    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM public.tenants WHERE id = :id"), {"id": tid})


@pytest.fixture
async def failed_tenant(engine, setup_database):
    """A `tenant_owned` tenant whose provisioning attempt failed, with a real
    connection row so a retry has something to enqueue."""
    from src.shared.data_sources.providers import PROVIDER_AZURE_POSTGRESQL_DATA_PLANE

    tid = f"dp-status-failed-{uuid.uuid4().hex[:8]}"
    connection_id = str(uuid.uuid4())
    async with engine.begin() as conn:
        await conn.execute(
            text("INSERT INTO public.tenants (id, name, slug) VALUES (:id, :n, :s)"),
            {"id": tid, "n": "DP Status Failed Fixture", "s": f"slug-{tid}"},
        )
        await conn.execute(
            text(
                "INSERT INTO public.tenant_data_source_connections "
                "(id, tenant_id, provider, configuration, secret_references, status) "
                "VALUES (:id, :tid, :provider, CAST(:config AS JSONB), CAST(:secrets AS JSONB), 'active')"
            ),
            {
                "id": connection_id,
                "tid": tid,
                "provider": PROVIDER_AZURE_POSTGRESQL_DATA_PLANE,
                "config": __import__("json").dumps(
                    {"host": "localhost", "port": 55433, "database": "d", "username": "u", "sslmode": "verify-full"}
                ),
                "secrets": __import__("json").dumps({"password_ref": f"env://{TENANT_STORE_PASSWORD_ENV}"}),
            },
        )
        await conn.execute(
            text(
                "INSERT INTO public.tenant_data_planes "
                "(tenant_id, mode, status, connection_id, status_reason) "
                "VALUES (:tid, 'tenant_owned', 'provisioning_failed', :cid, 'store_unreachable')"
            ),
            {"tid": tid, "cid": connection_id},
        )
    yield tid
    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM public.tenants WHERE id = :id"), {"id": tid})


async def test_get_data_plane_reports_platform_default(ready_platform_tenant):
    """Scenario: a tenant with no `tenant_data_planes` row reads back the platform
    default rather than a missing-record error."""
    transport = ASGITransport(app=gateway_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/api/v1/data-plane", headers=_bearer(ready_platform_tenant)
        )
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "platform"
    assert body["status"] == "ready"


async def test_provision_retry_rejected_outside_provisioning_failed(ready_platform_tenant):
    """Scenario: retry on a `platform`/`ready` tenant is a no-op, rejected."""
    transport = ASGITransport(app=gateway_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/data-plane/provision",
            headers={**_bearer(ready_platform_tenant), "Idempotency-Key": str(uuid.uuid4())},
        )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INVALID_LIFECYCLE_TRANSITION"


async def test_provision_retry_moves_to_provisioning_and_enqueues(engine, failed_tenant, monkeypatch):
    """Scenario: retry from `provisioning_failed` CAS's to `provisioning` and
    enqueues the same task the initial activation uses."""
    enqueued = []

    def _fake_send_task(name, args=None, queue=None):
        enqueued.append((name, args, queue))

    from src.document_service.blob_sync.tasks import celery_app as _document_celery_app

    monkeypatch.setattr(_document_celery_app, "send_task", _fake_send_task)

    transport = ASGITransport(app=gateway_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/data-plane/provision",
            headers={**_bearer(failed_tenant), "Idempotency-Key": str(uuid.uuid4())},
        )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "provisioning"
    assert enqueued == [("provision_tenant_data_plane", [failed_tenant], "data_plane")]

    async with engine.begin() as conn:
        row = (
            await conn.execute(
                text("SELECT status FROM public.tenant_data_planes WHERE tenant_id = :tid"),
                {"tid": failed_tenant},
            )
        ).fetchone()
    assert row.status == "provisioning"
