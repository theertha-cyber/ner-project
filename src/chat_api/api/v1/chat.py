import asyncio
import time
import uuid
import json
import logging
from fastapi import APIRouter, Depends, Request, HTTPException
from src.shared.data_plane_gate import require_data_plane_ready
from fastapi.responses import JSONResponse, StreamingResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError, OperationalError
from sqlalchemy.ext.asyncio import async_sessionmaker
from src.shared.data_plane import DataPlaneNotReady, DataPlaneUnavailable
from src.shared.database import get_resolver
from src.shared.exceptions import NotFoundError
from src.shared.tenant_context import classify_driver_error, record_health_best_effort
from pydantic import ValidationError
from src.chat_api.api.v1.schemas import ChatRequest, ChatResponse, Source, Citation, ConversationSummary, ConversationDetail, MessageResponse, ConversationCreateResponse, ConversationRenameRequest, ConversationRenameResponse, FeedbackCreate, FeedbackOut, RetrievalStatusOut, ExportAvailability, ChartPayload
from src.chat_api.services.chart_tool import ChartFrame
from src.chat_api.services.rag_orchestrator import RAGOrchestrator, STREAM_DONE
from src.chat_api.services.guardrails import GuardrailService
from src.chat_api.services.rate_limiter import rate_limiter, INTERNAL_RATE_LIMIT, INTERNAL_WINDOW
from src.chat_api.services.title_generator import derive_conversation_title
from src.shared.tenant_schema import schema_for_tenant as _schema
from src.chat_api.services.export_rendering import cap_rows, render_csv, render_xlsx

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/chat", tags=["chat"], dependencies=[Depends(require_data_plane_ready)])
orchestrator = RAGOrchestrator()
guardrails = GuardrailService()


def _parse_persisted_source(s) -> Source | Citation:
    # Persisted rows are Citation-shaped for every RAG reply (rag_orchestrator's
    # _enrich_citations always converts Source -> Citation before chat.py writes
    # this column). Citation carries `context_snippet` (the readable chunk text)
    # under a different field name than Source's `chunk_text`; deserializing a
    # Citation-shaped dict as Source silently drops it, leaving only document_id
    # on reload. Distinguish by a field unique to each shape.
    d = s if isinstance(s, dict) else s.model_dump()
    if "context_snippet" in d:
        return Citation(**d)
    return Source(**d)


async def get_session(request: Request) -> AsyncSession:
    """Routed through EngineResolver (ADR-017): a `tenant_owned` tenant's
    conversations and messages live wherever its data plane resolves.

    `SELECT 1` proves the connection is genuinely reachable before this dependency
    yields — engine creation itself is lazy and would otherwise let a request
    through to `chat()`/`chat_stream()` even when the store is actually down,
    which would surface as an unclassified driver exception rather than 503
    `TENANT_DATA_PLANE_UNAVAILABLE` (tenant-data-plane-failure-isolation spec's
    "Chat fails closed during a store outage")."""
    tenant_id = getattr(request.state, "tenant_id", None)
    engine = await get_resolver().resolve(tenant_id)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        try:
            await session.execute(text("SELECT 1"))
        except (DBAPIError, OperationalError, OSError) as exc:
            reason = classify_driver_error(exc)
            await record_health_best_effort(tenant_id, reason)
            raise DataPlaneUnavailable(reason) from exc
        try:
            yield session
        finally:
            await session.close()


def _check_tenant_and_rate_limit(request: Request) -> str:
    """Shared by both `chat()` and `chat_stream()`: raises 403/429 before either
    route does anything else, so a rate-limited or unauthenticated caller of the
    streaming endpoint never has a stream opened at all (chat-response-streaming
    spec: "no event stream SHALL be opened")."""
    tenant_id = getattr(request.state, "tenant_id", None)
    if not tenant_id:
        raise HTTPException(status_code=403, detail="Tenant context not available")

    allowed = rate_limiter.check(f"internal:{tenant_id}", INTERNAL_RATE_LIMIT, INTERNAL_WINDOW)
    if not allowed[0]:
        raise HTTPException(
            status_code=429,
            detail={"code": "RATE_LIMIT_EXCEEDED", "message": "Rate limit exceeded", "retry_after": allowed[3]},
            headers={"Retry-After": str(allowed[3]), "X-RateLimit-Limit": str(INTERNAL_RATE_LIMIT), "X-RateLimit-Remaining": "0", "X-RateLimit-Reset": str(allowed[2])},
        )
    return tenant_id


