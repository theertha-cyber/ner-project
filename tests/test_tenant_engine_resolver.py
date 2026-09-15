"""Verification for `EngineResolver` (ADR-017, Design D4) — routing spec scenarios
#4, #5, #6, #8.

The residency-tenant scenarios (#5, #6) connect for real to `postgres-tenant-store`,
the local Compose stand-in for a tenant-owned Azure Flexible Server (docker-compose.yml,
port 55433). That container has no TLS configured, so these tests register their
connection row directly (bypassing the `providers.py` validation that fixes real
`azure_postgresql_data_plane` drafts at `sslmode=verify-full`) with `sslmode=disable` —
exercising the resolver's actual routing and no-fallback behaviour against a live
second server, which is the whole point of Design D11's local stand-in, without
requiring a CA-signed certificate on a laptop.
"""

import os
import uuid

import pytest
from sqlalchemy import text

from src.shared import data_plane
from src.shared.data_plane import DataPlaneNotReady, DataPlaneUnavailable
from src.shared.database import EngineResolver

pytestmark = [pytest.mark.asyncio]

TENANT_STORE_HOST = "localhost"
TENANT_STORE_PORT = int(os.environ.get("NER_TEST_TENANT_STORE_PORT", "55433"))
TENANT_STORE_DB = os.environ.get("NER_TENANT_STORE_DB_NAME", "ner_tenant_store")
TENANT_STORE_USER = os.environ.get("NER_TENANT_STORE_DB_USER", "ner_tenant_store")
TENANT_STORE_PASSWORD_ENV = "NER_TEST_TENANT_STORE_PASSWORD"

os.environ.setdefault(TENANT_STORE_PASSWORD_ENV, os.environ.get("NER_TENANT_STORE_DB_PASSWORD", "ner_tenant_store"))


@pytest.fixture(autouse=True)
def fresh_resolver_and_cache():
    """Each test gets its own resolver instance and a cleared data-plane cache, so
    cache TTL / staleness from one test can never leak into the next."""
    data_plane._cache.clear()
    yield EngineResolver()
    data_plane._cache.clear()


@pytest.fixture
async def residency_tenant(engine, setup_database):
    """A `tenant_owned`, `ready` tenant with an active data-plane connection pointing
    at `postgres-tenant-store`."""
    tid = f"resolver-{uuid.uuid4().hex[:8]}"
    connection_id = str(uuid.uuid4())
    async with engine.begin() as conn:
        await conn.execute(
            text("INSERT INTO public.tenants (id, name, slug) VALUES (:id, :n, :s)"),
            {"id": tid, "n": "Resolver Fixture", "s": f"slug-{tid}"},
        )
        await conn.execute(
            text(
                "INSERT INTO public.tenant_data_source_connections "
                "(id, tenant_id, provider, configuration, secret_references, status) "
                "VALUES (:id, :tid, 'azure_postgresql_data_plane', "
                "CAST(:config AS JSONB), CAST(:secrets AS JSONB), 'active')"
            ),
            {
                "id": connection_id,
                "tid": tid,
                "config": (
                    '{"host": "%s", "port": %d, "database": "%s", '
                    '"username": "%s", "sslmode": "disable"}'
                )
                % (TENANT_STORE_HOST, TENANT_STORE_PORT, TENANT_STORE_DB, TENANT_STORE_USER),
                "secrets": '{"password_ref": "env://%s"}' % TENANT_STORE_PASSWORD_ENV,
            },
        )
        await conn.execute(
            text(
                "INSERT INTO public.tenant_data_planes "
                "(tenant_id, mode, status, connection_id) "
                "VALUES (:tid, 'tenant_owned', 'ready', CAST(:cid AS UUID))"
            ),
            {"cid": connection_id, "tid": tid},
        )
    yield tid, connection_id
    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM public.tenants WHERE id = :id"), {"id": tid})
        await conn.execute(
            text("DELETE FROM public.tenant_data_source_connections WHERE id = CAST(:id AS UUID)"),
            {"id": connection_id},
        )


