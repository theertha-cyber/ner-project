"""Verification for fleet operations against the control plane (ADR-017) — routing spec
scenarios #11, #12. Exercises `sql_execution_role.provision_role` against a real second
Postgres server (`postgres-tenant-store`, docker-compose.yml) alongside the platform
database — the residency integration the routing spec's "reconciler reaches a residency
tenant" and "one unreachable store does not abort the fleet run" scenarios describe.
"""

import os
import uuid

import pytest
import sqlalchemy
from sqlalchemy import text

from src.chat_api.services.sql_execution_role import provision_role

pytestmark = [pytest.mark.asyncio]

TENANT_STORE_HOST = "localhost"
TENANT_STORE_PORT = int(os.environ.get("NER_TEST_TENANT_STORE_PORT", "55433"))
TENANT_STORE_DB = os.environ.get("NER_TENANT_STORE_DB_NAME", "ner_tenant_store")
TENANT_STORE_USER = os.environ.get("NER_TENANT_STORE_DB_USER", "ner_tenant_store")
TENANT_STORE_PASSWORD_ENV = "NER_TEST_TENANT_STORE_PASSWORD"
os.environ.setdefault(TENANT_STORE_PASSWORD_ENV, os.environ.get("NER_TENANT_STORE_DB_PASSWORD", "ner_tenant_store"))


async def _insert_tenant(conn, tid: str) -> None:
    await conn.execute(
        text("INSERT INTO public.tenants (id, name, slug) VALUES (:id, :n, :s)"),
        {"id": tid, "n": f"Fleet {tid[:8]}", "s": f"fleet-{tid}"},
    )


async def _insert_residency_connection(conn, tid: str, *, host: str, port: int) -> str:
    connection_id = str(uuid.uuid4())
    await conn.execute(
        text(
            "INSERT INTO public.tenant_data_source_connections "
            "(id, tenant_id, provider, configuration, secret_references, status) "
            "VALUES (:id, :tid, 'azure_postgresql_data_plane', CAST(:config AS JSONB), "
            "CAST(:secrets AS JSONB), 'active')"
        ),
        {
            "id": connection_id,
            "tid": tid,
            "config": (
                '{"host": "%s", "port": %d, "database": "%s", "username": "%s", "sslmode": "disable"}'
            )
            % (host, port, TENANT_STORE_DB, TENANT_STORE_USER),
            "secrets": '{"password_ref": "env://%s"}' % TENANT_STORE_PASSWORD_ENV,
        },
    )
    await conn.execute(
        text(
            "INSERT INTO public.tenant_data_planes (tenant_id, mode, status, connection_id) "
            "VALUES (:tid, 'tenant_owned', 'ready', CAST(:cid AS UUID))"
        ),
        {"tid": tid, "cid": connection_id},
    )
    return connection_id


async def _cleanup(engine, tenant_ids: list[str]) -> None:
    async with engine.begin() as conn:
        for tid in tenant_ids:
            await conn.execute(text("DELETE FROM public.tenants WHERE id = :id"), {"id": tid})


