"""Verification for the content-route readiness gate (ADR-017, Design D9) —
routing spec scenarios #9, #10.
"""

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from src.document_service.main import app as document_app
from src.gateway.main import app as gateway_app
from src.shared.auth import create_access_token

pytestmark = [pytest.mark.asyncio]


@pytest.fixture
async def awaiting_store_tenant(engine, setup_database):
    tid = f"gate-{uuid.uuid4().hex[:8]}"
    async with engine.begin() as conn:
        await conn.execute(
            text("INSERT INTO public.tenants (id, name, slug) VALUES (:id, :n, :s)"),
            {"id": tid, "n": "Gate Fixture", "s": f"slug-{tid}"},
        )
        await conn.execute(
            text(
                "INSERT INTO public.tenant_data_planes (tenant_id, mode, status) "
                "VALUES (:tid, 'tenant_owned', 'awaiting_store')"
            ),
            {"tid": tid},
        )
    yield tid
    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM public.tenants WHERE id = :id"), {"id": tid})


def _bearer(tenant_id: str, role: str = "business_user") -> dict:
    token = create_access_token(tenant_id=tenant_id, user_id="gate-test-user", role=role)
    return {"Authorization": f"Bearer {token}"}


async def test_awaiting_store_tenant_cannot_upload(engine, awaiting_store_tenant):
    """Scenario: Awaiting-store tenant cannot upload."""
    transport = ASGITransport(app=document_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/documents",
            headers=_bearer(awaiting_store_tenant),
            files={"file": ("test.pdf", b"%PDF-1.4 fake", "application/pdf")},
            data={"purpose": "query"},
        )

    assert response.status_code == 409
    body = response.json()
    assert body["error"]["code"] == "TENANT_DATA_PLANE_NOT_READY"
    assert body["error"]["status_class"] == "awaiting_store"

    # No bytes written to any store: no document row for this tenant anywhere.
    async with engine.begin() as conn:
        registry_rows = (
            await conn.execute(
                text("SELECT 1 FROM public.tenant_document_registry WHERE tenant_id = :tid"),
                {"tid": awaiting_store_tenant},
            )
        ).fetchall()
    assert registry_rows == []


async def test_awaiting_store_tenant_administrator_can_configure_the_store(
    engine, awaiting_store_tenant
):
    """Scenario: Awaiting-store tenant administrator can configure the store.

    Data-source settings routes are exempt from the readiness gate — listing
    connections for an `awaiting_store` tenant must not 409.
    """
    transport = ASGITransport(app=gateway_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/api/v1/data-sources",
            headers=_bearer(awaiting_store_tenant, role="tenant_admin"),
        )

    assert response.status_code != 409
