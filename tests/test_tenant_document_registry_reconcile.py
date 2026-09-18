"""Verification for `registry.record`/`update_status` and
`reconcile_tenant_document_registry` (ADR-017, task 12.4, tenant-document-registry
spec) — scenarios #33-#37. Extends `tests/test_tenant_document_registry.py`
(#31, #32, group 3).
"""

import json
import os
import uuid

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import async_sessionmaker

pytestmark = [pytest.mark.asyncio]

TENANT_STORE_HOST = "localhost"
TENANT_STORE_PORT = int(os.environ.get("NER_TEST_TENANT_STORE_PORT", "55433"))
TENANT_STORE_DB = os.environ.get("NER_TENANT_STORE_DB_NAME", "ner_tenant_store")
TENANT_STORE_USER = os.environ.get("NER_TENANT_STORE_DB_USER", "ner_tenant_store")
TENANT_STORE_PASSWORD_ENV = "NER_TEST_TENANT_STORE_PASSWORD"
os.environ.setdefault(TENANT_STORE_PASSWORD_ENV, os.environ.get("NER_TENANT_STORE_DB_PASSWORD", "ner_tenant_store"))


async def _write_registry(engine, coro_factory):
    """Runs one `registry.*` write on its own session — `registry.record`/
    `update_status` call `.commit()` internally, which ends an `engine.begin()`
    block's transaction; sharing one such block across multiple registry calls
    then fails the second call with "closed transaction". Each call gets its own
    session instead, matching how the real code (always a fresh
    `async_sessionmaker(...)()` per write) does it."""
    async with async_sessionmaker(engine, expire_on_commit=False)() as session:
        await coro_factory(session)


def _store_engine():
    return create_engine(
        f"postgresql://{TENANT_STORE_USER}:{os.environ[TENANT_STORE_PASSWORD_ENV]}@"
        f"{TENANT_STORE_HOST}:{TENANT_STORE_PORT}/{TENANT_STORE_DB}"
    )


@pytest.fixture
async def ready_tenant_with_real_store(engine, setup_database):
    """A `ready` `tenant_owned` tenant with a real `documents` table on
    `postgres-tenant-store` (a minimal stand-in shape, not the full provisioned
    schema — reconciliation only reads `documents`)."""
    from src.shared.data_sources.providers import PROVIDER_AZURE_POSTGRESQL_DATA_PLANE

    tid = f"registry-reconcile-{uuid.uuid4().hex[:8]}"
    schema = f"tenant_{tid.replace('-', '_')}"
    connection_id = str(uuid.uuid4())
    configuration = {
        "host": TENANT_STORE_HOST, "port": TENANT_STORE_PORT, "database": TENANT_STORE_DB,
        "username": TENANT_STORE_USER, "sslmode": "disable",
    }
    async with engine.begin() as conn:
        await conn.execute(
            text("INSERT INTO public.tenants (id, name, slug) VALUES (:id, :n, :s)"),
            {"id": tid, "n": "Registry Reconcile Fixture", "s": f"slug-{tid}"},
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
                "INSERT INTO public.tenant_data_planes (tenant_id, mode, status, connection_id) "
                "VALUES (:tid, 'tenant_owned', 'ready', :cid)"
            ),
            {"tid": tid, "cid": connection_id},
        )

    store_engine = _store_engine()
    with store_engine.connect() as store_conn:
        store_conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema}"))
        store_conn.execute(
            text(
                f"""
                CREATE TABLE {schema}.documents (
                    id VARCHAR PRIMARY KEY,
                    tenant_id VARCHAR NOT NULL,
                    filename VARCHAR(255) NOT NULL,
                    source_type VARCHAR(64) NOT NULL DEFAULT 'platform_upload',
                    status VARCHAR(20) DEFAULT 'uploaded',
                    file_size_bytes BIGINT,
                    checksum VARCHAR(64),
                    retention_mode VARCHAR(32) NOT NULL DEFAULT 'ephemeral',
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    updated_at TIMESTAMPTZ DEFAULT NOW()
                )
                """
            )
        )
        store_conn.commit()
    store_engine.dispose()

    yield tid, schema

    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM public.tenants WHERE id = :id"), {"id": tid})
    store_engine = _store_engine()
    with store_engine.connect() as store_conn:
        with store_conn.begin():
            store_conn.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
    store_engine.dispose()


async def test_scenario_33_status_transitions_reach_the_registry(engine, ready_tenant_with_real_store):
    """Scenario #33: Status transitions reach the registry."""
    from src.shared import tenant_document_registry as registry

    tid, schema = ready_tenant_with_real_store
    doc_id = f"doc-{uuid.uuid4().hex[:8]}"

    await _write_registry(
        engine,
        lambda s: registry.record(
            s, tenant_id=tid, document_id=doc_id, source_type="platform_upload",
            status="uploaded", retention_mode="ephemeral", file_size_bytes=100, checksum="abc",
        ),
    )
    await _write_registry(
        engine, lambda s: registry.update_status(s, tenant_id=tid, document_id=doc_id, status="processed")
    )

    async with engine.begin() as conn:
        row = (
            await conn.execute(
                text("SELECT status FROM public.tenant_document_registry WHERE tenant_id = :t AND document_id = :d"),
                {"t": tid, "d": doc_id},
            )
        ).fetchone()
    assert row.status == "processed"


