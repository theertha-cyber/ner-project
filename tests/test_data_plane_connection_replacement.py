"""Verification for "Replacement connections must point at the same store"
(ADR-017, task 10.3, tenant-residency-store-provisioning spec) — scenarios #21, #22.

Both scenarios run against the real `postgres-tenant-store` stand-in: a replacement
connection's own secure test reads the store identity marker written at
provisioning and compares it to the tenant's recorded `store_id`.
"""

import os
import uuid

import pytest
from sqlalchemy import create_engine, text

from src.shared.data_sources import lifecycle as lc
from src.shared.data_sources import service as svc
from src.shared.data_sources.providers import PROVIDER_AZURE_POSTGRESQL_DATA_PLANE

pytestmark = [pytest.mark.asyncio]

TENANT_STORE_HOST = "localhost"
TENANT_STORE_PORT = int(os.environ.get("NER_TEST_TENANT_STORE_PORT", "55433"))
TENANT_STORE_DB = os.environ.get("NER_TENANT_STORE_DB_NAME", "ner_tenant_store")
TENANT_STORE_USER = os.environ.get("NER_TENANT_STORE_DB_USER", "ner_tenant_store")
TENANT_STORE_PASSWORD_ENV = "NER_TEST_TENANT_STORE_PASSWORD"
os.environ.setdefault(TENANT_STORE_PASSWORD_ENV, os.environ.get("NER_TENANT_STORE_DB_PASSWORD", "ner_tenant_store"))

DP_CONFIG = {
    "host": TENANT_STORE_HOST,
    "port": TENANT_STORE_PORT,
    "database": TENANT_STORE_DB,
    "username": TENANT_STORE_USER,
    "sslmode": "verify-full",
}


def _store_engine():
    return create_engine(
        f"postgresql://{TENANT_STORE_USER}:{os.environ[TENANT_STORE_PASSWORD_ENV]}@"
        f"{TENANT_STORE_HOST}:{TENANT_STORE_PORT}/{TENANT_STORE_DB}"
    )


@pytest.fixture
async def ready_tenant_with_real_store(engine, setup_database):
    """A `tenant_owned` tenant already `ready`, with a real `tenant_<id>` schema and
    `platform_store_meta` row on `postgres-tenant-store` — provisioning itself is
    task 10.1's scope, so this fixture writes the post-provisioning state directly
    rather than running the Celery task."""
    from src.shared.tenant_store import apply as apply_module

    tid = f"dp-replace-{uuid.uuid4().hex[:8]}"
    connection_id = str(uuid.uuid4())
    schema = f"tenant_{tid.replace('-', '_')}"

    async with engine.begin() as conn:
        await conn.execute(
            text("INSERT INTO public.tenants (id, name, slug) VALUES (:id, :n, :s)"),
            {"id": tid, "n": "DP Replace Fixture", "s": f"slug-{tid}"},
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
                "config": __import__("json").dumps(DP_CONFIG),
                "secrets": __import__("json").dumps({"password_ref": f"env://{TENANT_STORE_PASSWORD_ENV}"}),
            },
        )
        await conn.execute(
            text(
                "INSERT INTO public.tenant_integration_profiles "
                "(tenant_id, retention_mode, status) VALUES (:tid, 'ephemeral', 'active')"
            ),
            {"tid": tid},
        )

    store_engine = _store_engine()
    with store_engine.connect() as store_conn:
        store_conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema}"))
        store_conn.commit()
        store_id, schema_revision = apply_module.apply(store_conn, schema, tid)
        store_conn.commit()
    store_engine.dispose()

    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO public.tenant_data_planes "
                "(tenant_id, mode, status, connection_id, store_id, schema_revision) "
                "VALUES (:tid, 'tenant_owned', 'ready', :cid, CAST(:sid AS UUID), :rev)"
            ),
            {"tid": tid, "cid": connection_id, "sid": store_id, "rev": schema_revision},
        )

    yield tid, connection_id, store_id

    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM public.tenants WHERE id = :id"), {"id": tid})
    store_engine = _store_engine()
    with store_engine.connect() as store_conn:
        with store_conn.begin():
            store_conn.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
    store_engine.dispose()


