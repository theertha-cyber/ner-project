"""Covers verification.md rows 24-26 and 31-32, 34: the chart's place in the chat
response contract, and its persistence across a conversation reload."""

import json
import uuid

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text

from src.chat_api.api.v1 import chat as chat_module
from src.chat_api.api.v1.schemas import Citation
from src.chat_api.main import app
from src.shared.auth import create_access_token

pytestmark = [pytest.mark.verification, pytest.mark.asyncio]

CHART = {
    "chart_type": "bar",
    "title": "Billed per quarter",
    "x_label": "Quarter",
    "y_label": "Amount",
    "categories": ["Q1", "Q2", "Q3", "Q4"],
    "series": [{"name": "amount", "data": [120000.0, 95000.0, 143000.0, 160000.0]}],
}


def auth_header(tenant_id: str, role: str = "business_user", user_id: str = "test-user") -> dict:
    return {"Authorization": f"Bearer {create_access_token(tenant_id=tenant_id, user_id=user_id, role=role)}"}


def _citation():
    return Citation(document_name="statement.pdf", document_id="doc-1",
                    source_type="sql", context_snippet="Q1 120000")


def _patch_turn(monkeypatch, chart, reply="Billing rose through the year.", sources=None):
    """Replaces the orchestrator's non-streaming entry point with a canned turn,
    matching the boundary test_chat_api_streaming.py patches at."""
    async def _execute(message, session, schema, tenant_id, jwt_token=None,
                       conversation_context=None, conversation_id=None,
                       requesting_user=None):
        return (reply, sources if sources is not None else [_citation()], None,
                "answer", "v1", None, None, chart)

    monkeypatch.setattr(chat_module.orchestrator, "execute_with_clarification", _execute)


async def _post_chat(tenant_id, message="how much did we bill per quarter?"):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        return await client.post("/api/v1/chat", headers=auth_header(tenant_id),
                                 json={"message": message, "conversation_id": None})


async def _get_conversation(tenant_id, conv_id):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        return await client.get(f"/api/v1/chat/conversations/{conv_id}", headers=auth_header(tenant_id))


class TestResponseContract:
    async def test_24_response_without_a_chart_omits_the_key(self, engine, tenant_schema, monkeypatch):
        """Row 24: absent, not null — a client that never looks for a chart sees no change."""
        tid, _ = tenant_schema
        _patch_turn(monkeypatch, chart=None)

        resp = await _post_chat(tid)

        assert resp.status_code == 200
        body = resp.json()
        assert "chart" not in body
        assert body["reply"] and body["sources"]

    async def test_25_charted_response_carries_the_payload_and_citations(self, engine, tenant_schema, monkeypatch):
        """Row 25."""
        tid, _ = tenant_schema
        _patch_turn(monkeypatch, chart=CHART)

        body = (await _post_chat(tid)).json()

        assert body["chart"]["chart_type"] == "bar"
        assert body["chart"]["title"] == "Billed per quarter"
        assert body["chart"]["categories"] == ["Q1", "Q2", "Q3", "Q4"]
        assert body["chart"]["series"][0]["data"] == [120000.0, 95000.0, 143000.0, 160000.0]
        assert len(body["sources"]) >= 1

    async def test_26_widget_response_has_no_chart_field(self, engine, tenant_schema):
        """Row 26: the widget contract is untouched by this change."""
        from src.chat_api.api.v1.schemas import WidgetChatResponse

        assert "chart" not in WidgetChatResponse.model_fields
        assert set(WidgetChatResponse.model_fields) == {"reply", "sources", "disclaimer"}


class TestPersistenceAndReload:
    async def test_31_chart_survives_conversation_reload(self, engine, tenant_schema, monkeypatch):
        """Row 31."""
        tid, schema = tenant_schema
        _patch_turn(monkeypatch, chart=CHART)

        live = (await _post_chat(tid)).json()
        reloaded = (await _get_conversation(tid, live["conversation_id"])).json()

        assistant = [m for m in reloaded["messages"] if m["role"] == "assistant"]
        assert len(assistant) == 1
        assert assistant[0]["chart"] == live["chart"]

    async def test_31_chart_is_persisted_as_jsonb_on_the_assistant_row(self, engine, tenant_schema, monkeypatch):
        tid, schema = tenant_schema
        _patch_turn(monkeypatch, chart=CHART)

        conv_id = (await _post_chat(tid)).json()["conversation_id"]

        async with engine.begin() as conn:
            rows = (await conn.execute(
                text(f"SELECT role, chart FROM {schema}.chat_messages WHERE conversation_id = :cid"),
                {"cid": conv_id},
            )).fetchall()

        by_role = {r.role: r.chart for r in rows}
        assert by_role["user"] is None
        stored = by_role["assistant"]
        stored = json.loads(stored) if isinstance(stored, str) else stored
        assert stored["title"] == "Billed per quarter"

    async def test_32_chartless_conversation_reloads_unchanged(self, engine, tenant_schema, monkeypatch):
        """Row 32."""
        tid, _ = tenant_schema
        _patch_turn(monkeypatch, chart=None)

        conv_id = (await _post_chat(tid)).json()["conversation_id"]
        reloaded = (await _get_conversation(tid, conv_id)).json()

        assert reloaded["messages"]
        for message in reloaded["messages"]:
            assert message["chart"] is None

    async def test_34_rows_written_before_the_column_read_back_cleanly(self, engine, tenant_schema):
        """Row 34: an assistant row inserted without ever naming the chart column —
        exactly what a row written before the migration looks like."""
        tid, schema = tenant_schema
        conv_id = str(uuid.uuid4())
        async with engine.begin() as conn:
            await conn.execute(
                text(f"INSERT INTO {schema}.conversations (id, tenant_id, user_id) VALUES (:id, :tid, 'test-user')"),
                {"id": conv_id, "tid": tid},
            )
            await conn.execute(
                text(
                    f"INSERT INTO {schema}.chat_messages (id, conversation_id, role, content, answer_kind) "
                    "VALUES (:id, :cid, 'assistant', 'an older answer', 'answer')"
                ),
                {"id": str(uuid.uuid4()), "cid": conv_id},
            )

        resp = await _get_conversation(tid, conv_id)

        assert resp.status_code == 200
        message = resp.json()["messages"][0]
        assert message["content"] == "an older answer"
        assert message["chart"] is None

    async def test_unreadable_persisted_chart_is_dropped_not_fatal(self, engine, tenant_schema):
        """A payload that no longer validates must not break the whole reload."""
        tid, schema = tenant_schema
        conv_id = str(uuid.uuid4())
        async with engine.begin() as conn:
            await conn.execute(
                text(f"INSERT INTO {schema}.conversations (id, tenant_id, user_id) VALUES (:id, :tid, 'test-user')"),
                {"id": conv_id, "tid": tid},
            )
            await conn.execute(
                text(
                    f"INSERT INTO {schema}.chat_messages (id, conversation_id, role, content, answer_kind, chart) "
                    "VALUES (:id, :cid, 'assistant', 'answer', 'answer', :chart)"
                ),
                {"id": str(uuid.uuid4()), "cid": conv_id,
                 "chart": json.dumps({"chart_type": "sunburst", "title": "nope"})},
            )

        resp = await _get_conversation(tid, conv_id)

        assert resp.status_code == 200
        assert resp.json()["messages"][0]["chart"] is None
