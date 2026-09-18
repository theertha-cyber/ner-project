"""Verification for `provision_tenant_data_plane` against
`tenant-residency-store-provisioning` spec scenarios #13-#16 (ADR-017, task 10.5).

Runs against the real `postgres-tenant-store` stand-in throughout.
"""

import json
import os
import uuid

import pytest
from sqlalchemy import create_engine, text

pytestmark = [pytest.mark.asyncio]

TENANT_STORE_HOST = "localhost"
TENANT_STORE_PORT = int(os.environ.get("NER_TEST_TENANT_STORE_PORT", "55433"))
TENANT_STORE_DB = os.environ.get("NER_TENANT_STORE_DB_NAME", "ner_tenant_store")
TENANT_STORE_USER = os.environ.get("NER_TENANT_STORE_DB_USER", "ner_tenant_store")
TENANT_STORE_PASSWORD_ENV = "NER_TEST_TENANT_STORE_PASSWORD"
os.environ.setdefault(TENANT_STORE_PASSWORD_ENV, os.environ.get("NER_TENANT_STORE_DB_PASSWORD", "ner_tenant_store"))


def _store_engine():
    return create_engine(
        f"postgresql://{TENANT_STORE_USER}:{os.environ[TENANT_STORE_PASSWORD_ENV]}@"
        f"{TENANT_STORE_HOST}:{TENANT_STORE_PORT}/{TENANT_STORE_DB}"
    )


async def _make_provisioning_tenant(engine, *, tid: str) -> str:
    from src.shared.data_sources.providers import PROVIDER_AZURE_POSTGRESQL_DATA_PLANE

    connection_id = str(uuid.uuid4())
    configuration = {
        "host": TENANT_STORE_HOST,
        "port": TENANT_STORE_PORT,
        "database": TENANT_STORE_DB,
        "username": TENANT_STORE_USER,
        "sslmode": "disable",
    }
    async with engine.begin() as conn:
        await conn.execute(
            text("INSERT INTO public.tenants (id, name, slug) VALUES (:id, :n, :s)"),
            {"id": tid, "n": "Store Provisioning Fixture", "s": f"slug-{tid}"},
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
                "config": json.dumps(configuration),
                "secrets": json.dumps({"password_ref": f"env://{TENANT_STORE_PASSWORD_ENV}"}),
            },
        )
        await conn.execute(
            text(
                "INSERT INTO public.tenant_data_planes "
                "(tenant_id, mode, status, connection_id) "
                "VALUES (:tid, 'tenant_owned', 'provisioning', :cid)"
            ),
            {"tid": tid, "cid": connection_id},
        )
    return connection_id


async def _cleanup(engine, tid: str) -> None:
    schema = f"tenant_{tid.replace('-', '_')}"
    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM public.tenants WHERE id = :id"), {"id": tid})
    store_engine = _store_engine()
    with store_engine.connect() as store_conn:
        with store_conn.begin():
            store_conn.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
    store_engine.dispose()


@pytest.fixture
async def provisioning_tenant(engine, setup_database):
    tid = f"srp-{uuid.uuid4().hex[:8]}"
    await _make_provisioning_tenant(engine, tid=tid)
    yield tid
    await _cleanup(engine, tid)


async def test_scenario_13_successful_provisioning_makes_the_tenant_ready(db_session, engine, provisioning_tenant):
    """Scenario #13: Successful provisioning makes the tenant ready."""
    from src.document_service.data_plane.tasks import provision_tenant_data_plane

    result = provision_tenant_data_plane.run(provisioning_tenant)
    assert result["outcome"] == "ready"

    row = (
        await db_session.execute(
            text("SELECT status, store_id, schema_revision FROM public.tenant_data_planes WHERE tenant_id = :tid"),
            {"tid": provisioning_tenant},
        )
    ).fetchone()
    assert row.status == "ready"
    assert row.store_id is not None
    assert row.schema_revision is not None

    schema = f"tenant_{provisioning_tenant.replace('-', '_')}"
    store_engine = _store_engine()
    with store_engine.connect() as store_conn:
        tables = {
            r[0]
            for r in store_conn.execute(
                text("SELECT tablename FROM pg_tables WHERE schemaname = :s"), {"s": schema}
            ).fetchall()
        }
    store_engine.dispose()
    assert "platform_store_meta" in tables


