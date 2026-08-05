import pytest

from src.chat_api.graph.nodes import build_nodes
from src.chat_api.services import conversation_entity_state as conv_state
from src.chat_api.services import entity_resolver
from src.chat_api.services.entity_resolver import Candidate, ResolutionResult
from src.chat_api.services.rag_orchestrator import RAGOrchestrator
from src.shared.retrieval.orchestrator import PlanEntry, RetrievalPlan

pytestmark = [pytest.mark.verification, pytest.mark.asyncio]


class _SentinelSession:
    """Never dereferenced directly — every call that would touch the DB is
    monkeypatched at the module-function level in these tests."""


def _tenant_plan(query="Tell me about Sreelakshmi"):
    return RetrievalPlan(entries=[
        PlanEntry(capability_name="semantic_retrieval", arguments={"query": query}),
        PlanEntry(capability_name="structured_retrieval", arguments={"query": query}),
    ])


def _base_state(message="Tell me about Sreelakshmi", conversation_id="conv-1"):
    return {
        "message": message, "tenant_id": "t1", "schema": "tenant_t1",
        "session": _SentinelSession(), "conversation_id": conversation_id,
        "retrieval_plan": _tenant_plan(message),
    }


@pytest.fixture
def nodes():
    orchestrator = RAGOrchestrator.__new__(RAGOrchestrator)
    orchestrator.llm_client = object()
    orchestrator.llm_model = "gpt-4o"
    return build_nodes(orchestrator)


class TestNoConversationId:
    async def test_absent_conversation_id_is_a_noop(self, nodes):
        state = _base_state(conversation_id=None)
        result = await nodes["entity_resolution"](state)
        assert result["entity_resolution_outcome"] is None
        assert result["resolved_document_ids"] == []
        assert "reply" not in result


class TestUnresolvedAndUnique:
    """Covers verification.md rows 15, 21, 28, 29, 50."""

    async def test_unresolved_adds_no_scope(self, nodes, monkeypatch):
        async def fake_read_state(session, schema, cid):
            return conv_state.ConversationState(conversation_id=cid)
        async def fake_resolve(message, session, schema, tenant_id):
            return ResolutionResult(outcome=entity_resolver.UNRESOLVED, mentions_checked=3)
        monkeypatch.setattr(conv_state, "read_state", fake_read_state)
        monkeypatch.setattr(entity_resolver, "resolve_entity", fake_resolve)

        state = _base_state()
        result = await nodes["entity_resolution"](state)

        assert result["entity_resolution_outcome"] == "unresolved"
        assert result["resolved_document_ids"] == []
        assert "retrieval_plan" not in result
        assert "reply" not in result

    async def test_unique_scopes_semantic_and_structured(self, nodes, monkeypatch):
        async def fake_read_state(session, schema, cid):
            return conv_state.ConversationState(conversation_id=cid)
        async def fake_resolve(message, session, schema, tenant_id):
            return ResolutionResult(outcome=entity_resolver.UNIQUE, mention="Sreelakshmi R",
                                     resolved_document_id="doc-1", resolved_entity_value="Sreelakshmi R")
        set_binding_calls = []
        async def fake_set_binding(session, schema, cid, doc_id, entity_value):
            set_binding_calls.append((doc_id, entity_value))

        monkeypatch.setattr(conv_state, "read_state", fake_read_state)
        monkeypatch.setattr(conv_state, "set_binding", fake_set_binding)
        monkeypatch.setattr(entity_resolver, "resolve_entity", fake_resolve)

        state = _base_state()
        result = await nodes["entity_resolution"](state)

        assert result["entity_resolution_outcome"] == "unique"
        assert result["resolved_document_ids"] == ["doc-1"]
        assert set_binding_calls == [("doc-1", "Sreelakshmi R")]

        plan = result["retrieval_plan"]
        semantic = next(e for e in plan.entries if e.capability_name == "semantic_retrieval")
        structured = next(e for e in plan.entries if e.capability_name == "structured_retrieval")
        assert semantic.arguments["scope"] == {"type": "document", "document_ids": ["doc-1"]}
        assert "doc-1" in structured.arguments["query"]