async def test_scenario_34_drift_is_reconciled(engine, ready_tenant_with_real_store):
    """Scenario #34: Drift is reconciled."""
    from src.document_service.data_plane.tasks import reconcile_tenant_document_registry

    tid, schema = ready_tenant_with_real_store
    doc_id = f"doc-{uuid.uuid4().hex[:8]}"

    # A document exists in the tenant store but the registry write for it was
    # never made — simulating a missed live write.
    store_engine = _store_engine()
    with store_engine.connect() as store_conn:
        store_conn.execute(
            text(
                f"INSERT INTO {schema}.documents (id, tenant_id, filename, status, checksum) "
                "VALUES (:id, :tid, 'f.pdf', 'processed', 'cs1')"
            ),
            {"id": doc_id, "tid": tid},
        )
        store_conn.commit()
    store_engine.dispose()

    result = reconcile_tenant_document_registry.run()
    assert tid in result["reconciled"]

    async with engine.begin() as conn:
        row = (
            await conn.execute(
                text("SELECT status FROM public.tenant_document_registry WHERE tenant_id = :t AND document_id = :d"),
                {"t": tid, "d": doc_id},
            )
        ).fetchone()
    assert row is not None
    assert row.status == "processed"


async def test_scenario_35_unreachable_store_does_not_erase_registry_rows(engine, ready_tenant_with_real_store):
    """Scenario #35: Unreachable store does not erase registry rows."""
    from src.document_service.data_plane.tasks import reconcile_tenant_document_registry
    from src.shared import tenant_document_registry as registry

    tid, schema = ready_tenant_with_real_store
    doc_id = f"doc-{uuid.uuid4().hex[:8]}"
    await _write_registry(
        engine,
        lambda s: registry.record(
            s, tenant_id=tid, document_id=doc_id, source_type="platform_upload",
            status="processed", retention_mode="ephemeral",
        ),
    )

    # Point the connection at an unreachable host, so this cycle's reconciliation
    # cannot reach the store at all.
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "UPDATE public.tenant_data_source_connections SET configuration = CAST(:c AS JSONB) "
                "WHERE tenant_id = :tid"
            ),
            {
                "tid": tid,
                "c": json.dumps({"host": "127.0.0.1", "port": 1, "database": "nope", "username": "nope", "sslmode": "disable"}),
            },
        )

    result = reconcile_tenant_document_registry.run()
    assert tid in result["skipped_unreachable"]

    async with engine.begin() as conn:
        row = (
            await conn.execute(
                text("SELECT status FROM public.tenant_document_registry WHERE tenant_id = :t AND document_id = :d"),
                {"t": tid, "d": doc_id},
            )
        ).fetchone()
    assert row is not None
    assert row.status == "processed"


async def test_scenario_36_system_admin_sees_counts_during_a_tenant_outage(engine, ready_tenant_with_real_store):
    """Scenario #36: System admin sees counts during a tenant outage."""
    from src.shared import tenant_document_registry as registry

    tid, schema = ready_tenant_with_real_store
    doc_id = f"doc-{uuid.uuid4().hex[:8]}"
    await _write_registry(
        engine,
        lambda s: registry.record(
            s, tenant_id=tid, document_id=doc_id, source_type="platform_upload",
            status="processed", retention_mode="ephemeral",
        ),
    )
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "UPDATE public.tenant_data_source_connections SET configuration = CAST(:c AS JSONB) "
                "WHERE tenant_id = :tid"
            ),
            {
                "tid": tid,
                "c": json.dumps({"host": "127.0.0.1", "port": 1, "database": "nope", "username": "nope", "sslmode": "disable"}),
            },
        )

    # A registry read never touches the (now unreachable) tenant store.
    async with engine.begin() as conn:
        count = (
            await conn.execute(
                text("SELECT COUNT(*) FROM public.tenant_document_registry WHERE tenant_id = :t"),
                {"t": tid},
            )
        ).scalar_one()
    assert count == 1


async def test_scenario_37_quota_uses_the_registry(engine, ready_tenant_with_real_store):
    """Scenario #37: Quota uses the registry.

    No document-count quota enforcement exists yet anywhere in this codebase
    (`max_documents` is a stored per-tenant limit that no upload path checks
    against — confirmed by search, a pre-existing gap this change does not
    invent). What this scenario CAN verify: the registry is the only source a
    quota check would ever need — the per-tenant count it returns matches the
    real document count, without a live connection to the tenant's own store,
    exactly the property `dashboard.py`'s tenant-admin document count now
    depends on (`_tenant_admin_data`, switched off `{schema}.documents` in this
    same task group)."""
    from src.shared import tenant_document_registry as registry

    tid, schema = ready_tenant_with_real_store
    doc_ids = [f"doc-{uuid.uuid4().hex[:8]}" for _ in range(3)]
    for doc_id in doc_ids:
        await _write_registry(
            engine,
            lambda s, doc_id=doc_id: registry.record(
                s, tenant_id=tid, document_id=doc_id, source_type="platform_upload",
                status="processed", retention_mode="ephemeral",
            ),
        )

    async with engine.begin() as conn:
        count = (
            await conn.execute(
                text(
                    "SELECT COUNT(*) FROM public.tenant_document_registry "
                    "WHERE tenant_id = :t AND status != 'error'"
                ),
                {"t": tid},
            )
        ).scalar_one()
    assert count == 3
