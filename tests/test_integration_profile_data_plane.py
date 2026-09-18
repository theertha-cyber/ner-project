"""Verification for the tenant-integration-profile ADDED requirement (ADR-017, task
8.3): `tenant_owned` tenants forbid `platform_blob` retention, both on the profile
write path and on data-plane connection activation.
"""

import uuid

import pytest
from sqlalchemy import text

from src.shared.integration_profile.service import (
    RetentionModeNotPermittedForDataPlane,
    write_profile,
)

pytestmark = [pytest.mark.asyncio]


@pytest.fixture
async def tenant_owned_tenant(engine, setup_database):
    tid = f"ip-owned-{uuid.uuid4().hex[:8]}"
    async with engine.begin() as conn:
        await conn.execute(
            text("INSERT INTO public.tenants (id, name, slug) VALUES (:id, :n, :s)"),
            {"id": tid, "n": "IP Owned Fixture", "s": f"slug-{tid}"},
        )
        await conn.execute(
            text(
                "INSERT INTO public.tenant_data_planes (tenant_id, mode, status) "
                "VALUES (:tid, 'tenant_owned', 'awaiting_store')"
            ),
            {"tid": tid},
        )
        await conn.execute(
            text(
                "INSERT INTO public.tenant_integration_profiles (tenant_id, status, retention_mode) "
                "VALUES (:tid, 'draft', 'ephemeral') ON CONFLICT (tenant_id) DO NOTHING"
            ),
            {"tid": tid},
        )
    yield tid
    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM public.tenants WHERE id = :id"), {"id": tid})


@pytest.fixture
async def platform_tenant(engine, setup_database):
    tid = f"ip-platform-{uuid.uuid4().hex[:8]}"
    async with engine.begin() as conn:
        await conn.execute(
            text("INSERT INTO public.tenants (id, name, slug) VALUES (:id, :n, :s)"),
            {"id": tid, "n": "IP Platform Fixture", "s": f"slug-{tid}"},
        )
        await conn.execute(
            text(
                "INSERT INTO public.tenant_integration_profiles (tenant_id, status) "
                "VALUES (:tid, 'draft') ON CONFLICT (tenant_id) DO NOTHING"
            ),
            {"tid": tid},
        )
    yield tid
    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM public.tenants WHERE id = :id"), {"id": tid})


async def test_platform_blob_retention_is_rejected_for_a_residency_tenant(
    db_session, tenant_owned_tenant
):
    """Scenario: Platform blob retention is rejected for a residency tenant."""
    with pytest.raises(RetentionModeNotPermittedForDataPlane) as excinfo:
        await write_profile(db_session, tenant_owned_tenant, retention_mode="platform_blob")
    assert excinfo.value.code == "RETENTION_MODE_NOT_PERMITTED_FOR_DATA_PLANE"

    row = (
        await db_session.execute(
            text(
                "SELECT retention_mode FROM public.tenant_integration_profiles "
                "WHERE tenant_id = :tid"
            ),
            {"tid": tenant_owned_tenant},
        )
    ).fetchone()
    assert row.retention_mode != "platform_blob"


async def test_platform_tenant_may_still_use_platform_blob_retention(
    db_session, platform_tenant
):
    """A `platform` tenant is unaffected by the new restriction."""
    await write_profile(db_session, platform_tenant, retention_mode="platform_blob")
    row = (
        await db_session.execute(
            text(
                "SELECT retention_mode FROM public.tenant_integration_profiles "
                "WHERE tenant_id = :tid"
            ),
            {"tid": platform_tenant},
        )
    ).fetchone()
    assert row.retention_mode == "platform_blob"


async def test_tenant_owned_may_use_ephemeral_or_source_only(db_session, tenant_owned_tenant):
    await write_profile(db_session, tenant_owned_tenant, retention_mode="ephemeral")
    row = (
        await db_session.execute(
            text(
                "SELECT retention_mode FROM public.tenant_integration_profiles "
                "WHERE tenant_id = :tid"
            ),
            {"tid": tenant_owned_tenant},
        )
    ).fetchone()
    assert row.retention_mode == "ephemeral"

    await write_profile(db_session, tenant_owned_tenant, retention_mode="source_only")
    row = (
        await db_session.execute(
            text(
                "SELECT retention_mode FROM public.tenant_integration_profiles "
                "WHERE tenant_id = :tid"
            ),
            {"tid": tenant_owned_tenant},
        )
    ).fetchone()
    assert row.retention_mode == "source_only"