class TestAmbiguousAndOverCap:
    """Covers verification.md rows 14, 32, 33, 34."""

    async def test_ambiguous_terminates_with_no_scope_and_no_plan_mutation(self, nodes, monkeypatch):
        candidates = [
            Candidate(document_id="doc-1", name="Sreelakshmi R", organization="SEO Technologies"),
            Candidate(document_id="doc-2", name="Sreelakshmi P", organization="UST Global"),
        ]
        async def fake_read_state(session, schema, cid):
            return conv_state.ConversationState(conversation_id=cid)
        async def fake_resolve(message, session, schema, tenant_id):
            return ResolutionResult(outcome=entity_resolver.AMBIGUOUS, mention="Sreelakshmi", candidates=candidates)
        stored = []
        async def fake_store(session, schema, cid, original_message, mention, cands):
            stored.append((original_message, mention, cands))

        monkeypatch.setattr(conv_state, "read_state", fake_read_state)
        monkeypatch.setattr(conv_state, "store_pending_clarification", fake_store)
        monkeypatch.setattr(entity_resolver, "resolve_entity", fake_resolve)

        state = _base_state()
        result = await nodes["entity_resolution"](state)

        assert result["entity_resolution_outcome"] == "ambiguous"
        assert result["resolved_document_ids"] == []
        assert result["sources"] == []
        assert "retrieval_plan" not in result
        assert "reply" in result
        assert "Sreelakshmi" in result["reply"]
        assert "1. " in result["reply"] and "2. " in result["reply"]
        assert result["pending_clarification"]["candidates"][0]["document_id"] == "doc-1"
        assert stored[0][0] == state["message"]

    async def test_over_cap_terminates_with_no_pending_state(self, nodes, monkeypatch):
        async def fake_read_state(session, schema, cid):
            return conv_state.ConversationState(conversation_id=cid)
        async def fake_resolve(message, session, schema, tenant_id):
            return ResolutionResult(outcome=entity_resolver.OVER_CAP, mention="Sreelakshmi")
        store_calls = []
        async def fake_store(*a, **kw):
            store_calls.append((a, kw))

        monkeypatch.setattr(conv_state, "read_state", fake_read_state)
        monkeypatch.setattr(conv_state, "store_pending_clarification", fake_store)
        monkeypatch.setattr(entity_resolver, "resolve_entity", fake_resolve)

        state = _base_state()
        result = await nodes["entity_resolution"](state)

        assert result["entity_resolution_outcome"] == "over_cap"
        assert result["sources"] == []
        assert "narrow" in result["reply"].lower()
        assert store_calls == []
        assert "pending_clarification" not in result


