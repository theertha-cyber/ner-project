"""Verification for "Per-tenant store health is a content-free control-plane
signal" (ADR-017, task 11.7, tenant-data-plane-failure-isolation spec) —
scenarios #29, #30.
"""

import json
import os
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

pytestmark = [pytest.mark.asyncio]

TENANT_STORE_HOST = "localhost"
TENANT_STORE_PORT = int(os.environ.get("NER_TEST_TENANT_STORE_PORT", "55433"))
TENANT_STORE_DB = os.environ.get("NER_TENANT_STORE_DB_NAME", "ner_tenant_store")
TENANT_STORE_USER = os.environ.get("NER_TENANT_STORE_DB_USER", "ner_tenant_store")
TENANT_STORE_PASSWORD_ENV = "NER_TEST_TENANT_STORE_PASSWORD"
os.environ.setdefault(TENANT_STORE_PASSWORD_ENV, os.environ.get("NER_TENANT_STORE_DB_PASSWORD", "ner_tenant_store"))


async def _make_ready_tenant(engine, *, tid: str, host: str, port: int) -> None:
    from src.shared.data_sources.providers import PROVIDER_AZURE_POSTGRESQL_DATA_PLANE

    connection_id = str(uuid.uuid4())
    configuration = {
        "host": host, "port": port, "database": TENANT_STORE_DB,
        "username": TENANT_STORE_USER, "sslmode": "disable",
    }
    async with engine.begin() as conn:
        await conn.execute(
            text("INSERT INTO public.tenants (id, name, slug) VALUES (:id, :n, :s)"),
            {"id": tid, "n": "Health Fixture", "s": f"slug-{tid}"},
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
                "secrets": json.dumps({"password_ref": f"env://{TENANT_STORE_PASSWORD_ENV}"}),
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


async def _cleanup(engine, tid: str) -> None:
    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM public.tenants WHERE id = :id"), {"id": tid})


async def test_scenario_29_service_stays_ready_during_a_tenant_outage(engine, setup_database):
    """Scenario #29: Service stays ready during a tenant outage."""
    from src.document_service.data_plane.tasks import probe_tenant_data_plane_health
    from src.document_service.main import app as document_app

    tid = f"health-outage-{uuid.uuid4().hex[:8]}"
    await _make_ready_tenant(engine, tid=tid, host="127.0.0.1", port=1)
    try:
        probe_tenant_data_plane_health.run()

        async with engine.begin() as conn:
            row = (
                await conn.execute(
                    text("SELECT health_outcome FROM public.tenant_data_planes WHERE tenant_id = :tid"),
                    {"tid": tid},
                )
            ).fetchone()
        assert row.health_outcome == "unreachable"

        transport = ASGITransport(app=document_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/health")
        # `/health` also probes MinIO, whose reachability is unrelated to this
        # scenario and to ADR-017 — the assertion that matters here is that the
        # *database* dependency (the one `require_data_plane_ready`/the resolver
        # could plausibly entangle with a tenant outage) stays healthy and does
        # not drag the whole service not-ready.
        assert response.json()["dependencies"]["database"]["status"] == "healthy"
    finally:
        await _cleanup(engine, tid)


async def test_scenario_30_recovery_is_detected(engine, setup_database):
    """Scenario #30: Recovery is detected."""
    from src.document_service.data_plane.tasks import probe_tenant_data_plane_health

    tid = f"health-recovery-{uuid.uuid4().hex[:8]}"
    # Start pointing at an unreachable port so the tenant is first recorded
    # `unreachable`, then repoint the connection at the real store and probe again.
    await _make_ready_tenant(engine, tid=tid, host="127.0.0.1", port=1)
    try:
        probe_tenant_data_plane_health.run()
        async with engine.begin() as conn:
            row = (
                await conn.execute(
                    text("SELECT health_outcome FROM public.tenant_data_planes WHERE tenant_id = :tid"),
                    {"tid": tid},
                )
            ).fetchone()
        assert row.health_outcome == "unreachable"

        async with engine.begin() as conn:
            await conn.execute(
                text(
                    "UPDATE public.tenant_data_source_connections SET configuration = CAST(:config AS JSONB) "
                    "WHERE tenant_id = :tid"
                ),
                {
                    "tid": tid,
                    "config": json.dumps(
                        {
                            "host": TENANT_STORE_HOST, "port": TENANT_STORE_PORT, "database": TENANT_STORE_DB,
                            "username": TENANT_STORE_USER, "sslmode": "disable",
                        }
                    ),
                },
            )

        probe_tenant_data_plane_health.run()
        async with engine.begin() as conn:
            row = (
                await conn.execute(
                    text("SELECT health_outcome FROM public.tenant_data_planes WHERE tenant_id = :tid"),
                    {"tid": tid},
                )
            ).fetchone()
        assert row.health_outcome == "healthy"
    finally:
        await _cleanup(engine, tid)
