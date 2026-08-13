import asyncio
from typing import TypedDict
from sqlalchemy.ext.asyncio import AsyncSession
from src.chat_api.api.v1.schemas import Source, Citation
from src.chat_api.services.context_assembler import AdmittedEvidence
from src.shared.retrieval.models import RetrievalResult
from src.shared.retrieval.orchestrator import RetrievalPlan, RetrievalStatus


class ChatState(TypedDict, total=False):
    # inputs — set once by the adapter. `message` is the one exception: when entity
    # resolution resumes a clarified turn, entity_resolution_node overwrites it with
    # `original_message` so every downstream node (which reads only `message`) answers
    # the original request without any node-by-node change.
    message: str
    tenant_id: str
    schema: str
    jwt_token: str | None
    conversation_context: list[dict] | None
    conversation_id: str | None

    # runtime context — not serializable, excluded from any future checkpointer
    session: AsyncSession

    # optional token sink for streaming delivery (chat-response-token-streaming).
    # Present only when the caller wants incremental delivery; only `generation_node`
    # reads it. Absent (or None), the graph behaves exactly as the non-streaming path.
    token_sink: asyncio.Queue | None

    # guardrail outcome
    blocked_reason: str | None

    # orchestrator outcome
    retrieval_plan: RetrievalPlan

    # entity resolution outcome (present only when entity_resolution_enabled)
    entity_resolution_outcome: str | None
    resolved_document_ids: list[str]
    pending_clarification: dict | None
    original_message: str | None

    # stage outputs
    sql_results: list[dict] | None
    chunks: list[RetrievalResult]

    # `{"returned": int, "matched": int | None, "truncated": bool}` for the structured
    # rows above, so prompt assembly can tell a complete answer from the first page of
    # a longer one and stop asserting a truncated list is exhaustive.
    sql_completeness: dict | None

    # The turn's retrieval outcome, one entry per plan entry. Replaces `sql_error` and
    # `retrieval_error`, which were written here every turn and read nowhere: they
    # could not express partial failure, and they replaced the specific error text
    # with a fixed string. Read by prompt_assembly_node (rendered into the prompt),
    # by the guardrail (empty vs failed), and by the HTTP response.
    retrieval_status: RetrievalStatus | None

    # orchestration trace (additive; absent when the turn was declined by the guardrail)
    plan_trace: list[dict]
    orchestration_degraded: bool
    orchestration_stop_reason: str

    # assembly. `prompt_assembly` runs first and reports what it admitted; citations
    # are derived from that, so the evidence shown to the user and the evidence the
    # answer was written from are the same set.
    prompt_messages: list[dict]
    document_names: dict[str, str]
    admitted_evidence: AdmittedEvidence | None
    sources: list[Source | Citation]

    # terminal
    reply: str
