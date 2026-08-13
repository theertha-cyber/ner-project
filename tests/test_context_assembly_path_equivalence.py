import pytest

from src.chat_api.api.v1.schemas import Source
from src.chat_api.graph.nodes import build_nodes
from src.chat_api.services.context_assembler import ContextAssembler
from src.shared.retrieval.models import RetrievalResult

pytestmark = [pytest.mark.verification, pytest.mark.asyncio]


class _StubOrchestrator:
    """Stands in for RAGOrchestrator's two DB-touching helpers. `prompt_assembly`
    resolves document names now (it needs them for its chunk labels), and
    `source_assembly` enriches whatever citations it was handed."""

    def __init__(self, document_names=None):
        self.document_names = document_names or {}

    async def _resolve_document_names(self, sources, session, schema):
        return dict(self.document_names)

    async def _enrich_citations(self, sources, session, schema, tenant_id, document_names=None):
        return list(sources)


def _make_chunk(document_id, chunk_index, text, page_number=None):
    return RetrievalResult(
        document_id=document_id,
        chunk_index=chunk_index,
        chunk_text=text,
        similarity_score=0.9,
        page_number=page_number,
    )


def _state(**overrides):
    state = {
        "message": "What organizations were mentioned?",
        "sql_results": None,
        "chunks": [],
        "conversation_context": None,
        "tenant_id": "t1",
        "schema": "tenant_t1",
        "session": object(),
    }
    state.update(overrides)
    return state


async def test_graph_path_matches_direct_assembler_call():
    """Covers scenario 13: task 6.5.

    Both execution paths delegate to ContextAssembler with the same inputs; this
    asserts the graph path's prompt_assembly_node produces exactly what a direct
    ContextAssembler.assemble call produces for identical inputs.
    """
    message = "What organizations were mentioned?"
    sql_results = [{"entity_type": "ORG", "count": 3}]
    chunks = [_make_chunk("doc-1", 0, "Acme Corp signed a contract.", page_number=1)]
    document_names = {"doc-1": "report.pdf"}
    conversation_context = [{"role": "user", "content": "Hi"}, {"role": "assistant", "content": "Hello"}]

    nodes = build_nodes(_StubOrchestrator(document_names))
    graph_result = await nodes["prompt_assembly"](_state(
        message=message, sql_results=sql_results, chunks=chunks,
        conversation_context=conversation_context,
    ))

    direct_messages = ContextAssembler().assemble(
        message, sql_results, chunks, document_names, conversation_context,
    )

    assert graph_result["prompt_messages"] == direct_messages


class TestCitationsDeriveFromAdmittedEvidence:
    """verification.md rows 71, 72, 73.

    `source_assembly` used to slice chunks at a hardcoded `[:3]` and re-serialise
    `sql_results[:5]` on its own, while the assembler admitted a different set under a
    token budget — so the citations and the evidence disagreed in both directions, and
    a 7,944-token structured block was measured disappearing from the prompt with its
    citation still attached."""

    async def _run(self, orchestrator, **state_overrides):
        nodes = build_nodes(orchestrator)
        state = _state(**state_overrides)
        state.update(await nodes["prompt_assembly"](state))
        state.update(await nodes["source_assembly"](state))
        return state

    async def test_no_structured_citation_when_block_absent(self):
        state = await self._run(_StubOrchestrator(), sql_results=None,
                                chunks=[_make_chunk("doc-1", 0, "text")])

        assert [s.source_type for s in state["sources"]] == ["document_chunk"]
        assert not any(s.source_type == "sql" for s in state["sources"])

    async def test_citations_cover_every_admitted_chunk(self):
        chunks = [_make_chunk(f"doc-{i}", 0, f"chunk {i}") for i in range(5)]
        state = await self._run(_StubOrchestrator(), chunks=chunks)

        admitted = state["admitted_evidence"].chunks
        assert len(admitted) == 5
        cited = [s for s in state["sources"] if s.source_type == "document_chunk"]
        # No cap unrelated to prompt admission reduces this — the old `[:3]` did.
        assert len(cited) == len(admitted)
        assert {s.document_id for s in cited} == {c.document_id for c in admitted}

    async def test_structured_citation_matches_admitted_subset(self):
        rows = [{"entity_value": f"value-{i}" * 60} for i in range(40)]
        nodes = build_nodes(_StubOrchestrator())
        state = _state(sql_results=rows, sql_completeness={"returned": 40, "matched": 142, "truncated": True})

        # A tight budget forces the assembler to truncate the block.
        import src.chat_api.graph.nodes as nodes_module
        original = nodes_module.ContextAssembler
        nodes_module.ContextAssembler = lambda: original(token_budget=900, max_chunks=5)
        try:
            state.update(await nodes["prompt_assembly"](state))
            state.update(await nodes["source_assembly"](state))
        finally:
            nodes_module.ContextAssembler = original

        admitted = state["admitted_evidence"]
        assert admitted.rows_truncated
        assert 0 < len(admitted.rows) < len(rows)

        sql_citation = next(s for s in state["sources"] if s.source_type == "sql")
        import json
        assert json.loads(sql_citation.value) == admitted.rows
        # The prompt says the underlying result was larger.
        assert "PARTIAL" in state["prompt_messages"][-1]["content"]
        assert "142" in state["prompt_messages"][-1]["content"]