async def _prepare_conversation(
    session: AsyncSession, schema: str, tenant_id: str, user_id: str | None, body: ChatRequest,
) -> tuple[str, list[dict] | None]:
    """Existence check, history load, title derivation, and new-conversation insert —
    identical for the streaming and non-streaming routes. Returns
    `(conversation_id, conversation_context)`."""
    conversation_id = body.conversation_id
    conversation_context = None

    if conversation_id:
        conv_check = await session.execute(
            text(f"SELECT id, title FROM {schema}.conversations WHERE id = :cid AND user_id = :uid"),
            {"cid": conversation_id, "uid": user_id},
        )
        conv_row = conv_check.fetchone()
        if not conv_row:
            raise NotFoundError("Conversation", conversation_id)

        msg_result = await session.execute(
            text(
                f"SELECT role, content FROM {schema}.chat_messages WHERE conversation_id = :cid "
                "ORDER BY created_at ASC, CASE role WHEN 'user' THEN 0 ELSE 1 END ASC"
            ),
            {"cid": conversation_id},
        )
        conversation_context = [{"role": r.role, "content": r.content} for r in msg_result.fetchall()]

        if not conv_row.title:
            title = derive_conversation_title(body.message)
            await session.execute(
                text(f"UPDATE {schema}.conversations SET title = :title WHERE id = :cid"),
                {"title": title, "cid": conversation_id},
            )
    else:
        conversation_id = str(uuid.uuid4())
        title = derive_conversation_title(body.message)
        await session.execute(
            text(f"INSERT INTO {schema}.conversations (id, tenant_id, user_id, title) VALUES (:id, :tid, :uid, :title)"),
            {"id": conversation_id, "tid": tenant_id, "uid": user_id, "title": title},
        )

    return conversation_id, conversation_context


async def _persist_turn_and_respond(
    session: AsyncSession, schema: str, conversation_id: str, user_message: str,
    reply: str, sources: list[Source | Citation], pending_clarification: dict | None,
    answer_kind: str, model_version: str | None, response_time_ms: int,
    retrieval_status: dict | None = None, sql_results: list[dict] | None = None,
    chart: dict | None = None,
) -> ChatResponse:
    """User row insert, assistant row insert, `updated_at` bump, and commit —
    identical for the streaming and non-streaming routes. Runs once, after the RAG
    pipeline has produced its complete reply, so a streaming turn persists exactly
    the same single user/assistant row pair the non-streaming turn does (design.md
    Decision 5).

    `sql_results` is the full, pre-token-budget structured result for the turn (see
    RAGOrchestrator.execute_with_clarification) — distinct from the
    prompt-budget-truncated subset the LLM actually saw. When structured retrieval
    matched at least one row (`sql_results` truthy — a query that ran but matched
    nothing, e.g. an empty list, offers nothing worth downloading and is treated the
    same as no structured retrieval at all), it is persisted as an export snapshot on
    the assistant row, capped at MAX_EXPORT_ROWS (export-chat-results design.md
    Decision 2; ADR-014).

    `chart` is the validated chart the generation model proposed for this turn, or
    None when it produced none (chat-chart-generation design.md Decision 5). It is
    gated on the same structured-retrieval condition as the export snapshot, so a
    turn with rows can carry both."""
    disclaimer = guardrails.inject_disclaimer()
    sources_data = json.dumps([s.model_dump() for s in sources]) if sources else None
    chart_data = json.dumps(chart) if chart else None
    message_id = str(uuid.uuid4())

    export_rows: list[dict] | None = None
    export_row_count: int | None = None
    if sql_results:
        export_rows = cap_rows(sql_results)
        export_row_count = len(export_rows)

    # created_at is written explicitly with clock_timestamp() rather than relying on
    # the column's NOW() default: NOW() is transaction_timestamp(), so both rows of a
    # turn — inserted in this same transaction — would land on the identical instant
    # and `ORDER BY created_at` could hand the assistant row back before the user row.
    await session.execute(
        text(
            f"INSERT INTO {schema}.chat_messages (id, conversation_id, role, content, sources, created_at) "
            "VALUES (:id, :cid, 'user', :content, NULL, clock_timestamp())"
        ),
        {"id": str(uuid.uuid4()), "cid": conversation_id, "content": user_message},
    )
    await session.execute(
        text(
            f"INSERT INTO {schema}.chat_messages (id, conversation_id, role, content, sources, answer_kind, model_version, response_time_ms, export_rows, export_row_count, chart, created_at) "
            "VALUES (:id, :cid, 'assistant', :content, :sources, :answer_kind, :model_version, :response_time_ms, :export_rows, :export_row_count, :chart, clock_timestamp())"
        ),
        {
            "id": message_id, "cid": conversation_id, "content": reply, "sources": sources_data,
            "answer_kind": answer_kind, "model_version": model_version, "response_time_ms": response_time_ms,
            "export_rows": json.dumps(export_rows, default=str) if export_rows is not None else None,
            "export_row_count": export_row_count,
            "chart": chart_data,
        },
    )
    await session.execute(
        text(f"UPDATE {schema}.conversations SET updated_at = NOW() WHERE id = :cid"),
        {"cid": conversation_id},
    )
    await session.commit()

    return ChatResponse(
        reply=reply,
        sources=sources,
        conversation_id=conversation_id,
        disclaimer=disclaimer,
        pending_clarification=pending_clarification,
        message_id=message_id,
        answer_kind=answer_kind,
        model_version=model_version,
        retrieval_status=RetrievalStatusOut(**retrieval_status) if retrieval_status else None,
        export=ExportAvailability(message_id=message_id, row_count=export_row_count) if export_row_count is not None else None,
        chart=chart,
    )


