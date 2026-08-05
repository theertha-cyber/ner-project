import uuid
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text

from src.shared.auth import create_access_token
from src.chat_api.main import app

pytestmark = [pytest.mark.verification, pytest.mark.asyncio]


def auth_header(tenant_id: str, role: str, user_id: str = "test-user") -> dict:
    token = create_access_token(tenant_id=tenant_id, user_id=user_id, role=role)
    return {"Authorization": f"Bearer {token}"}


async def _insert_conversation(engine, schema: str, tenant_id: str, user_id: str = "test-user") -> str:
    conv_id = str(uuid.uuid4())
    async with engine.begin() as conn:
        await conn.execute(
            text(f"INSERT INTO {schema}.conversations (id, tenant_id, user_id) VALUES (:id, :tid, :uid)"),
            {"id": conv_id, "tid": tenant_id, "uid": user_id},
        )
    return conv_id


async def _insert_message(engine, schema: str, conv_id: str, role: str = "assistant", answer_kind: str = "answer") -> str:
    msg_id = str(uuid.uuid4())
    async with engine.begin() as conn:
        await conn.execute(
            text(
                f"INSERT INTO {schema}.chat_messages (id, conversation_id, role, content, answer_kind) "
                "VALUES (:id, :cid, :role, 'hello', :kind)"
            ),
            {"id": msg_id, "cid": conv_id, "role": role, "kind": answer_kind},
        )
    return msg_id


async def _post_feedback(tenant_id: str, message_id: str, role: str, rating: str = "up"):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            f"/api/v1/chat/messages/{message_id}/feedback",
            headers=auth_header(tenant_id, role),
            json={"rating": rating},
        )
        return resp.status_code, resp.json() if resp.text else {}


class TestFeedbackEndpoint:
    async def test_business_user_submits_first_rating(self, engine, tenant_schema):
        tid, schema = tenant_schema
        conv_id = await _insert_conversation(engine, schema, tid)
        msg_id = await _insert_message(engine, schema, conv_id)

        status, body = await _post_feedback(tid, msg_id, "business_user", "up")

        assert status == 201
        assert body["message_id"] == msg_id
        assert body["rating"] == "up"

    async def test_duplicate_rating_returns_409_and_does_not_overwrite(self, engine, tenant_schema):
        tid, schema = tenant_schema
        conv_id = await _insert_conversation(engine, schema, tid)
        msg_id = await _insert_message(engine, schema, conv_id)

        first_status, _ = await _post_feedback(tid, msg_id, "business_user", "down")
        assert first_status == 201

        second_status, second_body = await _post_feedback(tid, msg_id, "business_user", "up")

        assert second_status == 409
        assert second_body["detail"]["rating"] == "down"

    async def test_rating_user_message_returns_404(self, engine, tenant_schema):
        tid, schema = tenant_schema
        conv_id = await _insert_conversation(engine, schema, tid)
        msg_id = await _insert_message(engine, schema, conv_id, role="user", answer_kind="answer")

        status, _ = await _post_feedback(tid, msg_id, "business_user")

        assert status == 404

    async def test_rating_clarification_message_returns_404(self, engine, tenant_schema):
        tid, schema = tenant_schema
        conv_id = await _insert_conversation(engine, schema, tid)
        msg_id = await _insert_message(engine, schema, conv_id, answer_kind="clarification")

        status, _ = await _post_feedback(tid, msg_id, "business_user")

        assert status == 404

    async def test_rating_guardrail_blocked_message_returns_404(self, engine, tenant_schema):
        tid, schema = tenant_schema
        conv_id = await _insert_conversation(engine, schema, tid)
        msg_id = await _insert_message(engine, schema, conv_id, answer_kind="guardrail_blocked")

        status, _ = await _post_feedback(tid, msg_id, "business_user")

        assert status == 404

    async def test_rating_out_of_domain_message_returns_404(self, engine, tenant_schema):
        tid, schema = tenant_schema
        conv_id = await _insert_conversation(engine, schema, tid)
        msg_id = await _insert_message(engine, schema, conv_id, answer_kind="out_of_domain")

        status, _ = await _post_feedback(tid, msg_id, "business_user")

        assert status == 404

    async def test_non_business_user_role_returns_403(self, engine, tenant_schema):
        tid, schema = tenant_schema
        conv_id = await _insert_conversation(engine, schema, tid)
        msg_id = await _insert_message(engine, schema, conv_id)

        status, _ = await _post_feedback(tid, msg_id, "tenant_admin")

        assert status == 403

    async def test_unauthenticated_request_returns_401(self, engine, tenant_schema):
        tid, schema = tenant_schema
        conv_id = await _insert_conversation(engine, schema, tid)
        msg_id = await _insert_message(engine, schema, conv_id)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(f"/api/v1/chat/messages/{msg_id}/feedback", json={"rating": "up"})

        assert resp.status_code == 401

    async def test_duplicate_rating_same_value_returns_409(self, engine, tenant_schema):
        tid, schema = tenant_schema
        conv_id = await _insert_conversation(engine, schema, tid)
        msg_id = await _insert_message(engine, schema, conv_id)

        first_status, _ = await _post_feedback(tid, msg_id, "business_user", "up")
        assert first_status == 201

        second_status, second_body = await _post_feedback(tid, msg_id, "business_user", "up")

        assert second_status == 409
        assert second_body["detail"]["rating"] == "up"

    async def test_rating_persists_and_is_visible_via_conversation_get(self, engine, tenant_schema):
        tid, schema = tenant_schema
        conv_id = await _insert_conversation(engine, schema, tid)
        msg_id = await _insert_message(engine, schema, conv_id)

        status, _ = await _post_feedback(tid, msg_id, "business_user", "down")
        assert status == 201

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                f"/api/v1/chat/conversations/{conv_id}",
                headers=auth_header(tid, "business_user"),
            )

        assert resp.status_code == 200
        body = resp.json()
        msg = next(m for m in body["messages"] if m["id"] == msg_id)
        assert msg["feedback"]["rating"] == "down"
        assert msg["answer_kind"] == "answer"
