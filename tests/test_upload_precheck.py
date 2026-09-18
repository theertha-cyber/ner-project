"""Verification for "Uploads are rejected before bytes are accepted when the
store is unavailable" (ADR-017, task 11.1, tenant-data-plane-failure-isolation
spec).
"""

import json
import os
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from src.document_service.main import app as document_app
from src.shared.auth import create_access_token

pytestmark = [pytest.mark.asyncio]

_PASSWORD_ENV = "NER_PRECHECK_TEST_PASSWORD"
os.environ.setdefault(_PASSWORD_ENV, "unreachable-store-placeholder")


def _bearer(tenant_id: str, role: str = "business_user") -> dict:
    token = create_access_token(tenant_id=tenant_id, user_id="precheck-test-user", role=role)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def unreachable_ready_tenant(engine, setup_database):
    """A `ready` `tenant_owned` tenant whose store is actually unreachable —
    `require_data_plane_ready` (status-only) lets this through; the upload precheck
    is what must catch it."""
    from src.shared.data_sources.providers import PROVIDER_AZURE_POSTGRESQL_DATA_PLANE

    tid = f"precheck-{uuid.uuid4().hex[:8]}"
    connection_id = str(uuid.uuid4())
    configuration = {
        "host": "127.0.0.1", "port": 1, "database": "nope", "username": "nope", "sslmode": "disable",
    }
    async with engine.begin() as conn:
        await conn.execute(
            text("INSERT INTO public.tenants (id, name, slug) VALUES (:id, :n, :s)"),
            {"id": tid, "n": "Precheck Fixture", "s": f"slug-{tid}"},
        )
        await conn.execute(
            text(
                "INSERT INTO public.tenant_data_source_connections "
                "(id, tenant_id, provider, configuration, secret_references, status) "
                "VALUES (:id, :tid, :provider, CAST(:config AS JSONB), CAST(:secrets AS JSONB), 'active')"
            ),
            {
                "id": connection_id, "tid": tid, "provider": PROVIDER_AZURE_POSTGRESQL_DATA_PLANE,
                "config": json.dumps(configuration),
                "secrets": json.dumps({"password_ref": f"env://{_PASSWORD_ENV}"}),
            },
        )
        await conn.execute(
            text(
                "INSERT INTO public.tenant_data_planes "
                "(tenant_id, mode, status, connection_id) "
                "VALUES (:tid, 'tenant_owned', 'ready', :cid)"
            ),
            {"tid": tid, "cid": connection_id},
        )
    yield tid
    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM public.tenants WHERE id = :id"), {"id": tid})


async def test_upload_during_outage_writes_nothing(engine, unreachable_ready_tenant):
    """Scenario: Upload during outage writes nothing."""
    transport = ASGITransport(app=document_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/documents",
            headers=_bearer(unreachable_ready_tenant),
            files={"file": ("test.pdf", b"%PDF-1.4 fake", "application/pdf")},
            data={"purpose": "query"},
        )

    assert response.status_code == 503
    body = response.json()
    assert body["error"]["code"] == "TENANT_DATA_PLANE_UNAVAILABLE"
    assert "reason_class" in body["error"]
    # No driver text, host, or port ever reaches the response.
    assert "127.0.0.1" not in response.text

    async with engine.begin() as conn:
        registry_rows = (
            await conn.execute(
                text("SELECT 1 FROM public.tenant_document_registry WHERE tenant_id = :tid"),
                {"tid": unreachable_ready_tenant},
            )
        ).fetchall()
        health_row = (
            await conn.execute(
                text("SELECT health_outcome FROM public.tenant_data_planes WHERE tenant_id = :tid"),
                {"tid": unreachable_ready_tenant},
            )
        ).fetchone()
    assert registry_rows == []
    assert health_row.health_outcome == "unreachable"
