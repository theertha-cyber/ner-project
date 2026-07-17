import pytest
from sqlalchemy import text
from src.gateway.models import AuditEventKind
from src.gateway.services.audit_service import AuditService
from src.shared.auth import create_access_token


@pytest.fixture
def system_admin_header():
    token = create_access_token(tenant_id="system", user_id="admin@test.com", role="system_admin", email="admin@test.com")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def tenant_admin_header():
    token = create_access_token(tenant_id="test-tenant", user_id="user@test.com", role="tenant_admin", email="user@test.com")
    return {"Authorization": f"Bearer {token}"}


class TestAuditServiceRecord:
    async def test_inserts_and_returns_correct_fields(self, db_session):
        svc = AuditService(db_session)
        result = await svc.record(
            actor="admin@test.com",
            role="system_admin",
            action="tenant.deactivate",
            target="test-tenant",
            kind=AuditEventKind.reject,
        )

        assert result["actor"] == "admin@test.com"
        assert result["role"] == "system_admin"
        assert result["action"] == "tenant.deactivate"
        assert result["target"] == "test-tenant"
        assert result["kind"] == "reject"
        assert "id" in result
        assert "created_at" in result

        row = await db_session.execute(
            text("SELECT actor, role, action, target, kind FROM public.audit_events WHERE id = :id"),
            {"id": result["id"]},
        )
        db = row.fetchone()
        assert db is not None
        assert db.actor == "admin@test.com"
        assert db.kind == "reject"

    async def test_records_with_tenant_id(self, db_session):
        svc = AuditService(db_session)
        result = await svc.record(
            actor="admin@test.com",
            role="system_admin",
            action="entity_type.create",
            target="vendor_name",
            kind=AuditEventKind.create,
            tenant_id="test-tenant",
        )

        assert result["tenant_id"] == "test-tenant"
        row = await db_session.execute(
            text("SELECT tenant_id FROM public.audit_events WHERE id = :id"),
            {"id": result["id"]},
        )
        assert row.fetchone().tenant_id == "test-tenant"

    async def test_records_without_tenant_id(self, db_session):
        svc = AuditService(db_session)
        result = await svc.record(
            actor="admin@test.com",
            role="system_admin",
            action="tenant.deactivate",
            target="system-action",
            kind=AuditEventKind.reject,
        )

        row = await db_session.execute(
            text("SELECT tenant_id FROM public.audit_events WHERE id = :id"),
            {"id": result["id"]},
        )
        assert row.fetchone().tenant_id is None


class TestAuditServiceListEvents:
    async def seed_events(self, db_session):
        svc = AuditService(db_session)
        for i in range(5):
            await svc.record(
                actor=f"user{i}@test.com",
                role="system_admin",
                action=f"test.action.{i}",
                target=f"target-{i}",
                kind=AuditEventKind.create,
            )

    async def test_returns_paginated_results_ordered_by_created_at_desc(self, db_session):
        svc = AuditService(db_session)
        for i in range(5):
            await svc.record(
                actor=f"user{i}@test.com",
                role="system_admin",
                action=f"test.action.{i}",
                target=f"target-{i}",
                kind=AuditEventKind.create,
            )

        result = await svc.list_events(page=1, per_page=3)

        assert "events" in result
        assert "total" in result
        assert "page" in result
        assert "per_page" in result
        assert result["total"] == 5
        assert result["page"] == 1
        assert result["per_page"] == 3
        assert len(result["events"]) == 3

        timestamps = [e["created_at"] for e in result["events"]]
        assert timestamps == sorted(timestamps, reverse=True)

    async def test_second_page_returns_remaining(self, db_session):
        svc = AuditService(db_session)
        for i in range(5):
            await svc.record(
                actor=f"user{i}@test.com",
                role="system_admin",
                action=f"test.action.{i}",
                target=f"target-{i}",
                kind=AuditEventKind.create,
            )

        result = await svc.list_events(page=2, per_page=3)

        assert len(result["events"]) == 2
        assert result["total"] == 5

    async def test_empty_result(self, db_session):
        svc = AuditService(db_session)
        result = await svc.list_events()

        assert result["events"] == []
        assert result["total"] == 0
        assert result["page"] == 1


class TestAuditLogAPI:
    async def test_system_admin_can_list_events(self, client, db_session, system_admin_header):
        svc = AuditService(db_session)
        await svc.record(
            actor="admin@test.com",
            role="system_admin",
            action="tenant.deactivate",
            target="test-tenant",
            kind=AuditEventKind.reject,
        )

        resp = await client.get("/api/v1/admin/audit-log", headers=system_admin_header)

        assert resp.status_code == 200
        body = resp.json()
        assert "events" in body
        assert "total" in body
        assert "page" in body
        assert "per_page" in body
        assert body["total"] == 1
        assert len(body["events"]) == 1
        event = body["events"][0]
        assert event["actor"] == "admin@test.com"
        assert event["action"] == "tenant.deactivate"
        assert event["target"] == "test-tenant"
        assert event["kind"] == "reject"

    async def test_tenant_admin_receives_403(self, client, tenant_admin_header):
        resp = await client.get("/api/v1/admin/audit-log", headers=tenant_admin_header)

        assert resp.status_code == 403

    async def test_pagination_returns_correct_slice(self, client, db_session, system_admin_header):
        svc = AuditService(db_session)
        for i in range(10):
            await svc.record(
                actor=f"user{i}@test.com",
                role="system_admin",
                action=f"test.action.{i}",
                target=f"target-{i}",
                kind=AuditEventKind.create,
            )

        resp = await client.get("/api/v1/admin/audit-log?page=1&per_page=3", headers=system_admin_header)

        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 10
        assert len(body["events"]) == 3
        assert body["page"] == 1
        assert body["per_page"] == 3