@pytest.fixture
def _relax_data_plane_tls(monkeypatch):
    """The stored configuration validates as `sslmode=verify-full` (production
    shape); the local Compose stand-in has no TLS, so the actual connect attempt
    relaxes it, exactly as `test_data_plane_provider_control_plane.py` does."""
    from src.shared.data_sources import data_plane_tester

    original_connection_string = data_plane_tester._connection_string
    monkeypatch.setattr(
        data_plane_tester,
        "_connection_string",
        lambda configuration, password: original_connection_string(
            {**configuration, "sslmode": "disable"}, password
        ),
    )


async def test_credential_rotation_keeps_the_tenant_ready(
    db_session, ready_tenant_with_real_store, _relax_data_plane_tls
):
    """Scenario: Credential rotation keeps the tenant ready."""
    tenant_id, connection_id, store_id = ready_tenant_with_real_store

    successor = await svc.replace_connection(
        db_session, tenant_id, connection_id, PROVIDER_AZURE_POSTGRESQL_DATA_PLANE,
        DP_CONFIG, {"password_ref": f"env://{TENANT_STORE_PASSWORD_ENV}"},
    )
    tested = await svc.test_connection(db_session, tenant_id, str(successor.id))
    assert tested.last_test_outcome == lc.TEST_OUTCOME_PASSED, tested.last_test_reason

    await svc.activate_connection(
        db_session, tenant_id, str(successor.id), ["network_approved", "governance_approved"],
    )

    dp_row = (
        await db_session.execute(
            text("SELECT status, connection_id, store_id FROM public.tenant_data_planes WHERE tenant_id = :tid"),
            {"tid": tenant_id},
        )
    ).fetchone()
    assert dp_row.status == "ready"
    assert str(dp_row.connection_id) == str(successor.id)
    assert str(dp_row.store_id) == str(store_id)

    predecessor = await svc.get_connection(db_session, tenant_id, connection_id)
    assert predecessor.status == lc.STATUS_RETIRED


async def test_pointing_at_a_different_store_is_rejected(
    db_session, ready_tenant_with_real_store, _relax_data_plane_tls
):
    """Scenario: Pointing at a different server is rejected.

    Simulated by recording a `store_id` on the tenant that does not match the real
    store's marker — the identity check the tester runs is exactly the comparison
    a genuinely different server would also fail."""
    tenant_id, connection_id, _store_id = ready_tenant_with_real_store

    await db_session.execute(
        text("UPDATE public.tenant_data_planes SET store_id = gen_random_uuid() WHERE tenant_id = :tid"),
        {"tid": tenant_id},
    )
    await db_session.commit()

    successor = await svc.replace_connection(
        db_session, tenant_id, connection_id, PROVIDER_AZURE_POSTGRESQL_DATA_PLANE,
        DP_CONFIG, {"password_ref": f"env://{TENANT_STORE_PASSWORD_ENV}"},
    )
    tested = await svc.test_connection(db_session, tenant_id, str(successor.id))
    assert tested.last_test_outcome == lc.TEST_OUTCOME_FAILED
    assert tested.last_test_reason == lc.TEST_REASON_STORE_IDENTITY_MISMATCH

    with pytest.raises(lc.LifecycleRejected) as excinfo:
        await svc.activate_connection(
            db_session, tenant_id, str(successor.id), ["network_approved", "governance_approved"],
        )
    assert excinfo.value.code == "TEST_FAILED"

    dp_row = (
        await db_session.execute(
            text("SELECT connection_id FROM public.tenant_data_planes WHERE tenant_id = :tid"),
            {"tid": tenant_id},
        )
    ).fetchone()
    assert str(dp_row.connection_id) == str(connection_id)
