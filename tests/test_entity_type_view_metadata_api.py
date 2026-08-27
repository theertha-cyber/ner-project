"""`cardinality` and `sql_identifier` reachable end to end through the entity-type API.

Both columns have existed since migration `037`, and until this change neither was reachable
from anywhere: `sql_identifier` was absent from the create INSERT (so every entity type created
after `037` carried NULL and was silently skipped by the reconciler and the projection), and
`cardinality` was absent from the INSERT, from `update_entity_type`'s allowed fields, from both
SELECT lists, and from `_row_to_dict`. An entity type that is absent from the relational
surface still extracts into `document_entities` normally, so the failure has no symptom other
than an empty table.

The tenant is inserted directly rather than through `POST /api/v1/admin/tenants`: that endpoint
returns 422 on `main` (a pre-existing failure, see the baseline), and these assertions are
about the entity-type API rather than about tenant provisioning.

Covers verification.md rows 102-113, 117, 118.
"""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from src.shared.auth import create_access_token

pytestmark = pytest.mark.asyncio


@pytest.fixture
async def tenant(client: AsyncClient, engine):
    tid = f"etm-{uuid.uuid4().hex[:8]}"
    schema = f"tenant_{tid.replace('-', '_')}"
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO public.tenants (id, name, slug, status, max_users, max_documents, "
                "max_storage_gb, max_model_versions) "
                "VALUES (:id, :id, :id, 'active', 10, 1000, 5, 10) ON CONFLICT (id) DO NOTHING"
            ),
            {"id": tid},
        )
        await conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema}"'))

    token = create_access_token(tenant_id=tid, user_id="admin", role="tenant_admin")
    yield {
        "id": tid,
        "slug": tid,
        "headers": {"Authorization": f"Bearer {token}"},
        "url": f"/api/v1/tenants/{tid}/entity-types",
    }

    async with engine.begin() as conn:
        await conn.execute(
            text("DELETE FROM public.entity_definitions WHERE tenant_id = :id"), {"id": tid}
        )
        await conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        await conn.execute(text("DELETE FROM public.tenants WHERE id = :id"), {"id": tid})


async def _create(client, tenant, name, **fields):
    return await client.post(
        tenant["url"], json={"name": name, **fields}, headers=tenant["headers"]
    )


class TestSqlIdentifierAssignment:
    """verification.md rows 102, 103, 105"""

    async def test_a_new_entity_type_gets_an_identifier(self, client, tenant):
        resp = await _create(client, tenant, "Vendor Name")
        assert resp.status_code == 201
        assert resp.json()["sql_identifier"] == "e_vendor_name"

    async def test_the_identifier_is_unique_within_the_tenant(self, client, tenant):
        first = await _create(client, tenant, "Vendor Name")
        second = await _create(client, tenant, "vendor-name")
        assert first.status_code == 201 and second.status_code == 201
        # Both names slug to the same base; the partial unique index on
        # (tenant_id, sql_identifier) must not be violated.
        assert first.json()["sql_identifier"] == "e_vendor_name"
        assert second.json()["sql_identifier"] == "e_vendor_name_2"

    async def test_the_identifier_survives_every_write_path(self, client, tenant):
        created = await _create(client, tenant, "Vendor Name")
        identifier = created.json()["sql_identifier"]

        updated = await client.put(
            f"{tenant['url']}/Vendor Name",
            json={"description": "changed"},
            headers=tenant["headers"],
        )
        assert updated.json()["sql_identifier"] == identifier

        toggled = await client.patch(
            f"{tenant['url']}/Vendor Name",
            json={"is_active": False},
            headers=tenant["headers"],
        )
        assert toggled.json()["sql_identifier"] == identifier

        deleted = await client.delete(
            f"{tenant['url']}/Vendor Name", headers=tenant["headers"]
        )
        assert deleted.json()["sql_identifier"] == identifier

    async def test_the_slug_rule_is_imported_not_reimplemented(self):
        import inspect

        from src.gateway.services import entity_service

        source = inspect.getsource(entity_service)
        # A second copy of the slug rule would drift from the one migration `037` used, and
        # the migration would then record identifiers for tables the generator never creates.
        assert "from src.shared.entity_views import" in source
        assert "to_sql_identifier" in source
        assert "def to_sql_identifier" not in source


