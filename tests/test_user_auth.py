import pytest
from httpx import AsyncClient
from jose import jwt

from src.shared.auth import create_access_token
from src.shared.config import settings


def auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


_auth_counter = 0


@pytest.fixture
async def seeded_tenant_and_user(client: AsyncClient):
    global _auth_counter
    _auth_counter += 1
    sys_token = create_access_token(
        tenant_id="00000000-0000-0000-0000-000000000000",
        user_id="admin-001",
        role="system_admin",
    )
    slug = f"auth-test-{_auth_counter}"
    resp = await client.post("/api/v1/admin/tenants", json={
        "name": f"Auth Test Tenant {_auth_counter}", "slug": slug,
    }, headers=auth_header(sys_token))
    assert resp.status_code == 201
    tid = resp.json()["tenant"]["id"]

    ta_token = create_access_token(tenant_id=tid, user_id=f"ta-{_auth_counter}", role="tenant_admin")
    email = f"user{_auth_counter}@authtest.local"
    user_resp = await client.post(f"/api/v1/tenants/{slug}/users", json={
        "email": email,
        "password": "StrongPass1",
        "role": "annotator",
    }, headers=auth_header(ta_token))
    assert user_resp.status_code == 201
    uid = user_resp.json()["user"]["id"]

    return {"tid": tid, "uid": uid, "email": email, "password": "StrongPass1", "slug": slug}


