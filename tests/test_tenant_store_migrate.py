"""Verification for `src/shared/tenant_store/migrate.py` (ADR-017, task 10.6) —
tenant-residency-store-provisioning spec scenarios #19, #20, and tenant-schema-
migrations spec scenario #64.

A synthetic tenant-store revision is written to `revisions/` for the duration of
each test (real file-based discovery, not a mock of `_discover`) so `migrate.main()`
exercises exactly the mechanism a real Alembic migration + tenant-store revision
pair would use.
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

_REVISIONS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "src", "shared", "tenant_store", "revisions",
)
_REVISION_FILE = os.path.join(_REVISIONS_DIR, "9999_test_deploy_marker.py")
_REVISION_MODULE = "src.shared.tenant_store.revisions.9999_test_deploy_marker"
_MARKER_COLUMN = "deploy_test_marker"

_REVISION_SOURCE = '''"""Synthetic revision for test_tenant_store_migrate.py — deleted after the test run."""

REVISION = 9999


def statements(schema: str) -> list[str]:
    return [
        f"ALTER TABLE {schema}.documents ADD COLUMN IF NOT EXISTS ''' + _MARKER_COLUMN + '''  TEXT",
    ]
'''


def _store_engine():
    return create_engine(
        f"postgresql://{TENANT_STORE_USER}:{os.environ[TENANT_STORE_PASSWORD_ENV]}@"
        f"{TENANT_STORE_HOST}:{TENANT_STORE_PORT}/{TENANT_STORE_DB}"
    )


def _write_synthetic_revision() -> None:
    """Writes a real revision module to disk (matching `revisions/NNNN_<name>.py`'s
    contract) so file-based discovery (`_discover` in `revisions/__init__.py`)
    picks it up like any shipped revision would.

    A plain helper, not a fixture: each test provisions its baseline-only tenant
    *before* calling this, so `apply.apply()` during provisioning does not already
    see revision 9999 and apply it up front — the whole point of the scenario is a
    store that is behind until `migrate.py` catches it up."""
    import importlib

    with open(_REVISION_FILE, "w", encoding="utf-8") as f:
        f.write(_REVISION_SOURCE)
    importlib.invalidate_caches()


def _remove_synthetic_revision() -> None:
    import glob
    import importlib

    if os.path.exists(_REVISION_FILE):
        os.remove(_REVISION_FILE)
    pycache = os.path.join(_REVISIONS_DIR, "__pycache__")
    if os.path.isdir(pycache):
        for f in glob.glob(os.path.join(pycache, "9999_test_deploy_marker*")):
            os.remove(f)
    importlib.invalidate_caches()


async def _provisioned_tenant_at_baseline(engine, *, tid: str) -> None:
    """A `ready` `tenant_owned` tenant whose store is at the baseline revision only
    (provisioned before the synthetic revision existed) — real schema on
    `postgres-tenant-store`, via `apply.apply()` with the revision fixture NOT yet
    active."""
    from src.shared.data_sources.providers import PROVIDER_AZURE_POSTGRESQL_DATA_PLANE
    from src.shared.tenant_store import apply as apply_module

    connection_id = str(uuid.uuid4())
    configuration = {
        "host": TENANT_STORE_HOST, "port": TENANT_STORE_PORT, "database": TENANT_STORE_DB,
        "username": TENANT_STORE_USER, "sslmode": "disable",
    }
    schema = f"tenant_{tid.replace('-', '_')}"
    async with engine.begin() as conn:
        await conn.execute(
            text("INSERT INTO public.tenants (id, name, slug) VALUES (:id, :n, :s)"),
            {"id": tid, "n": "Migrate Fixture", "s": f"slug-{tid}"},
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


async def _cleanup_tenant(engine, tid: str) -> None:
    schema = f"tenant_{tid.replace('-', '_')}"
    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM public.tenants WHERE id = :id"), {"id": tid})
    store_engine = _store_engine()
    with store_engine.connect() as store_conn:
        with store_conn.begin():
            store_conn.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
    store_engine.dispose()


def _has_marker_column(schema: str) -> bool:
    store_engine = _store_engine()
    try:
        with store_engine.connect() as store_conn:
            row = store_conn.execute(
                text(
                    "SELECT 1 FROM information_schema.columns "
                    "WHERE table_schema = :s AND table_name = 'documents' AND column_name = :c"
                ),
                {"s": schema, "c": _MARKER_COLUMN},
            ).fetchone()
            return row is not None
    finally:
        store_engine.dispose()


async def test_scenario_19_deploy_upgrades_a_residency_store(db_session, engine, setup_database):
    """Scenario #19: Deploy upgrades a residency store."""
    from src.shared.tenant_store.migrate import main as migrate_main

    tid = f"migrate-upgrade-{uuid.uuid4().hex[:8]}"
    schema = f"tenant_{tid.replace('-', '_')}"
    await _provisioned_tenant_at_baseline(engine, tid=tid)
    assert not _has_marker_column(schema)
    _write_synthetic_revision()
    try:
        exit_code = migrate_main()
        assert exit_code == 0
        assert _has_marker_column(schema)

        row = (
            await db_session.execute(
                text("SELECT status, schema_revision FROM public.tenant_data_planes WHERE tenant_id = :tid"),
                {"tid": tid},
            )
        ).fetchone()
        assert row.status == "ready"
        assert row.schema_revision == 9999
    finally:
        _remove_synthetic_revision()
        await _cleanup_tenant(engine, tid)