class TestPendingClarificationResume:
    """Covers verification.md rows 42-49."""

    def _pending_conv(self, reask_count=0):
        return conv_state.ConversationState(
            conversation_id="conv-1",
            pending_original_message="Tell me about Sreelakshmi",
            pending_mention="Sreelakshmi",
            pending_candidates=[
                Candidate(document_id="doc-1", name="Sreelakshmi R", organization="SEO Technologies", skills=["ReactJS"]),
                Candidate(document_id="doc-2", name="Sreelakshmi P", organization="UST Global", skills=["Java"]),
            ],
            pending_reask_count=reask_count,
        )

    async def test_successful_selection_replays_original_message(self, nodes, monkeypatch):
        async def fake_read_state(session, schema, cid):
            return self._pending_conv()
        async def fake_interpret(answer, candidates, client, model):
            return 0
        clear_calls, bind_calls = [], []
        async def fake_clear_pending(session, schema, cid):
            clear_calls.append(cid)
        async def fake_set_binding(session, schema, cid, doc_id, value):
            bind_calls.append((doc_id, value))

        monkeypatch.setattr(conv_state, "read_state", fake_read_state)
        monkeypatch.setattr(conv_state, "clear_pending", fake_clear_pending)
        monkeypatch.setattr(conv_state, "set_binding", fake_set_binding)
        monkeypatch.setattr(entity_resolver, "interpret_selection", fake_interpret)

        state = _base_state(message="The React developer")
        result = await nodes["entity_resolution"](state)

        assert result["entity_resolution_outcome"] == "unique"
        assert result["resolved_document_ids"] == ["doc-1"]
        assert result["message"] == "Tell me about Sreelakshmi"
        assert result["original_message"] == "Tell me about Sreelakshmi"
        assert clear_calls == ["conv-1"]
        assert bind_calls == [("doc-1", "Sreelakshmi R")]

        plan = result["retrieval_plan"]
        semantic = next(e for e in plan.entries if e.capability_name == "semantic_retrieval")
        assert semantic.arguments["query"] == "Tell me about Sreelakshmi"
        assert semantic.arguments["scope"] == {"type": "document", "document_ids": ["doc-1"]}

    async def test_first_unresolvable_answer_reasks(self, nodes, monkeypatch):
        async def fake_read_state(session, schema, cid):
            return self._pending_conv(reask_count=0)
        async def fake_interpret(answer, candidates, client, model):
            return None
        reask_calls = []
        async def fake_increment(session, schema, cid, count):
            reask_calls.append(count)

        monkeypatch.setattr(conv_state, "read_state", fake_read_state)
        monkeypatch.setattr(conv_state, "increment_reask", fake_increment)
        monkeypatch.setattr(entity_resolver, "interpret_selection", fake_interpret)

        state = _base_state(message="I have no idea")
        result = await nodes["entity_resolution"](state)

        assert result["entity_resolution_outcome"] == "ambiguous"
        assert "reply" in result
        assert reask_calls == [0]

    async def test_second_unresolvable_answer_abandons_and_falls_through(self, nodes, monkeypatch):
        async def fake_read_state(session, schema, cid):
            return self._pending_conv(reask_count=1)
        async def fake_interpret(answer, candidates, client, model):
            return None
        clear_calls = []
        async def fake_clear_pending(session, schema, cid):
            clear_calls.append(cid)

        monkeypatch.setattr(conv_state, "read_state", fake_read_state)
        monkeypatch.setattr(conv_state, "clear_pending", fake_clear_pending)
        monkeypatch.setattr(entity_resolver, "interpret_selection", fake_interpret)

        state = _base_state(message="still no idea")
        result = await nodes["entity_resolution"](state)

        assert result["entity_resolution_outcome"] == "unresolved"
        assert "reply" not in result
        assert clear_calls == ["conv-1"]