async def test_scenario_14_provisioning_failure_is_safe_and_retryable(db_session, engine, provisioning_tenant, monkeypatch):
    """Scenario #14: Provisioning failure is safe and retryable.

    Schema creation is made to fail part-way by breaking the query-role step on the
    first attempt only; the retry, with the fault removed, completes without error
    on the objects the first attempt already created (idempotent statements)."""
    import src.document_service.data_plane.tasks as tasks_module
    from src.chat_api.services import sql_execution_role

    real_build_role_statements = sql_execution_role.build_role_statements
    call_count = {"n": 0}

    def _fail_once_then_real(role_name, schemas, generated_tables=None):
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise RuntimeError("simulated mid-provisioning failure")
        return real_build_role_statements(role_name, schemas, generated_tables)

    monkeypatch.setattr(sql_execution_role, "build_role_statements", _fail_once_then_real)

    first = tasks_module.provision_tenant_data_plane.run(provisioning_tenant)
    assert first["outcome"] == "store_unreachable"

    row = (
        await db_session.execute(
            text("SELECT status, status_reason FROM public.tenant_data_planes WHERE tenant_id = :tid"),
            {"tid": provisioning_tenant},
        )
    ).fetchone()
    assert row.status == "provisioning_failed"
    assert row.status_reason == "store_unreachable"

    # Retry: CAS back to `provisioning` (what the `/data-plane/provision` retry
    # endpoint does), then re-run with the fault removed.
    await db_session.execute(
        text("UPDATE public.tenant_data_planes SET status = 'provisioning' WHERE tenant_id = :tid"),
        {"tid": provisioning_tenant},
    )
    await db_session.commit()

    second = tasks_module.provision_tenant_data_plane.run(provisioning_tenant)
    assert second["outcome"] == "ready"

    row = (
        await db_session.execute(
            text("SELECT status FROM public.tenant_data_planes WHERE tenant_id = :tid"),
            {"tid": provisioning_tenant},
        )
    ).fetchone()
    assert row.status == "ready"


async def test_scenario_15_provisioning_refuses_a_non_empty_foreign_schema(db_session, engine, provisioning_tenant):
    """Scenario #15: Provisioning refuses a non-empty foreign schema."""
    from src.document_service.data_plane.tasks import provision_tenant_data_plane

    schema = f"tenant_{provisioning_tenant.replace('-', '_')}"
    store_engine = _store_engine()
    with store_engine.connect() as store_conn:
        with store_conn.begin():
            store_conn.execute(text(f"CREATE SCHEMA {schema}"))
            store_conn.execute(text(f"CREATE TABLE {schema}.foreign_table (id INT)"))
    store_engine.dispose()

    result = provision_tenant_data_plane.run(provisioning_tenant)
    assert result["outcome"] == "target_schema_not_empty"

    row = (
        await db_session.execute(
            text("SELECT status, status_reason FROM public.tenant_data_planes WHERE tenant_id = :tid"),
            {"tid": provisioning_tenant},
        )
    ).fetchone()
    assert row.status == "provisioning_failed"
    assert row.status_reason == "target_schema_not_empty"

    store_engine = _store_engine()
    with store_engine.connect() as store_conn:
        still_there = store_conn.execute(
            text(
                "SELECT 1 FROM information_schema.tables "
                "WHERE table_schema = :s AND table_name = 'foreign_table'"
            ),
            {"s": schema},
        ).fetchone()
        no_meta = store_conn.execute(
            text(
                "SELECT 1 FROM information_schema.tables "
                "WHERE table_schema = :s AND table_name = 'platform_store_meta'"
            ),
            {"s": schema},
        ).fetchone()
    store_engine.dispose()
    assert still_there is not None
    assert no_meta is None


async def test_scenario_16_no_platform_schema_is_created_for_a_residency_tenant(db_session, engine, provisioning_tenant):
    """Scenario #16: No platform schema is created for a residency tenant."""
    from src.document_service.data_plane.tasks import provision_tenant_data_plane

    result = provision_tenant_data_plane.run(provisioning_tenant)
    assert result["outcome"] == "ready"

    schema = f"tenant_{provisioning_tenant.replace('-', '_')}"
    async with engine.connect() as conn:
        row = (
            await conn.execute(
                text("SELECT 1 FROM information_schema.schemata WHERE schema_name = :s"),
                {"s": schema},
            )
        ).fetchone()
    assert row is None