async def test_reconciler_reaches_a_residency_tenant(engine, setup_database):
    """Scenario: Reconciler reaches a residency tenant.

    One platform tenant and one ready tenant_owned tenant, each provisioned via
    `provision_role`'s no-`schemas` (fleet) path: the platform tenant's grants land on
    the platform database, the residency tenant's on `postgres-tenant-store`.
    """
    platform_tid = f"fleet-platform-{uuid.uuid4().hex[:8]}"
    residency_tid = f"fleet-resid-{uuid.uuid4().hex[:8]}"
    role_name = f"ner_chat_sql_fleet_{uuid.uuid4().hex[:8]}"

    async with engine.begin() as conn:
        await _insert_tenant(conn, platform_tid)
        await conn.execute(
            text(
                "INSERT INTO public.tenant_data_planes (tenant_id, mode, status) "
                "VALUES (:tid, 'platform', 'ready')"
            ),
            {"tid": platform_tid},
        )
        # platform_tid needs an actual schema to grant on.
        schema = f"tenant_{platform_tid.replace('-', '_')}"
        await conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema}"))
        await conn.execute(
            text(f"CREATE TABLE IF NOT EXISTS {schema}.documents (id VARCHAR PRIMARY KEY)")
        )

        await _insert_tenant(conn, residency_tid)
        await _insert_residency_connection(conn, residency_tid, host=TENANT_STORE_HOST, port=TENANT_STORE_PORT)
        residency_schema = f"tenant_{residency_tid.replace('-', '_')}"

    # Provisioning (group 10) creates the tenant's schema on its own store; this test
    # only exercises the fleet operation, so it stands that step up directly.
    store_engine = sqlalchemy.ext.asyncio.create_async_engine(
        f"postgresql+asyncpg://{TENANT_STORE_USER}:{os.environ[TENANT_STORE_PASSWORD_ENV]}"
        f"@{TENANT_STORE_HOST}:{TENANT_STORE_PORT}/{TENANT_STORE_DB}"
    )
    async with store_engine.begin() as conn:
        await conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {residency_schema}"))
        await conn.execute(
            text(f"CREATE TABLE IF NOT EXISTS {residency_schema}.documents (id VARCHAR PRIMARY KEY)")
        )
    await store_engine.dispose()

    try:
        async with engine.begin() as conn:
            covered = await provision_role(conn, role_name)
        assert schema in covered
        assert residency_schema in covered

        # The role must actually exist server-side on postgres-tenant-store too.
        store_engine2 = sqlalchemy.ext.asyncio.create_async_engine(
            f"postgresql+asyncpg://{TENANT_STORE_USER}:{os.environ[TENANT_STORE_PASSWORD_ENV]}"
            f"@{TENANT_STORE_HOST}:{TENANT_STORE_PORT}/{TENANT_STORE_DB}"
        )
        async with store_engine2.connect() as conn:
            role_row = (
                await conn.execute(
                    text("SELECT 1 FROM pg_roles WHERE rolname = :r"), {"r": role_name}
                )
            ).fetchone()
        assert role_row is not None
        async with store_engine2.begin() as conn:
            # Schema first: its privileges depend on the role, and CASCADE drops them.
            await conn.execute(text(f"DROP SCHEMA IF EXISTS {residency_schema} CASCADE"))
            await conn.execute(text(f"DROP ROLE IF EXISTS {role_name}"))
        await store_engine2.dispose()
    finally:
        async with engine.begin() as conn:
            await conn.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
        await _cleanup(engine, [platform_tid, residency_tid])


async def test_one_unreachable_store_does_not_abort_the_fleet_run(engine, setup_database):
    """Scenario: One unreachable store does not abort the fleet run."""
    ok_tid = f"fleet-ok-{uuid.uuid4().hex[:8]}"
    unreachable_tid = f"fleet-bad-{uuid.uuid4().hex[:8]}"
    role_name = f"ner_chat_sql_fleet2_{uuid.uuid4().hex[:8]}"

    async with engine.begin() as conn:
        await _insert_tenant(conn, ok_tid)
        await conn.execute(
            text(
                "INSERT INTO public.tenant_data_planes (tenant_id, mode, status) "
                "VALUES (:tid, 'platform', 'ready')"
            ),
            {"tid": ok_tid},
        )
        schema = f"tenant_{ok_tid.replace('-', '_')}"
        await conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema}"))
        await conn.execute(
            text(f"CREATE TABLE IF NOT EXISTS {schema}.documents (id VARCHAR PRIMARY KEY)")
        )

        await _insert_tenant(conn, unreachable_tid)
        # A port nothing listens on: connect fails quickly rather than timing out slowly.
        await _insert_residency_connection(conn, unreachable_tid, host=TENANT_STORE_HOST, port=1)

    try:
        async with engine.begin() as conn:
            covered = await provision_role(conn, role_name)
        assert schema in covered
        bad_schema = f"tenant_{unreachable_tid.replace('-', '_')}"
        assert bad_schema not in covered
    finally:
        async with engine.begin() as conn:
            await conn.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
        await _cleanup(engine, [ok_tid, unreachable_tid])
