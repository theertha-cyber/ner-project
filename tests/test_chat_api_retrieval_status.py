"""`retrieval_status` on the chat response — verification.md rows 18, 19, 28.

The turn's per-capability outcome used to exist only as `ChatState["sql_error"]` /
`["retrieval_error"]`, which nothing read. It now reaches the answer model, the
guardrail, and the response payload; this file covers the last of the three, plus the
degraded-planning record that reaches both the prompt and the payload.

Endpoint tests patch `chat_module.orchestrator` at the same boundary
test_chat_api_streaming.py does, rather than standing up retrieval infrastructure.
"""

import pytest
from httpx import AsyncClient, ASGITransport

from src.chat_api.api.v1 import chat as chat_module
from src.chat_api.api.v1.schemas import ChatResponse, RetrievalStatusOut
from src.chat_api.graph.nodes import build_nodes
from src.chat_api.services.rag_orchestrator import RAGOrchestrator
from src.shared.auth import create_access_token
from src.shared.retrieval.orchestrator import (
    OUTCOME_FAILED,
    OUTCOME_OK,
    CapabilityStatus,
    RetrievalStatus,
)

pytestmark = [pytest.mark.verification, pytest.mark.asyncio]


def _app():
    from src.chat_api.main import app
    return app


def auth_header(tenant_id: str, role: str = "business_user", user_id: str = "test-user") -> dict:
    token = create_access_token(tenant_id=tenant_id, user_id=user_id, role=role)
    return {"Authorization": f"Bearer {token}"}


def _fake_citation():
    from src.chat_api.api.v1.schemas import Citation
    return Citation(document_name="report.pdf", document_id="doc-1", source_type="document_chunk",
                    context_snippet="snippet")


MIXED_STATUS = RetrievalStatus(entries=[
    CapabilityStatus(
        capability_name="structured_retrieval", outcome=OUTCOME_FAILED,
        error="SQL generation failed after 3 attempt(s)",
    ),
    CapabilityStatus(capability_name="semantic_retrieval", outcome=OUTCOME_OK, result_count=4),
])


class CannedOrchestrator:
    def __init__(self, retrieval_status=None, sources=None):
        self.retrieval_status = retrieval_status
        self.sources = sources if sources is not None else [_fake_citation()]

    async def execute_with_clarification(self, message, session, schema, tenant_id,
                                         jwt_token=None, conversation_context=None,
                                         conversation_id=None):
        return ("There are 5 organizations.", self.sources, None, "answer", None, self.retrieval_status)


def _patch(monkeypatch, fake: CannedOrchestrator) -> None:
    monkeypatch.setattr(chat_module.orchestrator, "execute_with_clarification",
                        fake.execute_with_clarification)


class TestResponseCarriesRetrievalStatus:
    async def test_response_reports_per_capability_status(self, engine, tenant_schema, monkeypatch):
        tid, _ = tenant_schema
        _patch(monkeypatch, CannedOrchestrator(retrieval_status=MIXED_STATUS.as_dict()))

        async with AsyncClient(transport=ASGITransport(app=_app()), base_url="http://test") as client:
            resp = await client.post("/api/v1/chat", headers=auth_header(tid),
                                     json={"message": "How many organizations?", "conversation_id": None})

        assert resp.status_code == 200
        body = resp.json()
        by_name = {e["capability_name"]: e for e in body["retrieval_status"]["entries"]}
        assert by_name["structured_retrieval"]["outcome"] == "failed"
        assert by_name["structured_retrieval"]["error"]
        assert by_name["semantic_retrieval"]["outcome"] == "ok"

    async def test_retrieval_status_is_additive_to_response_schema(self, engine, tenant_schema, monkeypatch):
        """A client reading only the previously specified fields sees no change, and a
        turn that never reached retrieval omits the key entirely rather than sending
        null."""
        tid, _ = tenant_schema
        previously_specified = {
            "reply", "sources", "conversation_id", "disclaimer", "message_id",
            "answer_kind", "model_version",
        }

        _patch(monkeypatch, CannedOrchestrator(retrieval_status=MIXED_STATUS.as_dict()))
        async with AsyncClient(transport=ASGITransport(app=_app()), base_url="http://test") as client:
            with_status = (await client.post("/api/v1/chat", headers=auth_header(tid),
                                             json={"message": "q", "conversation_id": None})).json()

        _patch(monkeypatch, CannedOrchestrator(retrieval_status=None))
        async with AsyncClient(transport=ASGITransport(app=_app()), base_url="http://test") as client:
            without_status = (await client.post("/api/v1/chat", headers=auth_header(tid),
                                                json={"message": "q", "conversation_id": None})).json()

        assert previously_specified <= set(with_status)
        assert "retrieval_status" not in without_status
        for field in previously_specified - {"conversation_id", "message_id"}:
            assert with_status[field] == without_status[field], field

    def test_response_model_defaults_to_absent(self):
        response = ChatResponse(reply="hi", sources=[])
        assert response.retrieval_status is None

    def test_status_dict_round_trips_into_the_response_model(self):
        parsed = RetrievalStatusOut(**MIXED_STATUS.as_dict())
        assert [e.outcome for e in parsed.entries] == ["failed", "ok"]
        assert parsed.planning_degraded is False


class TestDegradedPlanningSurfaces:
    async def test_degraded_planning_surfaces_in_prompt_and_response(self):
        """The degraded fallback was recorded in state and read nowhere. It now reaches
        prompt assembly and the response payload from the one stored value."""
        from src.chat_api.services.context_assembler import render_retrieval_status

        status = RetrievalStatus(entries=[], planning_degraded=True, stop_reason="planner_error")

        orchestrator = RAGOrchestrator.__new__(RAGOrchestrator)

        async def _no_names(sources, session, schema):
            return {}

        orchestrator._resolve_document_names = _no_names
        nodes = build_nodes(orchestrator)
        state = {
            "message": "who knows python?", "sql_results": None, "chunks": [],
            "conversation_context": None, "retrieval_status": status,
            "tenant_id": "t1", "schema": "tenant_t1", "session": object(),
        }
        prompt = await nodes["prompt_assembly"](state)
        user_content = prompt["prompt_messages"][-1]["content"]

        assert "DEGRADED" in user_content
        assert "planner_error" in user_content
        assert render_retrieval_status(status) is not None

        payload = RAGOrchestrator._retrieval_status_payload({"retrieval_status": status})
        assert payload["planning_degraded"] is True
        assert payload["stop_reason"] == "planner_error"

    def test_turn_that_never_retrieved_has_no_status_payload(self):
        assert RAGOrchestrator._retrieval_status_payload({}) is None
        assert RAGOrchestrator._retrieval_status_payload({"retrieval_status": None}) is None
