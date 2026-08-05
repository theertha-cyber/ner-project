import uuid
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text

from src.shared.auth import create_access_token
from src.gateway.main import app

pytestmark = [pytest.mark.verification, pytest.mark.asyncio]


def auth_header(tenant_id: str, role: str = "tenant_admin", user_id: str = "test-user") -> dict:
    token = create_access_token(tenant_id=tenant_id, user_id=user_id, role=role)
    return {"Authorization": f"Bearer {token}"}


async def _get_summary(tenant_id: str) -> tuple[int, dict]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/dashboard/summary", headers=auth_header(tenant_id))
        return resp.status_code, resp.json() if resp.text else {}


async def _seed_feedback(engine, schema: str, tenant_id: str, total: int, ratings: list[str]) -> None:
    """Creates `total` eligible assistant answer messages; the first
    len(ratings) of them get a chat_message_feedback row with the given rating."""
    async with engine.begin() as conn:
        conv_id = str(uuid.uuid4())
        await conn.execute(
            text("INSERT INTO {schema}.conversations (id, tenant_id, user_id) VALUES (:id, :tid, 'u1')".format(schema=schema)),
            {"id": conv_id, "tid": tenant_id},
        )
        for i in range(total):
            msg_id = str(uuid.uuid4())
            await conn.execute(
                text(
                    "INSERT INTO {schema}.chat_messages (id, conversation_id, role, content, answer_kind) "
                    "VALUES (:id, :cid, 'assistant', 'hi', 'answer')".format(schema=schema)
                ),
                {"id": msg_id, "cid": conv_id},
            )
            if i < len(ratings):
                await conn.execute(
                    text(
                        "INSERT INTO {schema}.chat_message_feedback (id, message_id, tenant_id, user_id, rating) "
                        "VALUES (:id, :mid, :tid, 'u1', :rating)".format(schema=schema)
                    ),
                    {"id": str(uuid.uuid4()), "mid": msg_id, "tid": tenant_id, "rating": ratings[i]},
                )


class TestResponseQualityCard:
    async def test_healthy_status_computed_from_rated_subset_only(self, engine, tenant_schema):
        tid, schema = tenant_schema
        # 61 eligible messages, 42 rated (35 up, 7 down), 19 unrated
        ratings = ["up"] * 35 + ["down"] * 7
        await _seed_feedback(engine, schema, tid, total=61, ratings=ratings)

        status, body = await _get_summary(tid)

        assert status == 200
        d = body["data"]
        # Active model panel is untouched by feedback data; the old sideBot/
        # sideRows slots are no longer used for feedback content
        assert d["sideTop"] == "Active model"
        assert d["sideBot"] == ""
        assert d["sideRows"] == []

        rq = d["responseQuality"]
        assert rq["status"] == "healthy"
        assert rq["satisfactionPct"] == 83.3  # 35/42, not 35/61
        assert rq["positive"] == 35
        assert rq["negative"] == 7
        assert rq["rated"] == 42
        assert rq["total"] == 61
        assert "No retraining recommended" in rq["recommendation"]

    async def test_unrated_messages_do_not_affect_ratio(self, engine, tenant_schema):
        tid, schema = tenant_schema
        # 20 eligible messages, 5 rated (4 up, 1 down), 15 unrated
        ratings = ["up"] * 4 + ["down"]
        await _seed_feedback(engine, schema, tid, total=20, ratings=ratings)

        status, body = await _get_summary(tid)

        assert status == 200
        rq = body["data"]["responseQuality"]
        assert rq["satisfactionPct"] == 80.0
        assert rq["total"] == 20
        assert rq["rated"] == 5

    async def test_no_ratings_yet_is_no_data_not_misleading_zero(self, engine, tenant_schema):
        tid, schema = tenant_schema
        await _seed_feedback(engine, schema, tid, total=10, ratings=[])

        status, body = await _get_summary(tid)

        assert status == 200
        rq = body["data"]["responseQuality"]
        assert rq["status"] == "no_data"
        assert rq["satisfactionPct"] is None
        assert rq["total"] == 10
        assert rq["rated"] == 0
        assert rq["positive"] == 0
        assert "Not enough feedback" in rq["recommendation"]

    async def test_low_satisfaction_is_needs_attention_with_retraining_recommendation(self, engine, tenant_schema):
        tid, schema = tenant_schema
        # 3 rated (1 up, 2 down) out of 70 -> 33%, below the 60% needs_attention threshold
        ratings = ["up"] + ["down"] * 2
        await _seed_feedback(engine, schema, tid, total=70, ratings=ratings)

        status, body = await _get_summary(tid)

        assert status == 200
        rq = body["data"]["responseQuality"]
        assert rq["status"] == "needs_attention"
        assert round(rq["satisfactionPct"]) == 33
        assert "Consider retraining" in rq["recommendation"]

    async def test_mid_range_satisfaction_is_monitor(self, engine, tenant_schema):
        tid, schema = tenant_schema
        # 7 up, 3 down out of 10 rated -> 70%, in the 60-79 monitor band
        ratings = ["up"] * 7 + ["down"] * 3
        await _seed_feedback(engine, schema, tid, total=40, ratings=ratings)

        status, body = await _get_summary(tid)

        assert status == 200
        rq = body["data"]["responseQuality"]
        assert rq["status"] == "monitor"

    async def test_unavailable_training_service_does_not_affect_response_quality_card(self, engine, tenant_schema):
        tid, schema = tenant_schema
        await _seed_feedback(engine, schema, tid, total=5, ratings=["up", "up"])
        async with engine.begin() as conn:
            await conn.execute(text(f"DROP TABLE IF EXISTS {schema}.training_jobs CASCADE"))

        status, body = await _get_summary(tid)

        assert status == 200
        assert body["sources"]["training"] is False
        rq = body["data"]["responseQuality"]
        assert rq["status"] == "healthy"
        assert rq["satisfactionPct"] == 100.0
