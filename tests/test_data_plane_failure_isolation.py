"""Verification for "An unreachable tenant store fails closed for that tenant
only" (ADR-017, task 11.5, tenant-data-plane-failure-isolation spec) —
scenarios #23-#26.
"""

import json
import os
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from src.chat_api.main import app as chat_app
from src.document_service.main import app as document_app
from src.shared.auth import create_access_token

pytestmark = [pytest.mark.asyncio]

_PASSWORD_ENV = "NER_ISOLATION_TEST_PASSWORD"
os.environ.setdefault(_PASSWORD_ENV, "unreachable-store-placeholder")


def _bearer(tenant_id: str, role: str = "business_user") -> dict:
    token = create_access_token(tenant_id=tenant_id, user_id="isolation-test-user", role=role)
    return {"Authorization": f"Bearer {token}"}


async def _make_unreachable_ready_tenant(engine, *, tid: str) -> None:
    from src.shared.data_sources.providers import PROVIDER_AZURE_POSTGRESQL_DATA_PLANE

    connection_id = str(uuid.uuid4())
    configuration = {
        "host": "127.0.0.1", "port": 1, "database": "nope", "username": "nope", "sslmode": "disable",
    }
    async with engine.begin() as conn:
        await conn.execute(
            text("INSERT INTO public.tenants (id, name, slug) VALUES (:id, :n, :s)"),
            {"id": tid, "n": "Isolation Fixture", "s": f"slug-{tid}"},
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


@pytest.fixture
async def unreachable_ready_tenant(engine, setup_database):
    tid = f"isolation-{uuid.uuid4().hex[:8]}"
    await _make_unreachable_ready_tenant(engine, tid=tid)
    yield tid
    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM public.tenants WHERE id = :id"), {"id": tid})


@pytest.fixture
async def platform_tenant(engine, tenant_schema):
    """`tenant_schema` (conftest.py) builds the full `test-tenant` content tables,
    but from a `_TENANT_TABLES_SQL` shape that predates `content_type` — a later
    migration's column, and a pre-existing gap unrelated to this change (the same
    root cause as the `uploaded_by`/`ocr_applied_flag` baseline failures elsewhere
    in this suite). Patched on here directly rather than widening the shared
    fixture, which other tests may depend on staying exactly as it is."""
    tid, schema_name = tenant_schema
    async with engine.begin() as conn:
        for column_ddl in (
            "content_type TEXT",
            "file_size BIGINT",
            "status TEXT DEFAULT 'processed'",
            "error_message TEXT",
            "purpose TEXT DEFAULT 'query'",
            "uploaded_by TEXT",
            "ingested_by_kind TEXT DEFAULT 'human'",
            "updated_at TIMESTAMPTZ DEFAULT NOW()",
        ):
            await conn.execute(
                text(f"ALTER TABLE {schema_name}.documents ADD COLUMN IF NOT EXISTS {column_ddl}")
            )
    yield tid


async def test_scenario_23_chat_fails_closed_during_a_store_outage(engine, unreachable_ready_tenant):
    """Scenario #23: Chat fails closed during a store outage."""
    transport = ASGITransport(app=chat_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/chat",
            headers=_bearer(unreachable_ready_tenant),
            json={"message": "hello"},
        )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "TENANT_DATA_PLANE_UNAVAILABLE"

    # No conversation or message row is written anywhere reachable — the tenant's
    # own store is unreachable by construction, so the only place a row could
    # have landed instead is the platform database, which must hold none either.
    async with engine.begin() as conn:
        exists = (
            await conn.execute(
                text(
                    "SELECT 1 FROM information_schema.schemata WHERE schema_name = :s"
                ),
                {"s": f"tenant_{unreachable_ready_tenant.replace('-', '_')}"},
            )
        ).fetchone()
    assert exists is None


async def test_scenario_24_other_tenants_are_unaffected(engine, unreachable_ready_tenant, platform_tenant):
    """Scenario #24: Other tenants are unaffected."""
    transport = ASGITransport(app=document_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        residency_response, platform_response = [
            await client.get("/api/v1/documents", headers=_bearer(tid))
            for tid in (unreachable_ready_tenant, platform_tenant)
        ]

    assert platform_response.status_code == 200
    assert residency_response.status_code == 503
    assert residency_response.json()["error"]["code"] == "TENANT_DATA_PLANE_UNAVAILABLE"


async def test_scenario_25_driver_error_text_is_not_exposed(unreachable_ready_tenant):
    """Scenario #25: Driver error text is not exposed."""
    transport = ASGITransport(app=chat_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/chat",
            headers=_bearer(unreachable_ready_tenant),
            json={"message": "hello"},
        )

    body_text = response.text
    assert "127.0.0.1" not in body_text
    assert "psycopg2" not in body_text.lower()
    assert "asyncpg" not in body_text.lower()
    assert "password" not in body_text.lower()


async def test_scenario_26_upload_during_outage_writes_nothing(engine, unreachable_ready_tenant):
    """Scenario #26: Upload during outage writes nothing (see also
    `test_upload_precheck.py`, which this duplicates for the isolation spec's own
    numbering)."""
    transport = ASGITransport(app=document_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/documents",
            headers=_bearer(unreachable_ready_tenant),
            files={"file": ("test.pdf", b"%PDF-1.4 fake", "application/pdf")},
            data={"purpose": "query"},
        )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "TENANT_DATA_PLANE_UNAVAILABLE"

    async with engine.begin() as conn:
        registry_rows = (
            await conn.execute(
                text("SELECT 1 FROM public.tenant_document_registry WHERE tenant_id = :tid"),
                {"tid": unreachable_ready_tenant},
            )
        ).fetchall()
    assert registry_rows == []
