import pytest

from src.chat_api.api.v1.schemas import CandidateEntity, ChatResponse, PendingClarification, Source

pytestmark = [pytest.mark.verification, pytest.mark.asyncio]


class TestPendingClarificationSerialization:
    """Covers verification.md rows 6, 7: `pending_clarification` is present with
    ambiguous turns and absent (not null) otherwise. Mirrors the exclude-when-None
    construction in `src/chat_api/api/v1/chat.py`."""

    def _response(self, pending):
        response = ChatResponse(
            reply="test", sources=[Source(source_type="sql", value="x")],
            conversation_id="conv-1", pending_clarification=pending,
        )
        exclude = {"pending_clarification"} if pending is None else set()
        return response.model_dump(exclude=exclude)

    def test_absent_when_no_clarification(self):
        payload = self._response(None)
        assert "pending_clarification" not in payload

    def test_present_when_clarification_pending(self):
        pending = PendingClarification(
            mention="Sreelakshmi",
            candidates=[
                CandidateEntity(document_id="doc-1", name="Sreelakshmi R", organization="SEO Technologies"),
                CandidateEntity(document_id="doc-2", name="Sreelakshmi P", organization="UST Global"),
            ],
        )
        payload = self._response(pending)
        assert "pending_clarification" in payload
        assert payload["pending_clarification"]["mention"] == "Sreelakshmi"
        assert len(payload["pending_clarification"]["candidates"]) == 2
        assert payload["pending_clarification"]["candidates"][0]["document_id"] == "doc-1"

    def test_candidate_entity_omits_absent_fields_gracefully(self):
        c = CandidateEntity(document_id="doc-1", name="X")
        assert c.organization is None
        assert c.skills == []


class TestAnaphoricFollowUpInheritsFullBoundSet:
    """verification.md row 50. A turn can resolve to several subjects, so the binding
    an anaphoric follow-up inherits has to be the whole set. It is encoded into the
    existing `resolved_document_id` column — a schema migration is out of scope — as a
    bare identifier for one document and a JSON array for several, so rows written
    before this change read back unchanged."""

    def test_single_document_binding_round_trips_as_a_bare_identifier(self):
        from src.chat_api.services.conversation_entity_state import (
            ConversationState,
            decode_document_ids,
            encode_document_ids,
        )

        stored = encode_document_ids(["D1"])
        assert stored == "D1"
        assert decode_document_ids(stored) == ["D1"]
        assert ConversationState(conversation_id="c", resolved_document_id=stored).resolved_document_ids == ["D1"]

    def test_multi_document_binding_round_trips(self):
        from src.chat_api.services.conversation_entity_state import (
            ConversationState,
            decode_document_ids,
            encode_document_ids,
        )

        stored = encode_document_ids(["D1", "D2"])
        assert decode_document_ids(stored) == ["D1", "D2"]
        state = ConversationState(conversation_id="c", resolved_document_id=stored)
        assert state.has_binding
        assert state.resolved_document_ids == ["D1", "D2"]

    async def test_anaphoric_followup_inherits_full_bound_set(self, monkeypatch):
        from src.chat_api.graph.nodes import build_nodes
        from src.chat_api.services import conversation_entity_state as conv_state
        from src.chat_api.services import entity_resolver
        from src.chat_api.services.entity_resolver import ResolutionResult
        from src.chat_api.services.rag_orchestrator import RAGOrchestrator
        from src.shared.retrieval.orchestrator import PlanEntry, RetrievalPlan

        orchestrator = RAGOrchestrator.__new__(RAGOrchestrator)
        orchestrator.llm_client = object()
        orchestrator.llm_model = "gpt-4o"
        nodes = build_nodes(orchestrator)

        async def fake_read_state(session, schema, cid):
            return conv_state.ConversationState(
                conversation_id=cid,
                resolved_document_id=conv_state.encode_document_ids(["D1", "D2"]),
                resolved_entity_value="Hannah, Girish",
            )

        async def fake_resolve(message, session, schema, tenant_id):
            return ResolutionResult(outcome=entity_resolver.UNRESOLVED)

        monkeypatch.setattr(conv_state, "read_state", fake_read_state)
        monkeypatch.setattr(entity_resolver, "resolve_entity", fake_resolve)

        plan = RetrievalPlan(entries=[
            PlanEntry(capability_name="semantic_retrieval", arguments={"query": "does she know Go"}),
            PlanEntry(capability_name="structured_retrieval", arguments={"query": "does she know Go"}),
        ])
        state = {
            "message": "does she also know Go", "tenant_id": "t1", "schema": "tenant_t1",
            "session": object(), "conversation_id": "conv-1", "retrieval_plan": plan,
        }
        result = await nodes["entity_resolution"](state)

        assert result["resolved_document_ids"] == ["D1", "D2"]
        rewritten = result["retrieval_plan"]
        for entry in rewritten.entries:
            assert entry.arguments["scope"] == {"type": "document", "document_ids": ["D1", "D2"]}


class TestClarificationResponseShape:
    """Covers verification.md row 6: status/empty-sources contract for a
    clarification response, exercised at the schema level (the node-level
    behaviour producing this shape is covered by tests/test_entity_resolution_graph.py)."""

    def test_clarification_response_has_empty_sources(self):
        response = ChatResponse(reply="Which one did you mean?\n\n1. A\n2. B", sources=[], conversation_id="conv-1")
        assert response.sources == []
        assert response.disclaimer is not None
