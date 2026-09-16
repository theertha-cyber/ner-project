"""Gateway `/api/v1/notifications` — read + mark-read, tenant + audience scoped.

The bell in the portal topbar. Rows are written by services (annotator approves a task
or a 50+ automated batch); this router only reads them and marks them read. A caller
sees a row when it is for their tenant AND addressed to their role or to them by id.
"""
import uuid

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text

from src.shared.auth import create_access_token
from src.gateway.main import app


def _auth(tenant_id: str, role: str = "tenant_admin", user_id: str = "u-1") -> dict:
    token = create_access_token(tenant_id=tenant_id, user_id=user_id, role=role)
    return {"Authorization": f"Bearer {token}"}


async def _seed(engine, *, tenant_id, recipient_role="tenant_admin", recipient_user_id=None,
                title="Task approved", read_at=None) -> str:
    nid = str(uuid.uuid4())
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO public.notifications "
                "(id, tenant_id, recipient_role, recipient_user_id, kind, title, body, read_at) "
                "VALUES (:id, :tid, :role, :uid, 'annotation_task_completed', :title, NULL, :read_at)"
            ),
            {"id": nid, "tid": tenant_id, "role": recipient_role,
             "uid": recipient_user_id, "title": title, "read_at": read_at},
        )
    return nid


async def _client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
class TestNotificationsApi:
    async def test_tenant_admin_sees_role_notification(self, engine, setup_database):
        tid = f"notif-{uuid.uuid4().hex[:8]}"
        await _seed(engine, tenant_id=tid, title="Batch ready for training")
        async with await _client() as c:
            resp = await c.get("/api/v1/notifications", headers=_auth(tid, "tenant_admin"))
        assert resp.status_code == 200
        body = resp.json()
        assert body["unread"] == 1
        assert body["items"][0]["title"] == "Batch ready for training"

    async def test_business_user_excluded(self, engine, setup_database):
        tid = f"notif-{uuid.uuid4().hex[:8]}"
        await _seed(engine, tenant_id=tid)
        async with await _client() as c:
            resp = await c.get("/api/v1/notifications", headers=_auth(tid, "business_user", "biz-1"))
        assert resp.status_code == 200
        body = resp.json()
        assert body["items"] == []
        assert body["unread"] == 0

    async def test_cross_tenant_isolation(self, engine, setup_database):
        tid_a = f"notif-{uuid.uuid4().hex[:8]}"
        tid_b = f"notif-{uuid.uuid4().hex[:8]}"
        await _seed(engine, tenant_id=tid_a, title="A only")
        async with await _client() as c:
            resp = await c.get("/api/v1/notifications", headers=_auth(tid_b, "tenant_admin"))
        assert resp.status_code == 200
        assert resp.json()["items"] == []

    async def test_mark_one_read(self, engine, setup_database):
        tid = f"notif-{uuid.uuid4().hex[:8]}"
        nid = await _seed(engine, tenant_id=tid)
        async with await _client() as c:
            marked = await c.post(f"/api/v1/notifications/{nid}/read", headers=_auth(tid, "tenant_admin"))
            assert marked.status_code == 200
            assert marked.json()["updated"] == 1
            after = await c.get("/api/v1/notifications", headers=_auth(tid, "tenant_admin"))
        assert after.json()["unread"] == 0

    async def test_mark_foreign_notification_404(self, engine, setup_database):
        tid = f"notif-{uuid.uuid4().hex[:8]}"
        other = f"notif-{uuid.uuid4().hex[:8]}"
        nid = await _seed(engine, tenant_id=other)
        async with await _client() as c:
            resp = await c.post(f"/api/v1/notifications/{nid}/read", headers=_auth(tid, "tenant_admin"))
        assert resp.status_code == 404
