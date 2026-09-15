"""Verification for tenant creation with `data_plane_mode` (ADR-017, task 9.3) —
tenant-provisioning spec scenarios: a `tenant_owned` tenant is created with no
platform schema and `awaiting_store` status, and an invalid mode is rejected.
"""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from src.shared.auth import create_access_token

SYSTEM_ADMIN_TOKEN = create_access_token(
    tenant_id="00000000-0000-0000-0000-000000000000",
    user_id="admin-001",
    role="system_admin",
)


def auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_system_admin_creates_a_tenant_owned_data_plane_tenant(client: AsyncClient, engine):
    """Scenario: System Admin creates a tenant-owned data plane tenant."""
    slug = f"contoso-{uuid.uuid4().hex[:8]}"
    payload = {
        "name": "Contoso",
        "slug": slug,
        "admin_email": f"admin@{slug}.io",
        "admin_password": "ContosoAdmin1",
        "data_plane_mode": "tenant_owned",
    }
    resp = await client.post("/api/v1/admin/tenants", json=payload, headers=auth_header(SYSTEM_ADMIN_TOKEN))
    assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.text}"
    data = resp.json()
    tenant = data.get("tenant", data)
    assert tenant["data_plane"] == {"mode": "tenant_owned", "status": "awaiting_store", "health": None}
    tenant_id = tenant["id"]

    schema_name = f"tenant_{tenant_id}".replace("-", "_")
    async with engine.connect() as conn:
        schemas = await conn.execute(
            text("SELECT schema_name FROM information_schema.schemata WHERE schema_name = :s"),
            {"s": schema_name},
        )
        assert schemas.fetchone() is None, f"Schema {schema_name} should not exist"

        profile = (
            await conn.execute(
                text(
                    "SELECT relational_adapter, index_adapter, retention_mode "
                    "FROM public.tenant_integration_profiles WHERE tenant_id = :id"
                ),
                {"id": tenant_id},
            )
        ).fetchone()
        assert profile.relational_adapter == "tenant_postgresql"
        assert profile.index_adapter == "tenant_pgvector"
        assert profile.retention_mode == "ephemeral"

        admin_row = (
            await conn.execute(
                text("SELECT id FROM public.tenant_users WHERE tenant_id = :id AND role = 'tenant_admin'"),
                {"id": tenant_id},
            )
        ).fetchone()
        assert admin_row is not None, "tenant admin SHALL be created even without a platform schema"


@pytest.mark.asyncio
async def test_invalid_data_plane_mode_is_rejected(client: AsyncClient, engine):
    """Scenario: Invalid data plane mode is rejected."""
    slug = f"invalid-dp-{uuid.uuid4().hex[:8]}"
    payload = {
        "name": "Invalid DP",
        "slug": slug,
        "admin_email": f"admin@{slug}.io",
        "admin_password": "InvalidAdmin1",
        "data_plane_mode": "hybrid",
    }
    resp = await client.post("/api/v1/admin/tenants", json=payload, headers=auth_header(SYSTEM_ADMIN_TOKEN))
    assert resp.status_code == 422

    async with engine.connect() as conn:
        row = (
            await conn.execute(
                text("SELECT 1 FROM public.tenants WHERE slug = :s"), {"s": slug}
            )
        ).fetchone()
        assert row is None


@pytest.mark.asyncio
async def test_tenant_owned_disabled_by_feature_flag(client: AsyncClient, engine, monkeypatch):
    """Feature-flag gating: creating a tenant_owned tenant is rejected when disabled."""
    from src.shared.config import settings

    monkeypatch.setattr(settings, "tenant_owned_data_plane_enabled", False)
    slug = f"flagged-{uuid.uuid4().hex[:8]}"
    payload = {
        "name": "Flagged",
        "slug": slug,
        "admin_email": f"admin@{slug}.io",
        "admin_password": "FlaggedAdmin1",
        "data_plane_mode": "tenant_owned",
    }
    resp = await client.post("/api/v1/admin/tenants", json=payload, headers=auth_header(SYSTEM_ADMIN_TOKEN))
    assert resp.status_code in (400, 422)

    async with engine.connect() as conn:
        row = (
            await conn.execute(
                text("SELECT 1 FROM public.tenants WHERE slug = :s"), {"s": slug}
            )
        ).fetchone()
        assert row is None
