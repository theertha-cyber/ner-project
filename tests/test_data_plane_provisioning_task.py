"""Verification for `provision_tenant_data_plane` (ADR-017, task 10.1): the Celery
task that turns `provisioning` into `ready` against a real second Postgres server
(`postgres-tenant-store`), and CAS's to `provisioning_failed` with a finite reason
on a failure that must not leave the row at `provisioning`.
"""

import os
import uuid

import pytest
from sqlalchemy import text

pytestmark = [pytest.mark.asyncio]

TENANT_STORE_HOST = "localhost"
TENANT_STORE_PORT = int(os.environ.get("NER_TEST_TENANT_STORE_PORT", "55433"))
TENANT_STORE_DB = os.environ.get("NER_TENANT_STORE_DB_NAME", "ner_tenant_store")
TENANT_STORE_USER = os.environ.get("NER_TENANT_STORE_DB_USER", "ner_tenant_store")
TENANT_STORE_PASSWORD_ENV = "NER_TEST_TENANT_STORE_PASSWORD"
os.environ.setdefault(TENANT_STORE_PASSWORD_ENV, os.environ.get("NER_TENANT_STORE_DB_PASSWORD", "ner_tenant_store"))


@pytest.fixture
async def provisioning_tenant(engine, setup_database):
    """A `tenant_owned` tenant in `provisioning`, with a real connection row pointing
    at the local `postgres-tenant-store` stand-in over a non-TLS local link."""
    from src.shared.data_sources.providers import PROVIDER_AZURE_POSTGRESQL_DATA_PLANE

    tid = f"dp-task-{uuid.uuid4().hex[:8]}"
    configuration = {
        "host": TENANT_STORE_HOST,
        "port": TENANT_STORE_PORT,
        "database": TENANT_STORE_DB,
        "username": TENANT_STORE_USER,
        "sslmode": "disable",
    }
    secret_references = {"password_ref": f"env://{TENANT_STORE_PASSWORD_ENV}"}
    connection_id = str(uuid.uuid4())
    async with engine.begin() as conn:
        await conn.execute(
            text("INSERT INTO public.tenants (id, name, slug) VALUES (:id, :n, :s)"),
            {"id": tid, "n": "DP Task Fixture", "s": f"slug-{tid}"},
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
                "config": __import__("json").dumps(configuration),
                "secrets": __import__("json").dumps(secret_references),
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
    yield tid, connection_id
    schema = f"tenant_{tid.replace('-', '_')}"
    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM public.tenants WHERE id = :id"), {"id": tid})
    from sqlalchemy import create_engine as _create_engine

    store_engine = _create_engine(
        f"postgresql://{TENANT_STORE_USER}:{os.environ[TENANT_STORE_PASSWORD_ENV]}@"
        f"{TENANT_STORE_HOST}:{TENANT_STORE_PORT}/{TENANT_STORE_DB}"
    )
    with store_engine.connect() as store_conn:
        with store_conn.begin():
            store_conn.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
    store_engine.dispose()


async def test_provisioning_task_moves_ready_and_creates_store(db_session, provisioning_tenant):
    tenant_id, _connection_id = provisioning_tenant
    from src.document_service.data_plane.tasks import provision_tenant_data_plane

    result = provision_tenant_data_plane.run(tenant_id)
    assert result["outcome"] == "ready", result

    row = (
        await db_session.execute(
            text(
                "SELECT status, status_reason, store_id, schema_revision "
                "FROM public.tenant_data_planes WHERE tenant_id = :tid"
            ),
            {"tid": tenant_id},
        )
    ).fetchone()
    assert row.status == "ready"
    assert row.status_reason == "provisioned"
    assert row.store_id is not None
    assert row.schema_revision is not None

    schema = f"tenant_{tenant_id.replace('-', '_')}"
    from sqlalchemy import create_engine as _create_engine

    store_engine = _create_engine(
        f"postgresql://{TENANT_STORE_USER}:{os.environ[TENANT_STORE_PASSWORD_ENV]}@"
        f"{TENANT_STORE_HOST}:{TENANT_STORE_PORT}/{TENANT_STORE_DB}"
    )
    with store_engine.connect() as store_conn:
        meta = store_conn.execute(
            text(f"SELECT store_id FROM {schema}.platform_store_meta LIMIT 1")
        ).fetchone()
        assert meta is not None
    store_engine.dispose()


async def test_provisioning_task_marks_failed_on_unreachable_store(db_session, engine):
    from src.shared.data_sources.providers import PROVIDER_AZURE_POSTGRESQL_DATA_PLANE

    tid = f"dp-task-fail-{uuid.uuid4().hex[:8]}"
    connection_id = str(uuid.uuid4())
    configuration = {
        "host": "127.0.0.1",
        "port": 1,
        "database": "nope",
        "username": "nope",
        "sslmode": "disable",
    }
    async with engine.begin() as conn:
        await conn.execute(
            text("INSERT INTO public.tenants (id, name, slug) VALUES (:id, :n, :s)"),
            {"id": tid, "n": "DP Task Fail Fixture", "s": f"slug-{tid}"},
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
                "config": __import__("json").dumps(configuration),
                "secrets": __import__("json").dumps({"password_ref": f"env://{TENANT_STORE_PASSWORD_ENV}"}),
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

    from src.document_service.data_plane.tasks import provision_tenant_data_plane

    result = provision_tenant_data_plane.run(tid)
    assert result["outcome"] == "store_unreachable"

    row = (
        await db_session.execute(
            text("SELECT status, status_reason FROM public.tenant_data_planes WHERE tenant_id = :tid"),
            {"tid": tid},
        )
    ).fetchone()
    assert row.status == "provisioning_failed"
    assert row.status_reason == "store_unreachable"

    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM public.tenants WHERE id = :id"), {"id": tid})
