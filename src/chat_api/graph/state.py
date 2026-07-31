from typing import TypedDict
from sqlalchemy.ext.asyncio import AsyncSession
from src.chat_api.api.v1.schemas import Source, Citation
from src.shared.retrieval.models import RetrievalResult
from src.shared.retrieval.orchestrator import RetrievalPlan


class ChatState(TypedDict, total=False):
    # inputs — set once by the adapter, never mutated
    message: str
    tenant_id: str
    schema: str
    jwt_token: str | None
    conversation_context: list[dict] | None

    # runtime context — not serializable, excluded from any future checkpointer
    session: AsyncSession

    # guardrail outcome
    blocked_reason: str | None

    # orchestrator outcome
    retrieval_plan: RetrievalPlan

    # stage outputs
    sql_results: list[dict] | None
    sql_error: str | None
    chunks: list[RetrievalResult]
    retrieval_error: str | None

    # orchestration trace (additive; absent when the turn was declined by the guardrail)
    plan_trace: list[dict]
    orchestration_degraded: bool
    orchestration_stop_reason: str

    # assembly
    sources: list[Source | Citation]
    document_names: dict[str, str]
    prompt_messages: list[dict]

    # terminal
    reply: str
