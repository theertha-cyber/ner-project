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


# --- Scenario 1: Tenant creation with valid data ---
@pytest.mark.asyncio
async def test_scenario_1_create_tenant_201(client: AsyncClient, engine):
    payload = {
        "name": "Acme Corp",
        "slug": "acme-corp",
        "max_users": 10,
        "max_documents": 1000,
        "max_storage_gb": 5,
        "max_model_versions": 10,
    }
    resp = await client.post("/api/v1/admin/tenants", json=payload, headers=auth_header(SYSTEM_ADMIN_TOKEN))
    assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.text}"
    data = resp.json()
    tenant = data.get("tenant", data)
    assert tenant.get("status") == "active", f"Expected active, got {tenant.get('status')}"
    tenant_id = tenant["id"]

    schema_name = f"tenant_{tenant_id}".replace("-", "_")
    async with engine.connect() as conn:
        schemas = await conn.execute(
            text("SELECT schema_name FROM information_schema.schemata WHERE schema_name = :s"),
            {"s": schema_name},
        )
        assert schemas.fetchone() is not None, f"Schema {schema_name} does not exist"


# --- Scenario 2: Duplicate slug returns 409 ---
@pytest.mark.asyncio
async def test_scenario_2_duplicate_slug_409(client: AsyncClient):
    payload = {"name": "Acme Corp Dup", "slug": "duplicate-slug"}
    resp1 = await client.post("/api/v1/admin/tenants", json=payload, headers=auth_header(SYSTEM_ADMIN_TOKEN))
    assert resp1.status_code == 201
    resp2 = await client.post("/api/v1/admin/tenants", json=payload, headers=auth_header(SYSTEM_ADMIN_TOKEN))
    assert resp2.status_code == 409, f"Expected 409, got {resp2.status_code}: {resp2.text}"


# --- Scenario 3: Quota exceeded returns 429 ---
@pytest.mark.asyncio
async def test_scenario_3_quota_exceeded_429(client: AsyncClient):
    payload_tenant = {"name": "Quota Test", "slug": "quota-test", "max_users": 1}
    resp = await client.post("/api/v1/admin/tenants", json=payload_tenant, headers=auth_header(SYSTEM_ADMIN_TOKEN))
    assert resp.status_code == 201
    tid = resp.json()["tenant"]["id"]
    slug = resp.json()["tenant"]["slug"]

    ta_token = create_access_token(tenant_id=tid, user_id="quota-admin", role="tenant_admin")
    user_payload = {"email": "user1@quota.test", "password": "StrongPass1", "role": "annotator"}
    resp1 = await client.post(f"/api/v1/tenants/{slug}/users", json=user_payload, headers=auth_header(ta_token))
    assert resp1.status_code == 201

    user_payload2 = {"email": "user2@quota.test", "password": "StrongPass2", "role": "annotator"}
    resp2 = await client.post(f"/api/v1/tenants/{slug}/users", json=user_payload2, headers=auth_header(ta_token))
    assert resp2.status_code == 429, f"Expected 429, got {resp2.status_code}: {resp2.text}"


# --- Scenario 4: Paginated tenant list ---
@pytest.mark.asyncio
async def test_scenario_4_paginated_list(client: AsyncClient):
    for i in range(25):
        resp = await client.post("/api/v1/admin/tenants", json={
            "name": f"Tenant {i}", "slug": f"tenant-{i}"
        }, headers=auth_header(SYSTEM_ADMIN_TOKEN))
        assert resp.status_code == 201

    resp = await client.get("/api/v1/admin/tenants?page=1&per_page=10", headers=auth_header(SYSTEM_ADMIN_TOKEN))
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["tenants"]) <= 10
    assert data["total"] >= 25


# --- Scenario 5: Tenant deactivation ---
@pytest.mark.asyncio
async def test_scenario_5_deactivate_tenant(client: AsyncClient, engine):
    resp = await client.post("/api/v1/admin/tenants", json={
        "name": "Deactivate Test", "slug": "deactivate-test"
    }, headers=auth_header(SYSTEM_ADMIN_TOKEN))
    assert resp.status_code == 201
    tid = resp.json()["tenant"]["id"]

    deact_resp = await client.post(f"/api/v1/admin/tenants/{tid}/deactivate", headers=auth_header(SYSTEM_ADMIN_TOKEN))
    assert deact_resp.status_code == 200

    async with engine.connect() as conn:
        row = await conn.execute(text("SELECT status FROM public.tenants WHERE id = :id"), {"id": tid})
        status = row.scalar()
        assert status == "inactive", f"Expected inactive, got {status}"

    user_token = create_access_token(tenant_id=tid, user_id="test-user", role="annotator")
    entity_resp = await client.get(
        "/api/v1/entity-types",
        headers={"Authorization": f"Bearer {user_token}"}
    )
    assert entity_resp.status_code == 403, f"Expected 403, got {entity_resp.status_code}: {entity_resp.text}"
