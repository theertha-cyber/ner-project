from langgraph.graph import StateGraph, END
from src.shared.config import settings
from src.chat_api.graph.state import ChatState
from src.chat_api.graph.nodes import build_nodes


def _route_after_guardrail(state: ChatState):
    if "reply" in state:
        return "end"
    return "orchestrator"


def _route_after_entity_resolution(state: ChatState):
    if "reply" in state:
        return "end"
    return "retrieval_execution"


def build_chat_graph(orchestrator):
    """Compiles the chat graph topology. With `entity_resolution_enabled` off (the
    default):

    guardrail -> (END | orchestrator) -> retrieval_execution -> prompt_assembly ->
    source_assembly -> generation -> END.

    `prompt_assembly` runs before `source_assembly` so citations are derived from the
    evidence the prompt actually admitted. The two stages previously guessed
    independently — `[:3]` in one, `[:5]` and a budget loop in the other — and
    disagreed in both directions, including citing a structured block the prompt had
    dropped whole. The node set and both routing predicates are unchanged, and
    `generation` still reads the `sources` that `source_assembly` writes immediately
    before it.

    With the flag on, one additional node and one additional conditional edge are
    inserted between `orchestrator` and `retrieval_execution`:

    orchestrator -> entity_resolution -> (END | retrieval_execution) -> ...

    The routing decision at both conditional edges is a pure function of state
    (whether a terminal `reply` is already present), never of an LLM's choice of
    next node — see design.md Decision 1 and the `chat-orchestration-graph` delta
    spec's "Routing is not model-decided" requirement."""
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

    if settings.entity_resolution_enabled:
        graph.add_node("entity_resolution", nodes["entity_resolution"])
        graph.add_edge("orchestrator", "entity_resolution")
        graph.add_conditional_edges(
            "entity_resolution",
            _route_after_entity_resolution,
            {"end": END, "retrieval_execution": "retrieval_execution"},
        )
    else:
        graph.add_edge("orchestrator", "retrieval_execution")

    graph.add_edge("retrieval_execution", "prompt_assembly")
    graph.add_edge("prompt_assembly", "source_assembly")
    graph.add_edge("source_assembly", "generation")
    graph.add_edge("generation", END)

    return graph.compile()
