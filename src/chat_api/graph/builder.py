from langgraph.graph import StateGraph, END
from src.shared.config import settings
from src.chat_api.graph.state import ChatState
from src.chat_api.graph.nodes import build_nodes


def _route_after_guardrail(state: ChatState):
    if "reply" in state:
        return "end"
    return ["sql_retrieval", "retrieval"]


def _route_after_guardrail_agentic(state: ChatState):
    if "reply" in state:
        return "end"
    return "agentic_retrieval"


def build_chat_graph(orchestrator):
    """Compiles a StateGraph wired to the given RAGOrchestrator instance's services.

    Flag-off topology (chat_agentic_retrieval=False, the default): guardrail ->
    (END | [sql_retrieval, retrieval] in parallel) -> ner_enrichment -> source_assembly
    -> prompt_assembly -> generation -> END. Identical to the pre-agentic-loop graph;
    the agentic node is not registered and is unreachable.

    Flag-on topology: guardrail -> (END | agentic_retrieval) -> ner_enrichment ->
    source_assembly -> prompt_assembly -> generation -> END. The agentic node's
    internal plan/observe cycle is not expressed as graph edges, so the graph
    itself remains acyclic in both cases."""
    nodes = build_nodes(orchestrator)
    agentic_enabled = settings.chat_agentic_retrieval

    graph = StateGraph(ChatState)
    graph.add_node("guardrail", nodes["guardrail"])
    if agentic_enabled:
        graph.add_node("agentic_retrieval", nodes["agentic_retrieval"])
    else:
        graph.add_node("sql_retrieval", nodes["sql_retrieval"])
        graph.add_node("retrieval", nodes["retrieval"])
    graph.add_node("ner_enrichment", nodes["ner_enrichment"])
    graph.add_node("source_assembly", nodes["source_assembly"])
    graph.add_node("prompt_assembly", nodes["prompt_assembly"])
    graph.add_node("generation", nodes["generation"])

    graph.set_entry_point("guardrail")

    if agentic_enabled:
        graph.add_conditional_edges(
            "guardrail",
            _route_after_guardrail_agentic,
            {"end": END, "agentic_retrieval": "agentic_retrieval"},
        )
        graph.add_edge("agentic_retrieval", "ner_enrichment")
    else:
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
