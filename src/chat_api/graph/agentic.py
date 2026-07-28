"""Chat-side entry point for the bounded agentic retrieval loop. The loop core has
no chat_api-specific dependencies (it only depends on src.shared.retrieval), so it
lives in src.shared.retrieval.agentic_loop where the eval harness can reach it
without importing src.chat_api (ADR-005). This module re-exports it for
src/chat_api/graph/nodes.py."""
from src.shared.retrieval.agentic_loop import (
    STOP_DEADLINE,
    STOP_ITERATION_CAP,
    STOP_MALFORMED_CALLS,
    STOP_PLANNER_ERROR,
    STOP_PLANNER_STOP,
    STOP_TOOL_CALL_CAP,
    AgenticLoopResult,
    LoopBudget,
    run_agentic_loop,
)

__all__ = [
    "STOP_DEADLINE", "STOP_ITERATION_CAP", "STOP_MALFORMED_CALLS", "STOP_PLANNER_ERROR",
    "STOP_PLANNER_STOP", "STOP_TOOL_CALL_CAP", "AgenticLoopResult", "LoopBudget", "run_agentic_loop",
]