async def test_scenario_20_unreachable_store_during_deploy_is_isolated(db_session, engine, setup_database):
    """Scenario #20: Unreachable store during deploy is isolated."""
    from src.shared.data_sources.providers import PROVIDER_AZURE_POSTGRESQL_DATA_PLANE
    from src.shared.tenant_store.migrate import main as migrate_main

    reachable_tid = f"migrate-reachable-{uuid.uuid4().hex[:8]}"
    unreachable_tid = f"migrate-unreachable-{uuid.uuid4().hex[:8]}"
    reachable_schema = f"tenant_{reachable_tid.replace('-', '_')}"
    await _provisioned_tenant_at_baseline(engine, tid=reachable_tid)

    unreachable_connection_id = str(uuid.uuid4())
    async with engine.begin() as conn:
        await conn.execute(
            text("INSERT INTO public.tenants (id, name, slug) VALUES (:id, :n, :s)"),
            {"id": unreachable_tid, "n": "Migrate Unreachable Fixture", "s": f"slug-{unreachable_tid}"},
        )
        await conn.execute(
            text(
                "INSERT INTO public.tenant_data_source_connections "
                "(id, tenant_id, provider, configuration, secret_references, status) "
                "VALUES (:id, :tid, :provider, CAST(:config AS JSONB), CAST(:secrets AS JSONB), 'active')"
            ),
            {
                "id": unreachable_connection_id, "tid": unreachable_tid,
                "provider": PROVIDER_AZURE_POSTGRESQL_DATA_PLANE,
                "config": json.dumps(
                    {"host": "127.0.0.1", "port": 1, "database": "nope", "username": "nope", "sslmode": "disable"}
                ),
                "secrets": json.dumps({"password_ref": f"env://{TENANT_STORE_PASSWORD_ENV}"}),
            },
        )
        await conn.execute(
            text(
                "INSERT INTO public.tenant_data_planes "
                "(tenant_id, mode, status, connection_id, schema_revision) "
                "VALUES (:tid, 'tenant_owned', 'ready', :cid, 43)"
            ),
            {"tid": unreachable_tid, "cid": unreachable_connection_id},
        )

    _write_synthetic_revision()
    try:
        exit_code = migrate_main()
        assert exit_code == 0  # platform startup is never blocked

        assert _has_marker_column(reachable_schema)
        reachable_row = (
            await db_session.execute(
                text("SELECT status FROM public.tenant_data_planes WHERE tenant_id = :tid"),
                {"tid": reachable_tid},
            )
        ).fetchone()
        assert reachable_row.status == "ready"

        unreachable_row = (
            await db_session.execute(
                text("SELECT status, status_reason FROM public.tenant_data_planes WHERE tenant_id = :tid"),
                {"tid": unreachable_tid},
            )
        ).fetchone()
        assert unreachable_row.status == "migration_required"
        assert unreachable_row.status_reason == "unreachable"
    finally:
        _remove_synthetic_revision()
        await _cleanup_tenant(engine, reachable_tid)
        async with engine.begin() as conn:
            await conn.execute(text("DELETE FROM public.tenants WHERE id = :id"), {"id": unreachable_tid})


async def test_scenario_64_a_column_added_by_migration_reaches_both_planes(engine, setup_database):
    """Scenario #64: A column added by migration reaches both planes.

    The platform side of this pairing is the paired Alembic migration, which is out
    of scope for this change (no new tenant-scoped column ships with ADR-017) — this
    verifies the shared mechanism instead: the same revision `statements()` a real
    migration would call inside its `tenant_template` + `pg_namespace` loop (per
    `revisions/__init__.py`'s module docstring) produces the identical column on
    `tenant_template` (the platform plane's source of truth for new tenant schemas)
    and, via `migrate.py`, on a real tenant-owned store (the residency plane)."""
    from src.shared.tenant_store.migrate import main as migrate_main
    from src.shared.tenant_store.revisions import all_revisions

    tid = f"migrate-both-planes-{uuid.uuid4().hex[:8]}"
    schema = f"tenant_{tid.replace('-', '_')}"
    await _provisioned_tenant_at_baseline(engine, tid=tid)
    _write_synthetic_revision()
    try:
        revision = next(m for m in all_revisions() if m.REVISION == 9999)
        async with engine.begin() as conn:
            for statement in revision.statements("tenant_template"):
                await conn.execute(text(statement))
            platform_row = (
                await conn.execute(
                    text(
                        "SELECT 1 FROM information_schema.columns "
                        "WHERE table_schema = 'tenant_template' AND table_name = 'documents' "
                        "AND column_name = :c"
                    ),
                    {"c": _MARKER_COLUMN},
                )
            ).fetchone()
        assert platform_row is not None

        migrate_main()
        assert _has_marker_column(schema)
    finally:
        _remove_synthetic_revision()
        await _cleanup_tenant(engine, tid)
        async with engine.begin() as conn:
            await conn.execute(
                text(f"ALTER TABLE tenant_template.documents DROP COLUMN IF EXISTS {_MARKER_COLUMN}")
            )
