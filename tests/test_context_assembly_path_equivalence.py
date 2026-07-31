import pytest

from src.chat_api.graph.nodes import build_nodes
from src.chat_api.services.context_assembler import ContextAssembler
from src.shared.retrieval.models import RetrievalResult

pytestmark = [pytest.mark.verification, pytest.mark.asyncio]


class _StubOrchestrator:
    pass


def _make_chunk(document_id, chunk_index, text, page_number=None):
    return RetrievalResult(
        document_id=document_id,
        chunk_index=chunk_index,
        chunk_text=text,
        similarity_score=0.9,
        page_number=page_number,
    )


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

    nodes = build_nodes(_StubOrchestrator())
    state = {
        "message": message,
        "sql_results": sql_results,
        "chunks": chunks,
        "document_names": document_names,
        "conversation_context": conversation_context,
    }
    graph_result = await nodes["prompt_assembly"](state)

    direct_messages = ContextAssembler().assemble(
        message, sql_results, chunks, document_names, conversation_context,
    )

    assert graph_result["prompt_messages"] == direct_messages
