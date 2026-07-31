from langgraph.graph import StateGraph, END
from src.chat_api.graph.state import ChatState
from src.chat_api.graph.nodes import build_nodes


def _route_after_guardrail(state: ChatState):
    if "reply" in state:
        return "end"
    return "orchestrator"


def build_chat_graph(orchestrator):
    """Compiles the single, fixed chat graph topology:

    guardrail -> (END | orchestrator) -> retrieval_execution -> source_assembly ->
    prompt_assembly -> generation -> END.

    The guardrail decline is the only conditional edge in the graph; there is no
    build-time or runtime setting that selects a different topology."""
    nodes = build_nodes(orchestrator)

    graph = StateGraph(ChatState)
    graph.add_node("guardrail", nodes["guardrail"])
    graph.add_node("orchestrator", nodes["orchestrator"])
    graph.add_node("retrieval_execution", nodes["retrieval_execution"])
    graph.add_node("source_assembly", nodes["source_assembly"])
    graph.add_node("prompt_assembly", nodes["prompt_assembly"])
    graph.add_node("generation", nodes["generation"])

    graph.set_entry_point("guardrail")

    graph.add_conditional_edges(
        "guardrail",
        _route_after_guardrail,
        {"end": END, "orchestrator": "orchestrator"},
    )
    graph.add_edge("orchestrator", "retrieval_execution")
    graph.add_edge("retrieval_execution", "source_assembly")
    graph.add_edge("source_assembly", "prompt_assembly")
    graph.add_edge("prompt_assembly", "generation")
    graph.add_edge("generation", END)

    return graph.compile()