def _response_payload(response: ChatResponse) -> dict:
    # pending_clarification is additive: omit it entirely from the payload when
    # absent instead of serializing it as null, so existing clients see no change.
    # retrieval_status and export are additive on the same terms — a turn that
    # never reached retrieval, or whose retrieval produced no structured result,
    # omits the key rather than sending null.
    exclude = set()
    if response.pending_clarification is None:
        exclude.add("pending_clarification")
    if response.retrieval_status is None:
        exclude.add("retrieval_status")
    if response.export is None:
        exclude.add("export")
    # chart is additive on the same terms: a turn that produced no chart omits the key
    # rather than sending null, so a client that never looks for one sees no change.
    if response.chart is None:
        exclude.add("chart")
    return response.model_dump(exclude=exclude)


@router.post("", response_model=ChatResponse)
async def chat(
    body: ChatRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    tenant_id = _check_tenant_and_rate_limit(request)
    user_id = getattr(request.state, "user_id", None)
    schema = _schema(tenant_id)

    conversation_id, conversation_context = await _prepare_conversation(session, schema, tenant_id, user_id, body)

    auth_header = request.headers.get("Authorization", "")
    jwt_token = auth_header.removeprefix("Bearer ")
    started_at = time.monotonic()
    reply, sources, pending_clarification, answer_kind, model_version, retrieval_status, sql_results, chart = await orchestrator.execute_with_clarification(
        body.message, session, schema, tenant_id, jwt_token, conversation_context, conversation_id,
    )
    response_time_ms = round((time.monotonic() - started_at) * 1000)

    response = await _persist_turn_and_respond(
        session, schema, conversation_id, body.message, reply, sources,
        pending_clarification, answer_kind, model_version, response_time_ms,
        retrieval_status, sql_results, chart,
    )

    headers = rate_limiter.get_headers(f"internal:{tenant_id}", INTERNAL_RATE_LIMIT, INTERNAL_WINDOW)
    return JSONResponse(content=_response_payload(response), headers=headers)


def _sse_frame(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@router.post("/stream")
async def chat_stream(
    body: ChatRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    """Server-Sent Events sibling of `chat()`. Emits `token` events as the
    generation LLM produces content, then a single `done` event carrying the same
    payload `chat()` returns as JSON, or a single `error` event on failure. See the
    `chat-response-streaming` spec and design.md Decisions 1, 2, 6, 9."""
    tenant_id = _check_tenant_and_rate_limit(request)
    user_id = getattr(request.state, "user_id", None)
    schema = _schema(tenant_id)

    conversation_id, conversation_context = await _prepare_conversation(session, schema, tenant_id, user_id, body)

    auth_header = request.headers.get("Authorization", "")
    jwt_token = auth_header.removeprefix("Bearer ")

    async def event_stream():
        sink: asyncio.Queue = asyncio.Queue()
        started_at = time.monotonic()
        task = asyncio.create_task(
            orchestrator.execute_with_clarification_stream(
                body.message, session, schema, tenant_id, sink, jwt_token, conversation_context, conversation_id,
            )
        )
        try:
            while True:
                item = await sink.get()
                if item is STREAM_DONE:
                    break
                if isinstance(item, ChartFrame):
                    # Reaches the client before the first token because the generation
                    # node puts it on the sink before stage B produces any delta.
                    yield _sse_frame("chart", item.payload)
                    continue
                yield _sse_frame("token", {"delta": item})

            reply, sources, pending_clarification, answer_kind, model_version, retrieval_status, sql_results, chart = await task
        except Exception as e:
            logger.exception("Streaming chat turn failed for tenant_id=%s", tenant_id)
            yield _sse_frame("error", {"code": "GENERATION_FAILED", "message": str(e)})
            return

        response_time_ms = round((time.monotonic() - started_at) * 1000)
        response = await _persist_turn_and_respond(
            session, schema, conversation_id, body.message, reply, sources,
            pending_clarification, answer_kind, model_version, response_time_ms,
            retrieval_status, sql_results, chart,
        )
        yield _sse_frame("done", _response_payload(response))

    headers = rate_limiter.get_headers(f"internal:{tenant_id}", INTERNAL_RATE_LIMIT, INTERNAL_WINDOW)
    headers.update({
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    })
    return StreamingResponse(event_stream(), media_type="text/event-stream", headers=headers)


@router.post("/conversations", status_code=201)
async def create_conversation(
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    tenant_id = getattr(request.state, "tenant_id", None)
    user_id = getattr(request.state, "user_id", None)
    if not tenant_id:
        raise HTTPException(status_code=403, detail="Tenant context not available")

    allowed = rate_limiter.check(f"internal:{tenant_id}", INTERNAL_RATE_LIMIT, INTERNAL_WINDOW)
    if not allowed[0]:
        raise HTTPException(
            status_code=429,
            detail={"code": "RATE_LIMIT_EXCEEDED", "message": "Rate limit exceeded", "retry_after": allowed[3]},
            headers={"Retry-After": str(allowed[3]), "X-RateLimit-Limit": str(INTERNAL_RATE_LIMIT), "X-RateLimit-Remaining": "0", "X-RateLimit-Reset": str(allowed[2])},
        )

    schema = _schema(tenant_id)
    conversation_id = str(uuid.uuid4())
    result = await session.execute(
        text(f"INSERT INTO {schema}.conversations (id, tenant_id, user_id) VALUES (:id, :tid, :uid) RETURNING created_at"),
        {"id": conversation_id, "tid": tenant_id, "uid": user_id},
    )
    created_at = result.fetchone()[0]
    await session.commit()

    headers = rate_limiter.get_headers(f"internal:{tenant_id}", INTERNAL_RATE_LIMIT, INTERNAL_WINDOW)
    return JSONResponse(
        content=ConversationCreateResponse(
            id=conversation_id,
            title=None,
            created_at=str(created_at),
        ).model_dump(),
        status_code=201,
        headers=headers,
    )


@router.get("/conversations", response_model=list[ConversationSummary])
async def list_conversations(
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    tenant_id = getattr(request.state, "tenant_id", None)
    user_id = getattr(request.state, "user_id", None)
    if not tenant_id:
        raise HTTPException(status_code=403, detail="Tenant context not available")

    schema = _schema(tenant_id)
    result = await session.execute(
        text(f"""
            SELECT c.id, c.title, c.created_at, COUNT(m.id) AS message_count
            FROM {schema}.conversations c
            LEFT JOIN {schema}.chat_messages m ON m.conversation_id = c.id
            WHERE c.user_id = :uid
            GROUP BY c.id, c.title, c.created_at
            ORDER BY MAX(m.created_at) DESC NULLS LAST, c.created_at DESC
        """),
        {"uid": user_id},
    )
    rows = result.fetchall()
    return [
        ConversationSummary(id=r.id, title=r.title, created_at=str(r.created_at), message_count=r.message_count)
        for r in rows
    ]


@router.get("/conversations/{conv_id}", response_model=ConversationDetail)
async def get_conversation(
    conv_id: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    tenant_id = getattr(request.state, "tenant_id", None)
    user_id = getattr(request.state, "user_id", None)
    if not tenant_id:
        raise HTTPException(status_code=403, detail="Tenant context not available")

    schema = _schema(tenant_id)
    conv_result = await session.execute(
        text(f"SELECT id, title, created_at FROM {schema}.conversations WHERE id = :cid AND user_id = :uid"),
        {"cid": conv_id, "uid": user_id},
    )
    conv = conv_result.fetchone()
    if not conv:
        raise NotFoundError("Conversation", conv_id)

    msg_result = await session.execute(
        text(f"""
            SELECT m.id, m.role, m.content, m.sources, m.created_at, m.answer_kind, m.model_version,
                   m.export_row_count, m.chart,
                   f.rating AS feedback_rating, f.created_at AS feedback_created_at
            FROM {schema}.chat_messages m
            LEFT JOIN {schema}.chat_message_feedback f ON f.message_id = m.id
            WHERE m.conversation_id = :cid
            -- Turns written before created_at used clock_timestamp() share one
            -- timestamp per turn; the role tiebreak keeps user before assistant.
            ORDER BY m.created_at ASC, CASE m.role WHEN 'user' THEN 0 ELSE 1 END ASC
        """),
        {"cid": conv_id},
    )
    messages = []
    for r in msg_result.fetchall():
        sources_list = []
        if r.sources:
            import json
            try:
                sources_list = [_parse_persisted_source(s) for s in (json.loads(r.sources) if isinstance(r.sources, str) else r.sources)]
            except (json.JSONDecodeError, TypeError):
                pass
        # Rows written before the chart column existed read back as NULL, and a
        # payload that no longer validates is dropped rather than failing the reload.
        chart = None
        if r.role == "assistant" and r.chart:
            import json
            try:
                raw = json.loads(r.chart) if isinstance(r.chart, str) else r.chart
                chart = ChartPayload.model_validate(raw)
            except (json.JSONDecodeError, TypeError, ValidationError):
                pass
        feedback = None
        if r.feedback_rating:
            feedback = FeedbackOut(message_id=r.id, rating=r.feedback_rating, created_at=str(r.feedback_created_at))
        messages.append(MessageResponse(
            id=r.id, role=r.role, content=r.content, sources=sources_list, created_at=str(r.created_at),
            answer_kind=r.answer_kind if r.role == "assistant" else None,
            model_version=r.model_version if r.role == "assistant" else None,
            feedback=feedback,
            export=ExportAvailability(message_id=r.id, row_count=r.export_row_count) if r.export_row_count is not None else None,
            chart=chart,
        ))

    return ConversationDetail(id=conv.id, title=conv.title, created_at=str(conv.created_at), messages=messages)


@router.post("/messages/{message_id}/feedback", status_code=201)
async def submit_message_feedback(
    message_id: str,
    body: FeedbackCreate,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    tenant_id = getattr(request.state, "tenant_id", None)
    user_id = getattr(request.state, "user_id", None)
    role = getattr(request.state, "role", None)
    if not tenant_id:
        raise HTTPException(status_code=403, detail="Tenant context not available")
    if role != "business_user":
        raise HTTPException(status_code=403, detail="Only business users may submit feedback")

    schema = _schema(tenant_id)
    msg_result = await session.execute(
        text(f"SELECT id, role, answer_kind FROM {schema}.chat_messages WHERE id = :mid"),
        {"mid": message_id},
    )
    message = msg_result.fetchone()
    if not message or message.role != "assistant" or message.answer_kind != "answer":
        raise NotFoundError("Message", message_id)

    feedback_id = str(uuid.uuid4())
    try:
        result = await session.execute(
            text(
                f"INSERT INTO {schema}.chat_message_feedback (id, message_id, tenant_id, user_id, rating) "
                "VALUES (:id, :mid, :tid, :uid, :rating) RETURNING created_at"
            ),
            {"id": feedback_id, "mid": message_id, "tid": tenant_id, "uid": user_id, "rating": body.rating},
        )
        created_at = result.fetchone()[0]
        await session.commit()
    except IntegrityError:
        await session.rollback()
        existing = await session.execute(
            text(f"SELECT rating, created_at FROM {schema}.chat_message_feedback WHERE message_id = :mid"),
            {"mid": message_id},
        )
        row = existing.fetchone()
        raise HTTPException(
            status_code=409,
            detail=FeedbackOut(message_id=message_id, rating=row.rating, created_at=str(row.created_at)).model_dump(),
        )

    return JSONResponse(
        content=FeedbackOut(message_id=message_id, rating=body.rating, created_at=str(created_at)).model_dump(),
        status_code=201,
    )


@router.get("/messages/{message_id}/export")
async def export_message(
    message_id: str,
    format: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    """Downloads the structured-result snapshot persisted for an assistant message
    (see `_persist_turn_and_respond`) as CSV or XLSX. Ownership is enforced by
    joining through `conversations.user_id`, mirroring `delete_conversation`'s
    404-on-mismatch pattern — a message in another user's conversation is
    indistinguishable from one that doesn't exist (chat-export capability)."""
    tenant_id = getattr(request.state, "tenant_id", None)
    user_id = getattr(request.state, "user_id", None)
    if not tenant_id:
        raise HTTPException(status_code=403, detail="Tenant context not available")
    if format not in ("csv", "xlsx"):
        raise HTTPException(status_code=422, detail=f"Unsupported export format: '{format}'. Use 'csv' or 'xlsx'.")

    schema = _schema(tenant_id)
    result = await session.execute(
        text(f"""
            SELECT m.export_rows
            FROM {schema}.chat_messages m
            JOIN {schema}.conversations c ON c.id = m.conversation_id
            WHERE m.id = :mid AND c.user_id = :uid
        """),
        {"mid": message_id, "uid": user_id},
    )
    row = result.fetchone()
    if not row or row.export_rows is None:
        raise NotFoundError("Export", message_id)

    rows = row.export_rows if isinstance(row.export_rows, list) else json.loads(row.export_rows)

    if format == "csv":
        body = render_csv(rows)
        media_type = "text/csv"
        filename = f"chat-export-{message_id}.csv"
    else:
        body = render_xlsx(rows)
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        filename = f"chat-export-{message_id}.xlsx"

    return Response(
        content=body,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.patch("/conversations/{conv_id}", response_model=ConversationRenameResponse)
async def rename_conversation(
    conv_id: str,
    body: ConversationRenameRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    tenant_id = getattr(request.state, "tenant_id", None)
    user_id = getattr(request.state, "user_id", None)
    if not tenant_id:
        raise HTTPException(status_code=403, detail="Tenant context not available")

    schema = _schema(tenant_id)
    result = await session.execute(
        text(f"SELECT id FROM {schema}.conversations WHERE id = :cid AND user_id = :uid"),
        {"cid": conv_id, "uid": user_id},
    )
    if not result.fetchone():
        raise NotFoundError("Conversation", conv_id)

    title = body.title
    await session.execute(
        text(f"UPDATE {schema}.conversations SET title = :title WHERE id = :cid"),
        {"title": title, "cid": conv_id},
    )
    await session.commit()

    return ConversationRenameResponse(id=conv_id, title=title)


@router.delete("/conversations/{conv_id}", status_code=204)
async def delete_conversation(
    conv_id: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    tenant_id = getattr(request.state, "tenant_id", None)
    user_id = getattr(request.state, "user_id", None)
    if not tenant_id:
        raise HTTPException(status_code=403, detail="Tenant context not available")

    schema = _schema(tenant_id)
    result = await session.execute(
        text(f"SELECT id FROM {schema}.conversations WHERE id = :cid AND user_id = :uid"),
        {"cid": conv_id, "uid": user_id},
    )
    if not result.fetchone():
        raise NotFoundError("Conversation", conv_id)

    await session.execute(
        text(f"DELETE FROM {schema}.chat_messages WHERE conversation_id = :cid"),
        {"cid": conv_id},
    )
    await session.execute(
        text(f"DELETE FROM {schema}.conversations WHERE id = :cid"),
        {"cid": conv_id},
    )
    await session.commit()