async def test_platform_tenant_resolves_to_platform_engine(fresh_resolver_and_cache, engine, setup_database):
    """Scenario: Platform tenant resolves to the platform engine."""
    resolver = fresh_resolver_and_cache
    resolved = await resolver.resolve("test-tenant")
    assert resolved is resolver._platform_engine()


async def test_residency_tenant_resolves_to_its_own_store(fresh_resolver_and_cache, residency_tenant):
    """Scenario: Residency tenant resolves to its own store."""
    tid, _ = residency_tenant
    resolver = fresh_resolver_and_cache
    resolved = await resolver.resolve(tid)
    assert resolved is not resolver._platform_engine()

    async with resolved.connect() as conn:
        result = await conn.execute(text("SELECT current_database()"))
        assert result.scalar_one() == TENANT_STORE_DB


async def test_residency_tenant_never_falls_back_to_platform(fresh_resolver_and_cache, engine, setup_database):
    """Scenario: Residency tenant never falls back to the platform engine.

    A tenant_owned tenant whose connection is paused: the resolver raises rather than
    silently returning the platform engine.
    """
    tid = f"resolver-paused-{uuid.uuid4().hex[:8]}"
    async with engine.begin() as conn:
        await conn.execute(
            text("INSERT INTO public.tenants (id, name, slug) VALUES (:id, :n, :s)"),
            {"id": tid, "n": "Paused Fixture", "s": f"slug-{tid}"},
        )
        await conn.execute(
            text(
                "INSERT INTO public.tenant_data_planes (tenant_id, mode, status) "
                "VALUES (:tid, 'tenant_owned', 'paused')"
            ),
            {"tid": tid},
        )
    try:
        resolver = fresh_resolver_and_cache
        with pytest.raises(DataPlaneNotReady) as excinfo:
            await resolver.resolve(tid)
        assert excinfo.value.status_class == "paused"
    finally:
        async with engine.begin() as conn:
            await conn.execute(text("DELETE FROM public.tenants WHERE id = :id"), {"id": tid})


async def test_missing_connection_raises_unavailable_not_platform_fallback(
    fresh_resolver_and_cache, engine, setup_database
):
    tid = f"resolver-nofallback-{uuid.uuid4().hex[:8]}"
    async with engine.begin() as conn:
        await conn.execute(
            text("INSERT INTO public.tenants (id, name, slug) VALUES (:id, :n, :s)"),
            {"id": tid, "n": "No Connection Fixture", "s": f"slug-{tid}"},
        )
        await conn.execute(
            text(
                "INSERT INTO public.tenant_data_planes (tenant_id, mode, status) "
                "VALUES (:tid, 'tenant_owned', 'ready')"
            ),
            {"tid": tid},
        )
    try:
        resolver = fresh_resolver_and_cache
        with pytest.raises(DataPlaneUnavailable) as excinfo:
            await resolver.resolve(tid)
        assert excinfo.value.reason_class == "connection_missing"
    finally:
        async with engine.begin() as conn:
            await conn.execute(text("DELETE FROM public.tenants WHERE id = :id"), {"id": tid})


async def test_engine_cache_invalidated_on_connection_change(fresh_resolver_and_cache, residency_tenant, engine):
    """Scenario: Engine cache is invalidated on connection change.

    Bumping the connection's `updated_at` (what a pause/replace/retire does) changes
    the cache key, so the next resolution builds (and returns) a different engine
    object rather than reusing the stale one.
    """
    tid, connection_id = residency_tenant
    resolver = fresh_resolver_and_cache
    data_plane.invalidate(tid)
    first = await resolver.resolve(tid)

    async with engine.begin() as conn:
        await conn.execute(
            text(
                "UPDATE public.tenant_data_source_connections "
                "SET updated_at = NOW() WHERE id = CAST(:id AS UUID)"
            ),
            {"id": connection_id},
        )
    data_plane.invalidate(tid)

    second = await resolver.resolve(tid)
    assert first is not second
    await first.dispose()
    await second.dispose()
