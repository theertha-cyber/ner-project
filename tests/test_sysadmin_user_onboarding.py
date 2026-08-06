import pytest
from httpx import AsyncClient
from sqlalchemy import text

from src.shared.auth import create_access_token

SYSTEM_ADMIN_TOKEN = create_access_token(
    tenant_id="system",
    user_id="platform-admin",
    role="system_admin",
    email="platform-admin@example.com",
)


def auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def create_tenant(client: AsyncClient, slug: str, max_users: int = 10) -> dict:
    resp = await client.post(
        "/api/v1/admin/tenants",
        json={
            "name": slug,
            "slug": slug,
            "max_users": max_users,
            "admin_email": f"admin@{slug}.io",
            "admin_password": "StrongPass1",
        },
        headers=auth_header(SYSTEM_ADMIN_TOKEN),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["tenant"]


def tenant_admin_token(tenant_id: str, email: str = "admin@acme.com") -> str:
    return create_access_token(tenant_id=tenant_id, user_id=email, role="tenant_admin", email=email)


# --- Scenario 1-3: System Admin creates each role in a specific tenant ---
@pytest.mark.asyncio
async def test_admin_creates_business_user_in_target_tenant(client: AsyncClient):
    tenant = await create_tenant(client, "sysadmin-biz")
    resp = await client.post(
        f"/api/v1/admin/tenants/{tenant['id']}/users",
        json={"email": "biz@sysadmin-biz.io", "password": "StrongPass1", "role": "business_user"},
        headers=auth_header(SYSTEM_ADMIN_TOKEN),
    )
    assert resp.status_code == 201, resp.text
    user = resp.json()["user"]
    assert user["email"] == "biz@sysadmin-biz.io"
    assert user["role"] == "business_user"
    assert user["status"] == "active"


@pytest.mark.asyncio
async def test_admin_creates_tenant_admin_in_target_tenant(client: AsyncClient):
    tenant = await create_tenant(client, "sysadmin-ta")
    resp = await client.post(
        f"/api/v1/admin/tenants/{tenant['id']}/users",
        json={"email": "admin2@sysadmin-ta.io", "password": "StrongPass1", "role": "tenant_admin"},
        headers=auth_header(SYSTEM_ADMIN_TOKEN),
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["user"]["role"] == "tenant_admin"


@pytest.mark.asyncio
async def test_admin_creates_annotator_in_target_tenant(client: AsyncClient):
    tenant = await create_tenant(client, "sysadmin-ann")
    resp = await client.post(
        f"/api/v1/admin/tenants/{tenant['id']}/users",
        json={"email": "ann@sysadmin-ann.io", "password": "StrongPass1", "role": "annotator"},
        headers=auth_header(SYSTEM_ADMIN_TOKEN),
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["user"]["role"] == "annotator"


# --- Scenario 4: nonexistent tenant ---
@pytest.mark.asyncio
async def test_admin_create_user_nonexistent_tenant_returns_404(client: AsyncClient):
    resp = await client.post(
        "/api/v1/admin/tenants/tid-ghost/users",
        json={"email": "ghost@example.io", "password": "StrongPass1", "role": "annotator"},
        headers=auth_header(SYSTEM_ADMIN_TOKEN),
    )
    assert resp.status_code == 404


# --- Scenario 5: quota exceeded ---
@pytest.mark.asyncio
async def test_admin_create_user_quota_exceeded_returns_429(client: AsyncClient):
    tenant = await create_tenant(client, "sysadmin-quota", max_users=1)
    resp = await client.post(
        f"/api/v1/admin/tenants/{tenant['id']}/users",
        json={"email": "over-quota@sysadmin-quota.io", "password": "StrongPass1", "role": "annotator"},
        headers=auth_header(SYSTEM_ADMIN_TOKEN),
    )
    assert resp.status_code == 429


# --- Scenario 6: duplicate email in same tenant ---
@pytest.mark.asyncio
async def test_admin_create_user_duplicate_email_in_tenant_returns_409(client: AsyncClient):
    tenant = await create_tenant(client, "sysadmin-dup")
    payload = {"email": "dup@sysadmin-dup.io", "password": "StrongPass1", "role": "annotator"}
    resp1 = await client.post(f"/api/v1/admin/tenants/{tenant['id']}/users", json=payload, headers=auth_header(SYSTEM_ADMIN_TOKEN))
    assert resp1.status_code == 201
    resp2 = await client.post(f"/api/v1/admin/tenants/{tenant['id']}/users", json=payload, headers=auth_header(SYSTEM_ADMIN_TOKEN))
    assert resp2.status_code == 409


# --- Scenario 7: non-system-admin rejected ---
@pytest.mark.asyncio
async def test_admin_create_user_rejects_non_system_admin_403(client: AsyncClient):
    tenant = await create_tenant(client, "sysadmin-forbidden")
    ta_token = tenant_admin_token(tenant["id"])
    resp = await client.post(
        f"/api/v1/admin/tenants/{tenant['id']}/users",
        json={"email": "sneaky@sysadmin-forbidden.io", "password": "StrongPass1", "role": "annotator"},
        headers=auth_header(ta_token),
    )
    assert resp.status_code == 403


# --- Scenario 8: unauthenticated ---
@pytest.mark.asyncio
async def test_admin_create_user_requires_auth_401(client: AsyncClient):
    resp = await client.post(
        "/api/v1/admin/tenants/tid-123/users",
        json={"email": "noauth@example.io", "password": "StrongPass1", "role": "annotator"},
    )
    assert resp.status_code == 401


# --- Scenario 9: inactive tenant ---
@pytest.mark.asyncio
async def test_admin_create_user_inactive_tenant_returns_403(client: AsyncClient):
    tenant = await create_tenant(client, "sysadmin-inactive")
    deact = await client.post(f"/api/v1/admin/tenants/{tenant['id']}/deactivate", headers=auth_header(SYSTEM_ADMIN_TOKEN))
    assert deact.status_code == 200

    resp = await client.post(
        f"/api/v1/admin/tenants/{tenant['id']}/users",
        json={"email": "late@sysadmin-inactive.io", "password": "StrongPass1", "role": "annotator"},
        headers=auth_header(SYSTEM_ADMIN_TOKEN),
    )
    assert resp.status_code == 403


# --- Scenario 10: tenant deactivated between form load and submission ---
@pytest.mark.asyncio
async def test_admin_create_user_tenant_deactivated_after_form_load_returns_403(client: AsyncClient):
    tenant = await create_tenant(client, "sysadmin-race")
    # simulate the System Admin having loaded the form while the tenant was active,
    # then the tenant being deactivated before the create request reaches the server
    deact = await client.post(f"/api/v1/admin/tenants/{tenant['id']}/deactivate", headers=auth_header(SYSTEM_ADMIN_TOKEN))
    assert deact.status_code == 200

    resp = await client.post(
        f"/api/v1/admin/tenants/{tenant['id']}/users",
        json={"email": "race@sysadmin-race.io", "password": "StrongPass1", "role": "annotator"},
        headers=auth_header(SYSTEM_ADMIN_TOKEN),
    )
    assert resp.status_code == 403


# --- Scenario 11-12: Tenant Admin path unchanged ---
@pytest.mark.asyncio
async def test_tenant_admin_create_user_still_scoped_to_own_tenant(client: AsyncClient):
    tenant = await create_tenant(client, "ta-own-tenant")
    ta_token = tenant_admin_token(tenant["id"])
    resp = await client.post(
        "/api/v1/users",
        json={"email": "user@ta-own-tenant.io", "password": "StrongPass1", "role": "annotator"},
        headers=auth_header(ta_token),
    )
    assert resp.status_code == 201, resp.text

    row = await client.get(f"/api/v1/admin/tenants/{tenant['id']}/users", headers=auth_header(SYSTEM_ADMIN_TOKEN))
    emails = [u["email"] for u in row.json()["users"]]
    assert "user@ta-own-tenant.io" in emails


@pytest.mark.asyncio
async def test_tenant_admin_create_user_ignores_foreign_tenant_field(client: AsyncClient):
    tenant = await create_tenant(client, "ta-ignore-foreign")
    other_tenant = await create_tenant(client, "ta-other-tenant")
    ta_token = tenant_admin_token(tenant["id"])

    resp = await client.post(
        "/api/v1/users",
        json={
            "email": "user@ta-ignore-foreign.io",
            "password": "StrongPass1",
            "role": "annotator",
            "tenant_id": other_tenant["id"],
        },
        headers=auth_header(ta_token),
    )
    assert resp.status_code == 201, resp.text

    own_users = await client.get(f"/api/v1/admin/tenants/{tenant['id']}/users", headers=auth_header(SYSTEM_ADMIN_TOKEN))
    other_users = await client.get(f"/api/v1/admin/tenants/{other_tenant['id']}/users", headers=auth_header(SYSTEM_ADMIN_TOKEN))
    assert "user@ta-ignore-foreign.io" in [u["email"] for u in own_users.json()["users"]]
    assert "user@ta-ignore-foreign.io" not in [u["email"] for u in other_users.json()["users"]]


# --- Scenario 13-15: shared business logic parity ---
@pytest.mark.asyncio
async def test_quota_enforcement_matches_across_admin_and_tenant_endpoints(client: AsyncClient):
    admin_tenant = await create_tenant(client, "quota-parity-admin", max_users=1)
    resp_admin = await client.post(
        f"/api/v1/admin/tenants/{admin_tenant['id']}/users",
        json={"email": "over@quota-parity-admin.io", "password": "StrongPass1", "role": "annotator"},
        headers=auth_header(SYSTEM_ADMIN_TOKEN),
    )
    assert resp_admin.status_code == 429

    ta_tenant = await create_tenant(client, "quota-parity-ta", max_users=1)
    ta_token = tenant_admin_token(ta_tenant["id"])
    resp_ta = await client.post(
        "/api/v1/users",
        json={"email": "over@quota-parity-ta.io", "password": "StrongPass1", "role": "annotator"},
        headers=auth_header(ta_token),
    )
    assert resp_ta.status_code == 429
    assert resp_admin.status_code == resp_ta.status_code


@pytest.mark.asyncio
async def test_password_validation_matches_across_admin_and_tenant_endpoints(client: AsyncClient):
    weak_password = "short"
    admin_tenant = await create_tenant(client, "pw-parity-admin")
    resp_admin = await client.post(
        f"/api/v1/admin/tenants/{admin_tenant['id']}/users",
        json={"email": "weak@pw-parity-admin.io", "password": weak_password, "role": "annotator"},
        headers=auth_header(SYSTEM_ADMIN_TOKEN),
    )

    ta_tenant = await create_tenant(client, "pw-parity-ta")
    ta_token = tenant_admin_token(ta_tenant["id"])
    resp_ta = await client.post(
        "/api/v1/users",
        json={"email": "weak@pw-parity-ta.io", "password": weak_password, "role": "annotator"},
        headers=auth_header(ta_token),
    )

    assert resp_admin.status_code == resp_ta.status_code
    assert resp_admin.status_code >= 400


@pytest.mark.asyncio
async def test_tenant_active_validation_matches_across_admin_and_tenant_endpoints(client: AsyncClient):
    admin_tenant = await create_tenant(client, "active-parity-admin")
    await client.post(f"/api/v1/admin/tenants/{admin_tenant['id']}/deactivate", headers=auth_header(SYSTEM_ADMIN_TOKEN))
    resp_admin = await client.post(
        f"/api/v1/admin/tenants/{admin_tenant['id']}/users",
        json={"email": "inactive@active-parity-admin.io", "password": "StrongPass1", "role": "annotator"},
        headers=auth_header(SYSTEM_ADMIN_TOKEN),
    )
    assert resp_admin.status_code == 403

    ta_tenant = await create_tenant(client, "active-parity-ta")
    ta_token = tenant_admin_token(ta_tenant["id"])
    await client.post(f"/api/v1/admin/tenants/{ta_tenant['id']}/deactivate", headers=auth_header(SYSTEM_ADMIN_TOKEN))
    resp_ta = await client.post(
        "/api/v1/users",
        json={"email": "inactive@active-parity-ta.io", "password": "StrongPass1", "role": "annotator"},
        headers=auth_header(ta_token),
    )
    assert resp_ta.status_code == 403
    assert resp_admin.status_code == resp_ta.status_code


# --- Scenario 16-17: audit logging ---
@pytest.mark.asyncio
async def test_audit_event_recorded_for_system_admin_user_creation(client: AsyncClient, db_session):
    tenant = await create_tenant(client, "audit-sysadmin")
    resp = await client.post(
        f"/api/v1/admin/tenants/{tenant['id']}/users",
        json={"email": "audited@audit-sysadmin.io", "password": "StrongPass1", "role": "annotator"},
        headers=auth_header(SYSTEM_ADMIN_TOKEN),
    )
    assert resp.status_code == 201

    row = await db_session.execute(
        text("SELECT actor, role, action, target, tenant_id FROM public.audit_events WHERE action = 'user.create' AND target = :target"),
        {"target": "audited@audit-sysadmin.io"},
    )
    event = row.fetchone()
    assert event is not None
    assert event.actor == "platform-admin@example.com"
    assert event.role == "system_admin"
    assert event.action == "user.create"
    assert event.tenant_id == tenant["id"]


@pytest.mark.asyncio
async def test_audit_event_recorded_for_tenant_admin_user_creation(client: AsyncClient, db_session):
    tenant = await create_tenant(client, "audit-tenantadmin")
    ta_token = tenant_admin_token(tenant["id"], email="admin@audit-tenantadmin.io")
    resp = await client.post(
        "/api/v1/users",
        json={"email": "audited@audit-tenantadmin.io", "password": "StrongPass1", "role": "annotator"},
        headers=auth_header(ta_token),
    )
    assert resp.status_code == 201

    row = await db_session.execute(
        text("SELECT actor, role, action, target, tenant_id FROM public.audit_events WHERE action = 'user.create' AND target = :target"),
        {"target": "audited@audit-tenantadmin.io"},
    )
    event = row.fetchone()
    assert event is not None
    assert event.actor == "admin@audit-tenantadmin.io"
    assert event.role == "tenant_admin"
    assert event.action == "user.create"
    assert event.tenant_id == tenant["id"]


# --- Cross-tenant email uniqueness is preserved, not widened (Hallucination Risk 10) ---
@pytest.mark.asyncio
async def test_same_email_succeeds_in_two_different_tenants_via_admin_endpoint(client: AsyncClient):
    tenant_a = await create_tenant(client, "cross-tenant-a")
    tenant_b = await create_tenant(client, "cross-tenant-b")
    payload = {"email": "shared@example.io", "password": "StrongPass1", "role": "annotator"}

    resp_a = await client.post(f"/api/v1/admin/tenants/{tenant_a['id']}/users", json=payload, headers=auth_header(SYSTEM_ADMIN_TOKEN))
    resp_b = await client.post(f"/api/v1/admin/tenants/{tenant_b['id']}/users", json=payload, headers=auth_header(SYSTEM_ADMIN_TOKEN))

    assert resp_a.status_code == 201
    assert resp_b.status_code == 201
