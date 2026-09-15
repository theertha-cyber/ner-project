"""Verification for the recovery sweep half of task 11.3
(`_recover_stuck_documents`, `probe_tenant_data_plane_health`) — a document a
worker abandoned mid-OCR when a tenant's store went down is resumed once the
next probe detects the store reachable again, and a document merely still
in-flight (recent `processing`) is left alone.
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


@pytest.fixture
async def ready_tenant_with_real_store(engine, setup_database):
    """A `ready` `tenant_owned` tenant with a real, fully-provisioned schema on
    `postgres-tenant-store` (via the same `apply_module.apply` provisioning
    every other real-infra test in this suite uses)."""
    from src.shared.data_sources.providers import PROVIDER_AZURE_POSTGRESQL_DATA_PLANE
    from src.shared.tenant_store import apply as apply_module

    tid = f"recovery-{uuid.uuid4().hex[:8]}"
    schema = f"tenant_{tid.replace('-', '_')}"
    connection_id = str(uuid.uuid4())
    configuration = {
        "host": TENANT_STORE_HOST, "port": TENANT_STORE_PORT, "database": TENANT_STORE_DB,
        "username": TENANT_STORE_USER, "sslmode": "disable",
    }
    async with engine.begin() as conn:
        await conn.execute(
            text("INSERT INTO public.tenants (id, name, slug) VALUES (:id, :n, :s)"),
            {"id": tid, "n": "Recovery Sweep Fixture", "s": f"slug-{tid}"},
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
        # Recorded `unreachable`: the exact state a prior probe or resolver
        # failure would have left, so this probe's `HEALTHY` result is a
        # genuine recovery transition, not the tenant's first-ever probe.
        await conn.execute(
            text(
                "INSERT INTO public.tenant_data_planes "
                "(tenant_id, mode, status, connection_id, health_outcome, health_checked_at) "
                "VALUES (:tid, 'tenant_owned', 'ready', :cid, 'unreachable', NOW())"
            ),
            {"tid": tid, "cid": connection_id},
        )

    store_engine = _store_engine()
    with store_engine.connect() as store_conn:
        store_conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema}"))
        store_conn.commit()
        apply_module.apply(store_conn, schema, tid)
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


def _insert_processing_document(schema: str, tenant_id: str, *, stale: bool) -> str:
    """A `source_only` document with no reopener registered — `process_document`
    deterministically resolves it as `ContentUnresolvable` and marks it `failed`,
    which is exactly the observable proof this test needs that the sweep really
    dispatched processing (not just reset a status column)."""
    doc_id = f"doc-{uuid.uuid4().hex[:8]}"
    store_engine = _store_engine()
    with store_engine.connect() as store_conn:
        store_conn.execute(
            text(
                f"""
                INSERT INTO {schema}.documents
                    (id, tenant_id, filename, status, purpose, source_type, source_id,
                     retention_mode, created_at, updated_at)
                VALUES
                    (:id, :tid, 'stuck.pdf', 'processing', 'query', 'platform_upload',
                     'no-such-source', 'source_only', NOW(),
                     NOW() - make_interval(secs => :age))
                """
            ),
            {"id": doc_id, "tid": tenant_id, "age": 600 if stale else 5},
        )
        store_conn.commit()
    store_engine.dispose()
    return doc_id


def _read_status(schema: str, doc_id: str) -> str:
    store_engine = _store_engine()
    try:
        with store_engine.connect() as store_conn:
            return store_conn.execute(
                text(f"SELECT status FROM {schema}.documents WHERE id = :id"), {"id": doc_id}
            ).scalar_one()
    finally:
        store_engine.dispose()


async def test_stale_processing_document_is_resumed_on_recovery(engine, ready_tenant_with_real_store):
    """A document stuck in `processing` longer than the threshold is reset and
    redispatched once the probe detects the store has come back."""
    from src.document_service.data_plane.tasks import probe_tenant_data_plane_health

    tid, schema = ready_tenant_with_real_store
    stale_doc = _insert_processing_document(schema, tid, stale=True)

    result = probe_tenant_data_plane_health.run()
    assert stale_doc in result["recovered"].get(tid, [])

    # process_document really ran: the document moved all the way to `failed`
    # (unresolvable source), not merely back to `pending`.
    assert _read_status(schema, stale_doc) == "failed"


async def test_recent_processing_document_is_left_alone(engine, ready_tenant_with_real_store):
    """A document still well within a normal processing window is not stolen
    from whatever worker may still be handling it."""
    from src.document_service.data_plane.tasks import probe_tenant_data_plane_health

    tid, schema = ready_tenant_with_real_store
    recent_doc = _insert_processing_document(schema, tid, stale=False)

    result = probe_tenant_data_plane_health.run()
    assert recent_doc not in result["recovered"].get(tid, [])
    assert _read_status(schema, recent_doc) == "processing"
