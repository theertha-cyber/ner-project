"""Blob sync reads control-plane rows from the platform DB, not the tenant's data plane.

A `tenant_owned` tenant's ledger and documents live in its own store, which has no
`public.tenant_data_source_connections` or `public.tenant_integration_profiles`. Reading
those through the tenant session failed every sync with UndefinedTableError.
"""

import pytest

from src.document_service.blob_sync import sync as blob_sync
from src.shared.data_sources import lifecycle as lc

pytestmark = pytest.mark.asyncio


class _Session(str):
    async def commit(self):
        return None


class _Marked:
    """Async session factory whose sessions carry a label, so a test can tell which
    database a call was routed to."""

    def __init__(self, label):
        self.label = label

    def __call__(self):
        return self

    async def __aenter__(self):
        return _Session(self.label)

    async def __aexit__(self, *exc):
        return False


async def test_connection_and_profile_are_read_from_platform_session(monkeypatch):
    seen = {}

    async def _noop(*args, **kwargs):
        return None

    async def _connection(session, tenant_id, connection_id):
        seen["connection"] = session
        return (connection_id, "azure_blob", lc.STATUS_ACTIVE, {"container": "c"}, {})

    async def _retention(session, tenant_id):
        seen["retention"] = session
        return "none"  # not a sync-allowed mode: run stops at the retention gate

    for name in ("ensure_sync_tables", "record_run_start", "record_run_finish"):
        monkeypatch.setattr(blob_sync.ledger, name, _noop)
    monkeypatch.setattr(blob_sync, "_active_blob_connection", _connection)
    monkeypatch.setattr(blob_sync, "_profile_retention", _retention)
    monkeypatch.setattr(blob_sync, "_record_metric", lambda *a, **k: None)

    await blob_sync.run_sync(
        _Marked("tenant"), "tenant-a", "cid", "manual",
        provider=object(), platform_session_factory=_Marked("platform"),
    )

    assert seen == {"connection": "platform", "retention": "platform"}


async def test_platform_factory_defaults_to_the_session_factory(monkeypatch):
    seen = {}

    async def _noop(*args, **kwargs):
        return None

    async def _connection(session, tenant_id, connection_id):
        seen["connection"] = session
        return None  # inactive: run finishes as blocked

    for name in ("ensure_sync_tables", "record_run_start", "record_run_finish"):
        monkeypatch.setattr(blob_sync.ledger, name, _noop)
    monkeypatch.setattr(blob_sync, "_active_blob_connection", _connection)
    monkeypatch.setattr(blob_sync, "_record_metric", lambda *a, **k: None)

    await blob_sync.run_sync(_Marked("only"), "tenant-a", "cid", "manual")

    assert seen == {"connection": "only"}


async def test_tenant_engines_are_disposed_before_the_task_loop_ends(monkeypatch):
    """Each Celery task runs its own `asyncio.run`; a cached pooled engine reused by the
    next task fails with 'attached to a different loop'."""
    from src.document_service.blob_sync import tasks
    from src.shared import database

    disposed = []

    class _Resolver:
        async def invalidate_tenant(self, tenant_id):
            disposed.append(tenant_id)

    monkeypatch.setattr(database, "get_resolver", lambda: _Resolver())

    await tasks._dispose_tenant_engines(["tenant-a", "tenant-b"])

    assert disposed == ["tenant-a", "tenant-b"]


async def test_last_run_status_is_read_from_the_tenant_data_plane(monkeypatch):
    """The connection list is served from the platform DB but the run ledger is tenant
    data; reading it through the platform session showed `never_run` for a
    `tenant_owned` tenant whose runs had all succeeded."""
    from src.gateway.api.v1 import data_sources as api
    from src.shared.data_plane import DataPlaneNotReady

    seen = {}

    class _Resolver:
        async def resolve(self, tenant_id):
            seen["resolved"] = tenant_id
            return "tenant-engine"

    class _Sessions:
        def __init__(self, engine, **kwargs):
            seen["engine"] = engine

        def __call__(self):
            return _Marked("tenant-session")()

    async def _latest(session, tenant_id, ids):
        seen["session"] = session
        return {ids[0]: {"outcome": "succeeded", "completed_at": None}}

    monkeypatch.setattr(api, "get_resolver", lambda: _Resolver())
    monkeypatch.setattr(api, "async_sessionmaker", _Sessions)
    monkeypatch.setattr(api, "latest_sync_outcomes", _latest)

    runs = await api._latest_runs("tenant-a", ["c1"])

    assert runs == {"c1": {"outcome": "succeeded", "completed_at": None}}
    assert seen == {"resolved": "tenant-a", "engine": "tenant-engine", "session": "tenant-session"}

    class _NotReady:
        async def resolve(self, tenant_id):
            raise DataPlaneNotReady("migration_required")

    monkeypatch.setattr(api, "get_resolver", lambda: _NotReady())
    assert await api._latest_runs("tenant-a", ["c1"]) == {}
