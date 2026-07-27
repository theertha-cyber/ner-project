from langgraph.graph import StateGraph, END
from src.chat_api.graph.state import ChatState
from src.chat_api.graph.nodes import build_nodes


def _route_after_guardrail(state: ChatState):
    if "reply" in state:
        return "end"
    return ["sql_retrieval", "retrieval"]


def build_chat_graph(orchestrator):
    """Compiles a StateGraph wired to the given RAGOrchestrator instance's services.
    Topology: guardrail -> (END | [sql_retrieval, retrieval] in parallel) -> ner_enrichment
    -> source_assembly -> prompt_assembly -> generation -> END."""
    nodes = build_nodes(orchestrator)

    graph = StateGraph(ChatState)
    for name, fn in nodes.items():
        graph.add_node(name, fn)

    graph.set_entry_point("guardrail")
    graph.add_conditional_edges(
        "guardrail",
        _route_after_guardrail,
        {"end": END, "sql_retrieval": "sql_retrieval", "retrieval": "retrieval"},
    )
    graph.add_edge("sql_retrieval", "ner_enrichment")
    graph.add_edge("retrieval", "ner_enrichment")
    graph.add_edge("ner_enrichment", "source_assembly")
    graph.add_edge("source_assembly", "prompt_assembly")
    graph.add_edge("prompt_assembly", "generation")
    graph.add_edge("generation", END)

    return graph.compile()