# --- Scenario 6: Login with valid credentials ---
@pytest.mark.asyncio
async def test_scenario_6_login_valid(client: AsyncClient, seeded_tenant_and_user):
    tenant = seeded_tenant_and_user
    resp = await client.post("/api/v1/auth/login", json={
        "email": tenant["email"],
        "password": tenant["password"],
    })
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data

    payload = jwt.decode(data["access_token"], settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    assert payload["tenant_id"] == tenant["tid"]
    assert payload["role"] == "annotator"


# --- Scenario 7: Login with wrong password ---
@pytest.mark.asyncio
async def test_scenario_7_login_wrong_password(client: AsyncClient, seeded_tenant_and_user):
    tenant = seeded_tenant_and_user
    resp = await client.post("/api/v1/auth/login", json={
        "email": tenant["email"],
        "password": "WrongPassword1",
    })
    assert resp.status_code == 401, f"Expected 401, got {resp.status_code}: {resp.text}"


# --- Scenario 8: Expired token ---
@pytest.mark.asyncio
async def test_scenario_8_expired_token(client: AsyncClient, seeded_tenant_and_user):
    from datetime import datetime, timedelta, timezone
    expired_token = jwt.encode(
        {
            "sub": f"{seeded_tenant_and_user['tid']}:test",
            "tenant_id": seeded_tenant_and_user["tid"],
            "user_id": "test",
            "role": "annotator",
            "iat": datetime.now(timezone.utc) - timedelta(hours=2),
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),
            "type": "access",
        },
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    resp = await client.get(
        "/api/v1/entity-types",
        headers=auth_header(expired_token),
    )
    assert resp.status_code == 401, f"Expected 401, got {resp.status_code}: {resp.text}"


# --- Scenario 9: Tenant Admin creates user in own tenant (via scoped route, not admin) ---
@pytest.mark.asyncio
async def test_scenario_9_create_user_own_tenant(client: AsyncClient):
    sys_token = create_access_token(
        tenant_id="00000000-0000-0000-0000-000000000000",
        user_id="admin-002",
        role="system_admin",
    )
    resp = await client.post("/api/v1/admin/tenants", json={
        "name": "User Mgmt Tenant", "slug": "user-mgmt",
    }, headers=auth_header(sys_token))
    assert resp.status_code == 201
    tid = resp.json()["tenant"]["id"]
    slug = resp.json()["tenant"]["slug"]

    ta_token = create_access_token(tenant_id=tid, user_id="ta-002", role="tenant_admin")
    user_resp = await client.post(f"/api/v1/tenants/{slug}/users", json={
        "email": "newuser@usermgmt.local",
        "password": "StrongPass1",
        "role": "annotator",
    }, headers=auth_header(ta_token))
    assert user_resp.status_code == 201, f"Expected 201, got {user_resp.status_code}: {user_resp.text}"
    user_data = user_resp.json()["user"]
    assert user_data["role"] == "annotator"


# --- Scenario 10: Cross-tenant user creation blocked ---
@pytest.mark.asyncio
async def test_scenario_10_cross_tenant_blocked(client: AsyncClient):
    sys_token = create_access_token(
        tenant_id="00000000-0000-0000-0000-000000000000",
        user_id="admin-003",
        role="system_admin",
    )
    resp_a = await client.post("/api/v1/admin/tenants", json={
        "name": "Tenant A Cross", "slug": "tenant-a-cross",
    }, headers=auth_header(sys_token))
    assert resp_a.status_code == 201
    tid_a = resp_a.json()["tenant"]["id"]

    resp_b = await client.post("/api/v1/admin/tenants", json={
        "name": "Tenant B Cross", "slug": "tenant-b-cross",
    }, headers=auth_header(sys_token))
    assert resp_b.status_code == 201
    slug_b = resp_b.json()["tenant"]["slug"]

    user_token_a = create_access_token(tenant_id=tid_a, user_id="user-a-cross", role="tenant_admin")

    cross_resp = await client.post(
        f"/api/v1/tenants/{slug_b}/users",
        json={"email": "cross@test.local", "password": "StrongPass1", "role": "annotator"},
        headers=auth_header(user_token_a),
    )
    assert cross_resp.status_code == 403, f"Expected 403, got {cross_resp.status_code}: {cross_resp.text}"


# --- Scenario 11: Valid request with matching token forwarded ---
# This is implicitly tested by all successful tenant-scoped requests above.
# Explicit test here:
@pytest.mark.asyncio
async def test_scenario_11_matching_token(client: AsyncClient):
    sys_token = create_access_token(
        tenant_id="00000000-0000-0000-0000-000000000000",
        user_id="admin-004",
        role="system_admin",
    )
    resp = await client.post("/api/v1/admin/tenants", json={
        "name": "Match Token Tenant", "slug": "match-token",
    }, headers=auth_header(sys_token))
    assert resp.status_code == 201
    tid = resp.json()["tenant"]["id"]

    user_token = create_access_token(tenant_id=tid, user_id="match-user", role="annotator")
    entity_resp = await client.get(
        "/api/v1/entity-types",
        headers=auth_header(user_token),
    )
    assert entity_resp.status_code == 200, f"Expected 200, got {entity_resp.status_code}"


# --- Scenario 12: Non-existent tenant returns 404 ---
@pytest.mark.asyncio
async def test_scenario_12_nonexistent_tenant(client: AsyncClient):
    user_token = create_access_token(
        tenant_id="ghost-tenant-id", user_id="ghost-user", role="annotator"
    )
    resp = await client.get(
        "/api/v1/entity-types",
        headers=auth_header(user_token),
    )
    assert resp.status_code == 404, f"Expected 404, got {resp.status_code}: {resp.text}"


# --- Scenario 13: System admin cannot access tenant-scoped entity-types ---
@pytest.mark.asyncio
async def test_scenario_13_system_admin_no_tenant(client: AsyncClient):
    sys_token = create_access_token(
        tenant_id="00000000-0000-0000-0000-000000000000",
        user_id="admin-005",
        role="system_admin",
    )
    resp = await client.get(
        "/api/v1/entity-types",
        headers=auth_header(sys_token),
    )
    assert resp.status_code == 404, f"Expected 404, got {resp.status_code}: {resp.text}"


# --- Tenant Admin user CRUD via tenant-scoped routes ---

@pytest.mark.asyncio
async def test_tenant_admin_creates_user_own_tenant(client: AsyncClient):
    sys_token = create_access_token(
        tenant_id="00000000-0000-0000-0000-000000000000",
        user_id="admin-ta-create",
        role="system_admin",
    )
    resp = await client.post("/api/v1/admin/tenants", json={
        "name": "TA Create Tenant", "slug": "ta-create",
    }, headers=auth_header(sys_token))
    assert resp.status_code == 201
    tid = resp.json()["tenant"]["id"]
    slug = resp.json()["tenant"]["slug"]

    ta_token = create_access_token(tenant_id=tid, user_id="ta-user", role="tenant_admin")
    user_resp = await client.post(
        f"/api/v1/tenants/{slug}/users",
        json={"email": "newuser@ta-create.local", "password": "StrongPass1", "role": "annotator"},
        headers=auth_header(ta_token),
    )
    assert user_resp.status_code == 201, f"Expected 201, got {user_resp.status_code}: {user_resp.text}"
    user_data = user_resp.json()["user"]
    assert user_data["role"] == "annotator"
    assert user_data["status"] == "active"


@pytest.mark.asyncio
async def test_tenant_admin_lists_users(client: AsyncClient):
    sys_token = create_access_token(
        tenant_id="00000000-0000-0000-0000-000000000000",
        user_id="admin-ta-list",
        role="system_admin",
    )
    resp = await client.post("/api/v1/admin/tenants", json={
        "name": "TA List Tenant", "slug": "ta-list",
    }, headers=auth_header(sys_token))
    assert resp.status_code == 201
    tid = resp.json()["tenant"]["id"]
    slug = resp.json()["tenant"]["slug"]

    ta_token = create_access_token(tenant_id=tid, user_id="ta-user", role="tenant_admin")
    await client.post(f"/api/v1/tenants/{slug}/users", json={
        "email": "existing@ta-list.local", "password": "StrongPass1", "role": "annotator",
    }, headers=auth_header(ta_token))
    list_resp = await client.get(
        f"/api/v1/tenants/{slug}/users",
        headers=auth_header(ta_token),
    )
    assert list_resp.status_code == 200, f"Expected 200, got {list_resp.status_code}: {list_resp.text}"
    data = list_resp.json()
    assert "users" in data


@pytest.mark.asyncio
async def test_tenant_admin_gets_user(client: AsyncClient):
    sys_token = create_access_token(
        tenant_id="00000000-0000-0000-0000-000000000000",
        user_id="admin-ta-get",
        role="system_admin",
    )
    resp = await client.post("/api/v1/admin/tenants", json={
        "name": "TA Get Tenant", "slug": "ta-get",
    }, headers=auth_header(sys_token))
    assert resp.status_code == 201
    tid = resp.json()["tenant"]["id"]
    slug = resp.json()["tenant"]["slug"]

    ta_token = create_access_token(tenant_id=tid, user_id="ta-user", role="tenant_admin")
    user_resp = await client.post(f"/api/v1/tenants/{slug}/users", json={
        "email": "target@ta-get.local", "password": "StrongPass1", "role": "business_user",
    }, headers=auth_header(ta_token))
    assert user_resp.status_code == 201
    uid = user_resp.json()["user"]["id"]
    get_resp = await client.get(
        f"/api/v1/tenants/{slug}/users/{uid}",
        headers=auth_header(ta_token),
    )
    assert get_resp.status_code == 200, f"Expected 200, got {get_resp.status_code}: {get_resp.text}"
    assert get_resp.json()["user"]["email"] == "target@ta-get.local"


@pytest.mark.asyncio
async def test_tenant_admin_updates_user(client: AsyncClient):
    sys_token = create_access_token(
        tenant_id="00000000-0000-0000-0000-000000000000",
        user_id="admin-ta-upd",
        role="system_admin",
    )
    resp = await client.post("/api/v1/admin/tenants", json={
        "name": "TA Update Tenant", "slug": "ta-upd",
    }, headers=auth_header(sys_token))
    assert resp.status_code == 201
    tid = resp.json()["tenant"]["id"]
    slug = resp.json()["tenant"]["slug"]

    ta_token = create_access_token(tenant_id=tid, user_id="ta-user", role="tenant_admin")
    user_resp = await client.post(f"/api/v1/tenants/{slug}/users", json={
        "email": "updatable@ta-upd.local", "password": "StrongPass1", "role": "annotator",
    }, headers=auth_header(ta_token))
    assert user_resp.status_code == 201
    uid = user_resp.json()["user"]["id"]
    upd_resp = await client.put(
        f"/api/v1/tenants/{slug}/users/{uid}",
        json={"role": "business_user"},
        headers=auth_header(ta_token),
    )
    assert upd_resp.status_code == 200, f"Expected 200, got {upd_resp.status_code}: {upd_resp.text}"
    assert upd_resp.json()["user"]["role"] == "business_user"


@pytest.mark.asyncio
async def test_tenant_admin_deactivates_user(client: AsyncClient):
    sys_token = create_access_token(
        tenant_id="00000000-0000-0000-0000-000000000000",
        user_id="admin-ta-deact",
        role="system_admin",
    )
    resp = await client.post("/api/v1/admin/tenants", json={
        "name": "TA Deactivate Tenant", "slug": "ta-deact",
    }, headers=auth_header(sys_token))
    assert resp.status_code == 201
    tid = resp.json()["tenant"]["id"]
    slug = resp.json()["tenant"]["slug"]

    ta_token = create_access_token(tenant_id=tid, user_id="ta-user", role="tenant_admin")
    user_resp = await client.post(f"/api/v1/tenants/{slug}/users", json={
        "email": "deactivable@ta-deact.local", "password": "StrongPass1", "role": "annotator",
    }, headers=auth_header(ta_token))
    assert user_resp.status_code == 201
    uid = user_resp.json()["user"]["id"]
    deact_resp = await client.delete(
        f"/api/v1/tenants/{slug}/users/{uid}",
        headers=auth_header(ta_token),
    )
    assert deact_resp.status_code == 200, f"Expected 200, got {deact_resp.status_code}: {deact_resp.text}"
    assert deact_resp.json()["user"]["status"] == "inactive"


@pytest.mark.asyncio
async def test_non_admin_role_cannot_create_users(client: AsyncClient):
    sys_token = create_access_token(
        tenant_id="00000000-0000-0000-0000-000000000000",
        user_id="admin-role-enf",
        role="system_admin",
    )
    resp = await client.post("/api/v1/admin/tenants", json={
        "name": "Role Enforce Tenant", "slug": "role-enf",
    }, headers=auth_header(sys_token))
    assert resp.status_code == 201
    tid = resp.json()["tenant"]["id"]
    slug = resp.json()["tenant"]["slug"]

    annotator_token = create_access_token(tenant_id=tid, user_id="anno-user", role="annotator")
    create_resp = await client.post(
        f"/api/v1/tenants/{slug}/users",
        json={"email": "shouldnot@role-enf.local", "password": "StrongPass1", "role": "annotator"},
        headers=auth_header(annotator_token),
    )
    assert create_resp.status_code == 403, f"Expected 403, got {create_resp.status_code}: {create_resp.text}"
