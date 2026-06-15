import pytest
from httpx import AsyncClient

from src.shared.auth import create_access_token


def auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


SYSTEM_ADMIN_TOKEN = create_access_token(
    tenant_id="00000000-0000-0000-0000-000000000000",
    user_id="admin-entity",
    role="system_admin",
)


_entity_counter = 0


@pytest.fixture
async def tenant_with_token(client: AsyncClient):
    global _entity_counter
    _entity_counter += 1
    slug = f"entity-config-{_entity_counter}"
    resp = await client.post("/api/v1/admin/tenants", json={
        "name": f"Entity Config Tenant {_entity_counter}", "slug": slug,
    }, headers=auth_header(SYSTEM_ADMIN_TOKEN))
    assert resp.status_code == 201
    tid = resp.json()["tenant"]["id"]

    token = create_access_token(tenant_id=tid, user_id=f"admin-{_entity_counter}", role="tenant_admin")
    return {"tid": tid, "token": token, "slug": slug}


# --- Scenario 14: Create entity type with version: 1 ---
@pytest.mark.asyncio
async def test_scenario_14_create_entity_type_v1(client: AsyncClient, tenant_with_token):
    tenant = tenant_with_token
    resp = await client.post(
        "/api/v1/entity-types",
        json={
            "name": "Organization",
            "description": "Company or organization names",
            "base_label_mapping": {"ORG": ["company_name", "organization_name"]},
            "required_flag": False,
        },
        headers=auth_header(tenant["token"]),
    )
    assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.text}"
    entity = resp.json()["entity_type"]
    assert entity["version"] == 1, f"Expected version 1, got {entity['version']}"


# --- Scenario 15: Update entity type increments version ---
@pytest.mark.asyncio
async def test_scenario_15_update_increments_version(client: AsyncClient, tenant_with_token):
    tenant = tenant_with_token
    resp = await client.post(
        "/api/v1/entity-types",
        json={"name": "Person", "base_label_mapping": {"PER": ["person_name"]}},
        headers=auth_header(tenant["token"]),
    )
    assert resp.status_code == 201
    entity_id = resp.json()["entity_type"]["id"]

    update_resp = await client.put(
        f"/api/v1/entity-types/{entity_id}",
        json={"description": "Updated description"},
        headers=auth_header(tenant["token"]),
    )
    assert update_resp.status_code == 200
    updated = update_resp.json()["entity_type"]
    assert updated["version"] == 2, f"Expected version 2, got {updated['version']}"


# --- Scenario 16: Valid base_label_mapping accepted ---
@pytest.mark.asyncio
async def test_scenario_16_valid_label_mapping(client: AsyncClient, tenant_with_token):
    tenant = tenant_with_token
    resp = await client.post(
        "/api/v1/entity-types",
        json={
            "name": "Location Entity",
            "base_label_mapping": {
                "LOC": ["city_name", "country_name"],
                "ORG": ["vendor_name"],
            },
        },
        headers=auth_header(tenant["token"]),
    )
    assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.text}"
    entity = resp.json()["entity_type"]
    assert "LOC" in entity["base_label_mapping"]
    assert "ORG" in entity["base_label_mapping"]


# --- Scenario 17: Invalid label returns 422 ---
@pytest.mark.asyncio
async def test_scenario_17_invalid_label_422(client: AsyncClient, tenant_with_token):
    tenant = tenant_with_token
    resp = await client.post(
        "/api/v1/entity-types",
        json={
            "name": "Bad Entity",
            "base_label_mapping": {"INVALID_LABEL": ["something"]},
        },
        headers=auth_header(tenant["token"]),
    )
    assert resp.status_code == 422, f"Expected 422, got {resp.status_code}: {resp.text}"


# --- Scenario 18: List all entity types with is_active ---
@pytest.mark.asyncio
async def test_scenario_18_list_all_entity_types(client: AsyncClient, tenant_with_token):
    tenant = tenant_with_token
    for name, label in [("Type A", "PER"), ("Type B", "ORG"), ("Type C", "LOC"),
                          ("Type D", "MISC"), ("Type E", "PER")]:
        await client.post(
            "/api/v1/entity-types",
            json={"name": name, "base_label_mapping": {label: ["test"]}},
            headers=auth_header(tenant["token"]),
        )

    resp = await client.get(
        "/api/v1/entity-types",
        headers=auth_header(tenant["token"]),
    )
    assert resp.status_code == 200
    types = resp.json()["entity_types"]
    assert len(types) >= 5
    for t in types:
        assert "is_active" in t


# --- Scenario 19: Filter active only ---
@pytest.mark.asyncio
async def test_scenario_19_filter_active(client: AsyncClient, tenant_with_token):
    tenant = tenant_with_token
    resp = await client.get(
        "/api/v1/entity-types?is_active=true",
        headers=auth_header(tenant["token"]),
    )
    assert resp.status_code == 200
    types = resp.json()["entity_types"]
    for t in types:
        assert t["is_active"] is True
