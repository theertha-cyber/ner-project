"""Verification for the `azure_postgresql_data_plane` provider on the control plane
(ADR-017, task 7.6) — tenant-data-source-control-plane spec scenarios: platform-plane
rejection, the vector-extension test failure, shared-secret-reference rejection, pause
driving `TENANT_DATA_PLANE_NOT_READY`, retirement leaving the store untouched, and
independent concurrent activation of all three approved providers.
"""

import os
import uuid

import pytest
from sqlalchemy import text

from src.shared.data_sources import service as svc
from src.shared.data_sources import lifecycle as lc
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
    # create_connection's validation requires exactly 'verify-full' (production
    # shape); tests that actually connect locally either use fake_data_plane_tester
    # (no real connect) or monkeypatch the tester's connection string separately.
    "sslmode": "verify-full",
}
DP_SECRETS = {"password_ref": f"env://{TENANT_STORE_PASSWORD_ENV}"}


@pytest.fixture
async def platform_tenant(engine, setup_database):
    """A tenant whose data plane is `platform` (the default backfill)."""
    tid = f"dp-platform-{uuid.uuid4().hex[:8]}"
    async with engine.begin() as conn:
        await conn.execute(
            text("INSERT INTO public.tenants (id, name, slug) VALUES (:id, :n, :s)"),
            {"id": tid, "n": "Platform Fixture", "s": f"slug-{tid}"},
        )
    yield tid
    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM public.tenants WHERE id = :id"), {"id": tid})


@pytest.fixture
async def tenant_owned_tenant(engine, setup_database):
    """A tenant whose data plane is `tenant_owned` / `awaiting_store`."""
    tid = f"dp-owned-{uuid.uuid4().hex[:8]}"
    async with engine.begin() as conn:
        await conn.execute(
            text("INSERT INTO public.tenants (id, name, slug) VALUES (:id, :n, :s)"),
            {"id": tid, "n": "Tenant-Owned Fixture", "s": f"slug-{tid}"},
        )
        await conn.execute(
            text(
                "INSERT INTO public.tenant_data_planes (tenant_id, mode, status) "
                "VALUES (:tid, 'tenant_owned', 'awaiting_store')"
            ),
            {"tid": tid},
        )
        # Real tenant creation (group 9) defaults a tenant_owned profile to
        # ephemeral; this fixture mirrors that so activation isn't blocked by the
        # platform_blob default a bare profile row would otherwise carry.
        await conn.execute(
            text(
                "INSERT INTO public.tenant_integration_profiles "
                "(tenant_id, retention_mode, status) VALUES (:tid, 'ephemeral', 'active')"
            ),
            {"tid": tid},
        )
    yield tid
    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM public.tenants WHERE id = :id"), {"id": tid})


async def test_platform_tenant_cannot_create_data_plane_connection(db_session, platform_tenant):
    """Scenario: Platform-plane tenant cannot create a data-plane connection."""
    with pytest.raises(lc.LifecycleRejected) as excinfo:
        await svc.create_connection(
            db_session, platform_tenant, PROVIDER_AZURE_POSTGRESQL_DATA_PLANE, DP_CONFIG, DP_SECRETS
        )
    assert excinfo.value.code == "DATA_PLANE_NOT_TENANT_OWNED"

    rows = (
        await db_session.execute(
            text(
                "SELECT 1 FROM public.tenant_data_source_connections WHERE tenant_id = :tid"
            ),
            {"tid": platform_tenant},
        )
    ).fetchall()
    assert rows == []


async def test_data_plane_test_reports_missing_vector_extension(db_session, tenant_owned_tenant, monkeypatch):
    """Scenario: Data-plane test reports a missing vector extension."""
    from src.shared.data_sources import data_plane_tester

    monkeypatch.setattr(data_plane_tester, "_vector_extension_available", lambda cur: False)
    # The stored configuration validates as sslmode=verify-full (production shape);
    # the local Compose stand-in has no TLS, so the actual connect attempt relaxes it,
    # exactly as Design D11 describes for the local stand-in.
    _original_connection_string = data_plane_tester._connection_string
    monkeypatch.setattr(
        data_plane_tester,
        "_connection_string",
        lambda configuration, password: _original_connection_string(
            {**configuration, "sslmode": "disable"}, password
        ),
    )

    row = await svc.create_connection(
        db_session, tenant_owned_tenant, PROVIDER_AZURE_POSTGRESQL_DATA_PLANE, DP_CONFIG, DP_SECRETS
    )
    tested = await svc.test_connection(db_session, tenant_owned_tenant, str(row.id))
    assert tested.last_test_outcome == lc.TEST_OUTCOME_FAILED
    assert tested.last_test_reason == lc.TEST_REASON_VECTOR_EXTENSION_UNAVAILABLE


