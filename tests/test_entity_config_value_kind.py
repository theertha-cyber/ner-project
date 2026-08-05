import uuid

import pytest
from httpx import AsyncClient

from src.shared.auth import create_access_token


def auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def tenant_admin_token():
    return create_access_token(tenant_id="test-tenant", user_id="admin-vk", role="tenant_admin")


def _unique_name(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


@pytest.mark.asyncio
class TestEntityConfigValueKind:
    """Covers verification.md rows 29-33."""

    async def test_create_entity_type_defaults_value_kind_to_text(self, client: AsyncClient, setup_database, tenant_admin_token):
        name = _unique_name("customer_name")
        resp = await client.post(
            "/api/v1/tenants/test-tenant/entity-types",
            json={
                "name": name,
                "description": "Full name of a customer",
                "examples": ["John Smith", "Acme Corp"],
                "validation_rule": None,
                "required_flag": True,
            },
            headers=auth_header(tenant_admin_token),
        )
        assert resp.status_code == 201, resp.text
        entity = resp.json()
        assert entity["version"] == 1
        assert entity["is_active"] is True
        assert entity["value_kind"] == "text"

    async def test_update_entity_type_increments_version(self, client: AsyncClient, setup_database, tenant_admin_token):
        name = _unique_name("customer_name")
        create_resp = await client.post(
            "/api/v1/tenants/test-tenant/entity-types",
            json={"name": name},
            headers=auth_header(tenant_admin_token),
        )
        assert create_resp.status_code == 201

        update_resp = await client.put(
            f"/api/v1/tenants/test-tenant/entity-types/{name}",
            json={"description": "Updated description"},
            headers=auth_header(tenant_admin_token),
        )
        assert update_resp.status_code == 200
        updated = update_resp.json()
        assert updated["version"] == 2
        assert updated["description"] == "Updated description"

    async def test_declare_structured_value_kind(self, client: AsyncClient, setup_database, tenant_admin_token):
        name = _unique_name("YEARS_OF_EXP")
        resp = await client.post(
            "/api/v1/tenants/test-tenant/entity-types",
            json={"name": name, "value_kind": "duration", "value_unit": "years"},
            headers=auth_header(tenant_admin_token),
        )
        assert resp.status_code == 201, resp.text
        entity = resp.json()
        assert entity["value_kind"] == "duration"
        assert entity["value_unit"] == "years"

    async def test_unsupported_value_kind_rejected(self, client: AsyncClient, setup_database, tenant_admin_token):
        name = _unique_name("office_location")
        resp = await client.post(
            "/api/v1/tenants/test-tenant/entity-types",
            json={"name": name, "value_kind": "geo"},
            headers=auth_header(tenant_admin_token),
        )
        assert resp.status_code == 422

        list_resp = await client.get(
            "/api/v1/tenants/test-tenant/entity-types",
            headers=auth_header(tenant_admin_token),
        )
        assert all(e["name"] != name for e in list_resp.json()["entity_types"])

    async def test_existing_entity_types_default_to_text(self, client: AsyncClient, setup_database, tenant_admin_token, engine):
        from sqlalchemy import text as sa_text

        name = _unique_name("legacy_type")
        async with engine.begin() as conn:
            await conn.execute(
                sa_text(
                    "INSERT INTO public.entity_definitions (id, tenant_id, name, description, version, required_flag, is_active) "
                    "VALUES (:id, :tid, :name, 'pre-existing', 1, false, true)"
                ),
                {"id": str(uuid.uuid4()), "tid": "test-tenant", "name": name},
            )

        resp = await client.get(
            f"/api/v1/tenants/test-tenant/entity-types/{name}",
            headers=auth_header(tenant_admin_token),
        )
        assert resp.status_code == 200
        entity = resp.json()
        assert entity["value_kind"] == "text"
        assert entity["value_unit"] is None
