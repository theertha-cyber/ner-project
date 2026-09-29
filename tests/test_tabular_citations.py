"""Tabular citations without row values (tabular-file-chat spec).

Sources come from the real prompt assembly, source assembly and citation
enrichment; the turn is persisted through the real chat route and reloaded
through the real conversation route."""

import json

import pytest
from httpx import ASGITransport, AsyncClient

from src.chat_api.api.v1 import chat as chat_module
from src.chat_api.graph.nodes import build_nodes
from src.chat_api.main import app
from src.chat_api.services.context_assembler import ContextAssembler
from src.chat_api.services.rag_orchestrator import RAGOrchestrator
from src.shared.auth import create_access_token

pytestmark = [pytest.mark.verification, pytest.mark.asyncio]

ROWS = [{"total": 1650}]
FILES = [{"display_name": "sales_q3.csv", "version": 1, "sheet": None, "relation": "sales_q3"}]
COLUMNS = ["amount", "region", "status"]


def _auth(tenant_id):
    return {"Authorization": f"Bearer {create_access_token(tenant_id=tenant_id, user_id='test-user', role='business_user')}"}


async def _real_sources():
    messages, admitted = ContextAssembler().assemble(
        "total closed revenue in EMEA?", None, [], {}, None,
        tabular_results=ROWS, tabular_files=FILES, tabular_columns=COLUMNS, return_evidence=True,
    )
    # The rows reach the generation prompt through their own channel.
    assert "1650" in messages[-1]["content"]
    orchestrator = RAGOrchestrator.__new__(RAGOrchestrator)
    state = {"tenant_id": "test-tenant", "schema": "tenant_test_tenant", "session": None,
             "admitted_evidence": admitted, "document_names": {}}
    return (await build_nodes(orchestrator)["source_assembly"](state))["sources"]


async def test_citation_names_file_and_columns_only(engine, tenant_schema, monkeypatch):
    """Scenario: Citation names file and columns only."""
    tid, _ = tenant_schema
    sources = await _real_sources()
    assert [s.source_type for s in sources] == ["tabular_file"]

    async def _execute(message, session, schema, tenant_id, jwt_token=None, conversation_context=None,
                       conversation_id=None, requesting_user=None):
        return ("Closed revenue in EMEA was 1650.", sources, None, "answer", "v1", None, None, None)

    monkeypatch.setattr(chat_module.orchestrator, "execute_with_clarification", _execute)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        posted = await client.post("/api/v1/chat", headers=_auth(tid),
                                   json={"message": "total closed revenue in EMEA?", "conversation_id": None})
        assert posted.status_code == 200, posted.text
        conv_id = posted.json()["conversation_id"]
        reloaded = await client.get(f"/api/v1/chat/conversations/{conv_id}", headers=_auth(tid))
    assert reloaded.status_code == 200
    assistant = [m for m in reloaded.json()["messages"] if m["role"] == "assistant"][0]
    [citation] = assistant["sources"]
    assert citation["source_type"] == "tabular_file"
    assert citation["file_name"] == "sales_q3.csv"
    assert citation["file_version"] == 1
    assert citation["relation"] == "sales_q3"
    assert citation["columns"] == ["amount", "region", "status"]
    serialized = json.dumps(citation)
    for value in ("EMEA", "closed", "1650", "APAC", "first deal"):
        assert value not in serialized
    # The live response carries the same shape.
    assert json.dumps(posted.json()["sources"]).count("EMEA") == 0