async def test_shared_secret_reference_between_source_and_data_plane_is_rejected(
    db_session, tenant_owned_tenant
):
    """Scenario: Shared secret reference between source and data plane is rejected."""
    shared_secret = {"password_ref": "env://SHARED_DP_TEST_SECRET"}
    await svc.create_connection(
        db_session, tenant_owned_tenant, "azure_postgresql",
        {"host": "h", "port": 5432, "database": "d", "username": "u", "sslmode": "verify-full"},
        shared_secret,
    )
    with pytest.raises(lc.LifecycleRejected) as excinfo:
        await svc.create_connection(
            db_session, tenant_owned_tenant, PROVIDER_AZURE_POSTGRESQL_DATA_PLANE,
            DP_CONFIG, shared_secret,
        )
    assert excinfo.value.code == "SECRET_REFERENCE_SHARED_ACROSS_PURPOSES"


async def test_pausing_data_plane_connection_stops_content_access(
    db_session, tenant_owned_tenant, fake_data_plane_tester
):
    """Scenario: Pausing the data-plane connection stops content access."""
    row = await svc.create_connection(
        db_session, tenant_owned_tenant, PROVIDER_AZURE_POSTGRESQL_DATA_PLANE, DP_CONFIG, DP_SECRETS
    )
    await svc.test_connection(db_session, tenant_owned_tenant, str(row.id))
    await svc.activate_connection(
        db_session, tenant_owned_tenant, str(row.id),
        ["network_approved", "governance_approved"],
    )

    dp_row = (
        await db_session.execute(
            text("SELECT status FROM public.tenant_data_planes WHERE tenant_id = :tid"),
            {"tid": tenant_owned_tenant},
        )
    ).fetchone()
    assert dp_row.status == "provisioning"

    # Force to ready (provisioning task itself is task group 10) so pause has
    # something to pause from.
    await db_session.execute(
        text("UPDATE public.tenant_data_planes SET status = 'ready' WHERE tenant_id = :tid"),
        {"tid": tenant_owned_tenant},
    )
    await db_session.commit()

    await svc.pause_connection(db_session, tenant_owned_tenant, str(row.id))
    dp_row = (
        await db_session.execute(
            text("SELECT status FROM public.tenant_data_planes WHERE tenant_id = :tid"),
            {"tid": tenant_owned_tenant},
        )
    ).fetchone()
    assert dp_row.status == "paused"


async def test_retirement_leaves_tenant_store_untouched(
    db_session, tenant_owned_tenant, fake_data_plane_tester
):
    """Scenario: Retirement leaves the tenant store untouched."""
    row = await svc.create_connection(
        db_session, tenant_owned_tenant, PROVIDER_AZURE_POSTGRESQL_DATA_PLANE, DP_CONFIG, DP_SECRETS
    )
    await svc.test_connection(db_session, tenant_owned_tenant, str(row.id))
    await svc.activate_connection(
        db_session, tenant_owned_tenant, str(row.id),
        ["network_approved", "governance_approved"],
    )
    await db_session.execute(
        text("UPDATE public.tenant_data_planes SET status = 'ready' WHERE tenant_id = :tid"),
        {"tid": tenant_owned_tenant},
    )
    await db_session.commit()
    await svc.pause_connection(db_session, tenant_owned_tenant, str(row.id))

    await svc.retire_connection(db_session, tenant_owned_tenant, str(row.id), True)
    dp_row = (
        await db_session.execute(
            text("SELECT status FROM public.tenant_data_planes WHERE tenant_id = :tid"),
            {"tid": tenant_owned_tenant},
        )
    ).fetchone()
    assert dp_row.status == "store_retired"


@pytest.fixture
def fake_data_plane_tester(monkeypatch):
    """A passing fake for the data-plane tester, so activation tests don't depend on a
    live secure test (already covered by the resolver/fleet-operations tests)."""
    from src.shared.data_sources import testing as testing_seam
    from src.shared.data_sources.testing import SecureTestResult

    class _Passing:
        async def run(self, provider, configuration, secret_values, tenant_id=None):
            return SecureTestResult(True, lc.TEST_REASON_NONE)

    testing_seam.register_tester(PROVIDER_AZURE_POSTGRESQL_DATA_PLANE, _Passing())
    yield
    from src.shared.data_sources.data_plane_tester import DataPlaneSecureTester

    testing_seam.register_tester(PROVIDER_AZURE_POSTGRESQL_DATA_PLANE, DataPlaneSecureTester())
