import uuid
import json
import logging
from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker
from src.shared.database import get_engine
from src.shared.exceptions import NotFoundError
from src.chat_api.api.v1.schemas import ChatRequest, ChatResponse, Source, Citation, ConversationSummary, ConversationDetail, MessageResponse, ConversationCreateResponse, ConversationRenameRequest, ConversationRenameResponse
from src.chat_api.services.rag_orchestrator import RAGOrchestrator
from src.chat_api.services.guardrails import GuardrailService
from src.chat_api.services.rate_limiter import rate_limiter, INTERNAL_RATE_LIMIT, INTERNAL_WINDOW
from src.chat_api.services.title_generator import derive_conversation_title

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])
orchestrator = RAGOrchestrator()
guardrails = GuardrailService()


def _schema(tenant_id: str) -> str:
    return f"tenant_{tenant_id.replace('-', '_')}"


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


async def get_session() -> AsyncSession:
    factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    async with factory() as session:
        try:
            yield session
        finally:
            await session.close()


@router.post("", response_model=ChatResponse)
async def chat(
    body: ChatRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    tenant_id = getattr(request.state, "tenant_id", None)
    user_id = getattr(request.state, "user_id", None)
    role = getattr(request.state, "role", None)

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
            text(f"SELECT role, content FROM {schema}.chat_messages WHERE conversation_id = :cid ORDER BY created_at ASC"),
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

    auth_header = request.headers.get("Authorization", "")
    jwt_token = auth_header.removeprefix("Bearer ")
    reply, sources = await orchestrator.execute(body.message, session, schema, tenant_id, jwt_token, conversation_context)

    disclaimer = guardrails.inject_disclaimer()
    sources_data = json.dumps([s.model_dump() for s in sources]) if sources else None
    message_id = str(uuid.uuid4())
    await session.execute(
        text(f"INSERT INTO {schema}.chat_messages (id, conversation_id, role, content, sources) VALUES (:id, :cid, 'user', :content, NULL)"),
        {"id": str(uuid.uuid4()), "cid": conversation_id, "content": body.message},
    )
    await session.execute(
        text(f"INSERT INTO {schema}.chat_messages (id, conversation_id, role, content, sources) VALUES (:id, :cid, 'assistant', :content, :sources)"),
        {"id": message_id, "cid": conversation_id, "content": reply, "sources": sources_data},
    )
    await session.execute(
        text(f"UPDATE {schema}.conversations SET updated_at = NOW() WHERE id = :cid"),
        {"cid": conversation_id},
    )
    await session.commit()

    headers = rate_limiter.get_headers(f"internal:{tenant_id}", INTERNAL_RATE_LIMIT, INTERNAL_WINDOW)
    return JSONResponse(
        content=ChatResponse(
            reply=reply,
            sources=sources,
            conversation_id=conversation_id,
            disclaimer=disclaimer,
        ).model_dump(),
        headers=headers,
    )


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
        text(f"SELECT id, role, content, sources, created_at FROM {schema}.chat_messages WHERE conversation_id = :cid ORDER BY created_at ASC"),
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
        messages.append(MessageResponse(id=r.id, role=r.role, content=r.content, sources=sources_list, created_at=str(r.created_at)))

    return ConversationDetail(id=conv.id, title=conv.title, created_at=str(conv.created_at), messages=messages)


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