class TestCardinality:
    """verification.md rows 106, 107, 108, 109"""

    async def test_create_with_single_persists_single(self, client, tenant):
        resp = await _create(client, tenant, "Candidate Email", cardinality="single")
        assert resp.status_code == 201
        assert resp.json()["cardinality"] == "single"

    async def test_create_without_cardinality_defaults_to_multi(self, client, tenant):
        # `multi` is the safe default: a multi-valued entity rendered as a child table is
        # merely one extra join, whereas one wrongly marked `single` silently discards every
        # value but the selected one from the query surface.
        resp = await _create(client, tenant, "Skill")
        assert resp.json()["cardinality"] == "multi"

    async def test_update_changes_cardinality_and_increments_version(self, client, tenant):
        created = await _create(client, tenant, "Skill")
        resp = await client.put(
            f"{tenant['url']}/Skill", json={"cardinality": "single"}, headers=tenant["headers"]
        )
        assert resp.status_code == 200
        assert resp.json()["cardinality"] == "single"
        assert resp.json()["version"] == created.json()["version"] + 1

    @pytest.mark.parametrize("bad", ["many", "SINGLE", "", "one"])
    async def test_an_invalid_cardinality_is_422_not_500(self, client, tenant, bad):
        resp = await _create(client, tenant, "Skill", cardinality=bad)
        assert resp.status_code == 422
        body = resp.text
        assert "single" in body and "multi" in body

    async def test_an_invalid_cardinality_on_update_is_422_and_writes_nothing(
        self, client, tenant
    ):
        await _create(client, tenant, "Skill")
        resp = await client.put(
            f"{tenant['url']}/Skill", json={"cardinality": "many"}, headers=tenant["headers"]
        )
        assert resp.status_code == 422

        unchanged = await client.get(f"{tenant['url']}/Skill", headers=tenant["headers"])
        assert unchanged.json()["cardinality"] == "multi"
        assert unchanged.json()["version"] == 1


class TestReadPathsCarryBothFields:
    """verification.md rows 110, 111, 112"""

    async def test_list_carries_both(self, client, tenant):
        await _create(client, tenant, "Skill")
        resp = await client.get(tenant["url"], headers=tenant["headers"])
        assert resp.status_code == 200
        for entry in resp.json()["entity_types"]:
            assert "cardinality" in entry and "sql_identifier" in entry

    async def test_get_by_name_carries_both(self, client, tenant):
        await _create(client, tenant, "Skill", cardinality="single")
        resp = await client.get(f"{tenant['url']}/Skill", headers=tenant["headers"])
        assert resp.json()["cardinality"] == "single"
        assert resp.json()["sql_identifier"] == "e_skill"

    async def test_create_and_update_responses_carry_both(self, client, tenant):
        created = await _create(client, tenant, "Skill")
        assert {"cardinality", "sql_identifier"} <= set(created.json())

        updated = await client.put(
            f"{tenant['url']}/Skill", json={"description": "x"}, headers=tenant["headers"]
        )
        assert {"cardinality", "sql_identifier"} <= set(updated.json())


class TestClientSuppliedIdentifierIsIgnored:
    """verification.md row 113"""

    async def test_create_ignores_a_supplied_identifier(self, client, tenant):
        resp = await _create(client, tenant, "Skill", sql_identifier="e_injected")
        assert resp.status_code == 201
        assert resp.json()["sql_identifier"] == "e_skill"

    async def test_update_ignores_a_supplied_identifier(self, client, tenant):
        await _create(client, tenant, "Skill")
        resp = await client.put(
            f"{tenant['url']}/Skill",
            json={"sql_identifier": "e_injected", "description": "x"},
            headers=tenant["headers"],
        )
        assert resp.json()["sql_identifier"] == "e_skill"


class TestTypedRequestSchemas:
    """verification.md rows 117, 118"""

    async def test_a_create_without_a_name_is_422(self, client, tenant):
        resp = await client.post(tenant["url"], json={"description": "x"}, headers=tenant["headers"])
        assert resp.status_code == 422

    async def test_a_toggle_without_is_active_is_422_not_500(self, client, tenant):
        await _create(client, tenant, "Skill")
        resp = await client.patch(
            f"{tenant['url']}/Skill", json={}, headers=tenant["headers"]
        )
        # Reading `payload["is_active"]` off an untyped dict raised KeyError here, which the
        # error handler surfaced as a 500 for a plainly malformed request.
        assert resp.status_code == 422

    async def test_a_toggle_with_is_active_still_works(self, client, tenant):
        await _create(client, tenant, "Skill")
        resp = await client.patch(
            f"{tenant['url']}/Skill", json={"is_active": False}, headers=tenant["headers"]
        )
        assert resp.status_code == 200
        assert resp.json()["is_active"] is False

    async def test_an_update_omitting_a_field_leaves_it_alone(self, client, tenant):
        await _create(client, tenant, "Skill", description="original", value_unit="years")
        resp = await client.put(
            f"{tenant['url']}/Skill", json={"description": "changed"}, headers=tenant["headers"]
        )
        assert resp.json()["description"] == "changed"
        # An optional field absent from the body must not be written as NULL.
        assert resp.json()["value_unit"] == "years"
