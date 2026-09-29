"""Entity type sensitivity classification: `open` / `pattern` / `local_only`.

Covers the `entity-sensitivity-classification` change's spec scenarios. `pattern` requires a
`validation_rule`; `local_only` requires no extra configuration; `sensitivity` is mutable
(unlike `provenance`) and defaults to `open` when omitted.
"""

import uuid

import pytest
from httpx import AsyncClient


def auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def tenant_admin_token():
    from src.shared.auth import create_access_token

    return create_access_token(tenant_id="test-tenant", user_id="admin-sens", role="tenant_admin")


def _unique_name(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


@pytest.mark.asyncio
class TestEntityTypeSensitivityClassification:
    async def test_new_entity_types_default_to_open(
        self, client: AsyncClient, setup_database, tenant_admin_token
    ):
        name = _unique_name("customer_name")
        resp = await client.post(
            "/api/v1/tenants/test-tenant/entity-types",
            json={"name": name},
            headers=auth_header(tenant_admin_token),
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["sensitivity"] == "open"

    async def test_pattern_with_a_validation_rule_is_accepted(
        self, client: AsyncClient, setup_database, tenant_admin_token
    ):
        name = _unique_name("ssn")
        resp = await client.post(
            "/api/v1/tenants/test-tenant/entity-types",
            json={
                "name": name,
                "sensitivity": "pattern",
                "validation_rule": r"^\d{3}-\d{2}-\d{4}$",
            },
            headers=auth_header(tenant_admin_token),
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["sensitivity"] == "pattern"

    async def test_pattern_without_a_validation_rule_is_rejected(
        self, client: AsyncClient, setup_database, tenant_admin_token
    ):
        name = _unique_name("ssn")
        resp = await client.post(
            "/api/v1/tenants/test-tenant/entity-types",
            json={"name": name, "sensitivity": "pattern"},
            headers=auth_header(tenant_admin_token),
        )
        assert resp.status_code == 422

        list_resp = await client.get(
            "/api/v1/tenants/test-tenant/entity-types", headers=auth_header(tenant_admin_token)
        )
        assert all(e["name"] != name for e in list_resp.json()["entity_types"])

    async def test_local_only_needs_no_extra_configuration(
        self, client: AsyncClient, setup_database, tenant_admin_token
    ):
        name = _unique_name("child_name")
        resp = await client.post(
            "/api/v1/tenants/test-tenant/entity-types",
            json={"name": name, "sensitivity": "local_only"},
            headers=auth_header(tenant_admin_token),
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["sensitivity"] == "local_only"

    async def test_unsupported_sensitivity_is_rejected(
        self, client: AsyncClient, setup_database, tenant_admin_token
    ):
        name = _unique_name("custom_type")
        resp = await client.post(
            "/api/v1/tenants/test-tenant/entity-types",
            json={"name": name, "sensitivity": "confidential"},
            headers=auth_header(tenant_admin_token),
        )
        assert resp.status_code == 422

    async def test_sensitivity_is_mutable_on_update(
        self, client: AsyncClient, setup_database, tenant_admin_token
    ):
        name = _unique_name("case_number")
        create_resp = await client.post(
            "/api/v1/tenants/test-tenant/entity-types",
            json={"name": name},
            headers=auth_header(tenant_admin_token),
        )
        assert create_resp.status_code == 201
        assert create_resp.json()["sensitivity"] == "open"

        update_resp = await client.put(
            f"/api/v1/tenants/test-tenant/entity-types/{name}",
            json={"sensitivity": "local_only"},
            headers=auth_header(tenant_admin_token),
        )
        assert update_resp.status_code == 200, update_resp.text
        updated = update_resp.json()
        assert updated["sensitivity"] == "local_only"
        assert updated["version"] == 2

    async def test_update_to_pattern_without_a_validation_rule_is_rejected(
        self, client: AsyncClient, setup_database, tenant_admin_token
    ):
        """The resolved-value check: a PUT that sends only `sensitivity` must still be
        validated against whatever `validation_rule` the type already has (here, none)."""
        name = _unique_name("passport_number")
        create_resp = await client.post(
            "/api/v1/tenants/test-tenant/entity-types",
            json={"name": name},
            headers=auth_header(tenant_admin_token),
        )
        assert create_resp.status_code == 201

        update_resp = await client.put(
            f"/api/v1/tenants/test-tenant/entity-types/{name}",
            json={"sensitivity": "pattern"},
            headers=auth_header(tenant_admin_token),
        )
        assert update_resp.status_code == 422

    async def test_existing_entity_types_backfill_to_open(
        self, client: AsyncClient, setup_database, tenant_admin_token, engine
    ):
        from sqlalchemy import text as sa_text

        name = _unique_name("legacy_type")
        async with engine.begin() as conn:
            await conn.execute(
                sa_text(
                    "INSERT INTO public.entity_definitions "
                    "(id, tenant_id, name, description, version, required_flag, is_active) "
                    "VALUES (:id, :tid, :name, 'pre-existing', 1, false, true)"
                ),
                {"id": str(uuid.uuid4()), "tid": "test-tenant", "name": name},
            )

        resp = await client.get(
            f"/api/v1/tenants/test-tenant/entity-types/{name}",
            headers=auth_header(tenant_admin_token),
        )
        assert resp.status_code == 200
        assert resp.json()["sensitivity"] == "open"