class TestBindingInheritance:
    """Covers verification.md rows 54-58."""

    async def test_nameless_followup_inherits_binding(self, nodes, monkeypatch):
        async def fake_read_state(session, schema, cid):
            return conv_state.ConversationState(conversation_id=cid, resolved_document_id="doc-1", resolved_entity_value="Sreelakshmi R")
        async def fake_resolve(message, session, schema, tenant_id):
            return ResolutionResult(outcome=entity_resolver.UNRESOLVED, mentions_checked=0)

        monkeypatch.setattr(conv_state, "read_state", fake_read_state)
        monkeypatch.setattr(entity_resolver, "resolve_entity", fake_resolve)

        state = _base_state(message="What technologies has she worked with?")
        result = await nodes["entity_resolution"](state)

        assert result["entity_resolution_outcome"] == "unique"
        assert result["resolved_document_ids"] == ["doc-1"]

    async def test_corpus_wide_question_clears_binding(self, nodes, monkeypatch):
        async def fake_read_state(session, schema, cid):
            return conv_state.ConversationState(conversation_id=cid, resolved_document_id="doc-1", resolved_entity_value="Sreelakshmi R")
        async def fake_resolve(message, session, schema, tenant_id):
            return ResolutionResult(outcome=entity_resolver.UNRESOLVED, mentions_checked=0)
        clear_calls = []
        async def fake_clear_binding(session, schema, cid):
            clear_calls.append(cid)

        monkeypatch.setattr(conv_state, "read_state", fake_read_state)
        monkeypatch.setattr(conv_state, "clear_binding", fake_clear_binding)
        monkeypatch.setattr(entity_resolver, "resolve_entity", fake_resolve)

        state = _base_state(message="How many documents do we have in total?")
        result = await nodes["entity_resolution"](state)

        assert result["entity_resolution_outcome"] == "unresolved"
        assert "retrieval_plan" not in result
        assert clear_calls == ["conv-1"]

    async def test_different_person_replaces_binding(self, nodes, monkeypatch):
        async def fake_read_state(session, schema, cid):
            return conv_state.ConversationState(conversation_id=cid, resolved_document_id="doc-1", resolved_entity_value="Sreelakshmi R")
        async def fake_resolve(message, session, schema, tenant_id):
            return ResolutionResult(outcome=entity_resolver.UNIQUE, mention="Arjun", resolved_document_id="doc-9", resolved_entity_value="Arjun")
        bind_calls = []
        async def fake_set_binding(session, schema, cid, doc_id, value):
            bind_calls.append((doc_id, value))

        monkeypatch.setattr(conv_state, "read_state", fake_read_state)
        monkeypatch.setattr(conv_state, "set_binding", fake_set_binding)
        monkeypatch.setattr(entity_resolver, "resolve_entity", fake_resolve)

        state = _base_state(message="Tell me about Arjun")
        result = await nodes["entity_resolution"](state)

        assert result["resolved_document_ids"] == ["doc-9"]
        assert bind_calls == [("doc-9", "Arjun")]

    async def test_bound_ambiguous_mention_is_not_reclarified(self, nodes, monkeypatch):
        candidates = [
            Candidate(document_id="doc-1", name="Sreelakshmi R", organization="SEO Technologies"),
            Candidate(document_id="doc-2", name="Sreelakshmi P", organization="UST Global"),
        ]
        async def fake_read_state(session, schema, cid):
            return conv_state.ConversationState(conversation_id=cid, resolved_document_id="doc-1", resolved_entity_value="Sreelakshmi R")
        async def fake_resolve(message, session, schema, tenant_id):
            return ResolutionResult(outcome=entity_resolver.AMBIGUOUS, mention="Sreelakshmi R", candidates=candidates)
        store_calls = []
        async def fake_store(*a, **kw):
            store_calls.append((a, kw))

        monkeypatch.setattr(conv_state, "read_state", fake_read_state)
        monkeypatch.setattr(conv_state, "store_pending_clarification", fake_store)
        monkeypatch.setattr(entity_resolver, "resolve_entity", fake_resolve)

        state = _base_state(message="Tell me more about Sreelakshmi R")
        result = await nodes["entity_resolution"](state)

        assert result["entity_resolution_outcome"] == "unique"
        assert result["resolved_document_ids"] == ["doc-1"]
        assert "reply" not in result
        assert store_calls == []


class TestStructuredPostFilter:
    """Covers verification.md rows 51, 52."""

    async def test_foreign_document_rows_dropped_and_idless_rows_retained(self, monkeypatch):
        from unittest.mock import AsyncMock
        from src.shared.retrieval.orchestrator import OrchestrationResult

        orchestrator = RAGOrchestrator.__new__(RAGOrchestrator)
        orchestrator.tool_registry = object()
        orchestrator.retriever = object()
        orchestrator._sql_source = AsyncMock()
        nodes_dict = build_nodes(orchestrator)

        fake_result = OrchestrationResult(
            chunks=[], sql_results=[
                {"document_id": "doc-1", "count": 5},
                {"document_id": "doc-2", "count": 9},
                {"count": 14},
            ],
            retrieval_error=None, sql_error=None, plan_trace=[], plan_truncated=False,
            orchestration_degraded=False, orchestration_stop_reason="plan_executed",
        )

        async def fake_execute_plan(plan, registry, context_factory, budget):
            return fake_result

        import src.chat_api.graph.nodes as nodes_module
        monkeypatch.setattr(nodes_module, "execute_plan", fake_execute_plan)

        state = _base_state()
        state["resolved_document_ids"] = ["doc-1"]
        result = await nodes_dict["retrieval_execution"](state)

        doc_ids_in_results = {r.get("document_id") for r in result["sql_results"]}
        assert doc_ids_in_results == {"doc-1", None}
        assert len(result["sql_results"]) == 2
