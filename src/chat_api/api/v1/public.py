import uuid
import logging
from fastapi import APIRouter, Depends, Request, HTTPException, Query
from fastapi.responses import JSONResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker
from src.shared.database import get_engine
from src.chat_api.api.v1.schemas import WidgetChatRequest, WidgetChatResponse, Source
from src.chat_api.services.rag_orchestrator import RAGOrchestrator
from src.chat_api.services.guardrails import GuardrailService
from src.chat_api.services.rate_limiter import rate_limiter, WIDGET_RATE_LIMIT, WIDGET_WINDOW

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/public", tags=["public"])
orchestrator = RAGOrchestrator()
guardrails = GuardrailService()


def _schema(tenant_id: str) -> str:
    return f"tenant_{tenant_id.replace('-', '_')}"


async def get_session() -> AsyncSession:
    factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    async with factory() as session:
        try:
            yield session
        finally:
            await session.close()


@router.get("/widget.js")
async def serve_widget_js(
    tenant: str = Query(..., description="Tenant slug"),
    request: Request = None,
):
    js_code = f"""(function() {{
    'use strict';
    var tenantSlug = '{tenant}';
    var apiBaseUrl = window.location.origin + '/api/v1/public';
    var apiKey = null;

    var widgetContainer = document.createElement('div');
    widgetContainer.id = 'ner-widget-container';
    widgetContainer.innerHTML = `
        <style>
            #ner-widget-container {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }}
            .ner-chat-bubble {{ position: fixed; bottom: 20px; right: 20px; width: 60px; height: 60px; border-radius: 50%; background: #2563eb; color: white; border: none; cursor: pointer; box-shadow: 0 4px 12px rgba(0,0,0,0.2); z-index: 999999; font-size: 28px; display: flex; align-items: center; justify-content: center; transition: transform 0.2s; }}
            .ner-chat-bubble:hover {{ transform: scale(1.1); }}
            .ner-chat-panel {{ position: fixed; bottom: 90px; right: 20px; width: 360px; height: 520px; background: white; border-radius: 12px; box-shadow: 0 8px 32px rgba(0,0,0,0.15); z-index: 999998; display: none; flex-direction: column; overflow: hidden; }}
            .ner-chat-panel.open {{ display: flex; }}
            .ner-chat-header {{ background: #2563eb; color: white; padding: 14px 16px; font-weight: 600; font-size: 15px; }}
            .ner-chat-messages {{ flex: 1; overflow-y: auto; padding: 12px; }}
            .ner-chat-input-area {{ border-top: 1px solid #e5e7eb; padding: 10px; display: flex; gap: 8px; background: #f9fafb; }}
            .ner-chat-input {{ flex: 1; border: 1px solid #d1d5db; border-radius: 8px; padding: 10px 12px; font-size: 14px; outline: none; }}
            .ner-chat-input:focus {{ border-color: #2563eb; }}
            .ner-chat-send {{ background: #2563eb; color: white; border: none; border-radius: 8px; padding: 10px 16px; cursor: pointer; font-size: 14px; }}
            .ner-chat-send:hover {{ background: #1d4ed8; }}
            .ner-message {{ margin-bottom: 12px; }}
            .ner-message-user {{ text-align: right; }}
            .ner-message-assistant {{ text-align: left; }}
            .ner-message-bubble {{ display: inline-block; padding: 10px 14px; border-radius: 12px; max-width: 85%; font-size: 14px; line-height: 1.4; }}
            .ner-message-user .ner-message-bubble {{ background: #2563eb; color: white; border-bottom-right-radius: 4px; }}
            .ner-message-assistant .ner-message-bubble {{ background: #f3f4f6; color: #111827; border-bottom-left-radius: 4px; }}
            .ner-loading {{ text-align: center; padding: 8px; color: #9ca3af; font-size: 13px; }}
            .ner-disclaimer {{ font-size: 11px; color: #9ca3af; padding: 8px 12px; text-align: center; border-top: 1px solid #e5e7eb; }}
        </style>
        <button class="ner-chat-bubble" id="ner-chat-bubble">💬</button>
        <div class="ner-chat-panel" id="ner-chat-panel">
            <div class="ner-chat-header">NER Assistant</div>
            <div class="ner-chat-messages" id="ner-chat-messages"></div>
            <div class="ner-chat-input-area">
                <input class="ner-chat-input" id="ner-chat-input" placeholder="Type your question..." />
                <button class="ner-chat-send" id="ner-chat-send">Send</button>
            </div>
            <div class="ner-disclaimer">Answers are AI-generated. Verify against source documents.</div>
        </div>
    `;
    document.body.appendChild(widgetContainer);

    var bubble = document.getElementById('ner-chat-bubble');
    var panel = document.getElementById('ner-chat-panel');
    var messages = document.getElementById('ner-chat-messages');
    var input = document.getElementById('ner-chat-input');
    var sendBtn = document.getElementById('ner-chat-send');

    bubble.onclick = function() {{
        panel.classList.toggle('open');
        if (panel.classList.contains('open')) input.focus();
    }};

    function addMessage(role, content) {{
        var div = document.createElement('div');
        div.className = 'ner-message ner-message-' + role;
        div.innerHTML = '<div class="ner-message-bubble">' + content + '</div>';
        messages.appendChild(div);
        messages.scrollTop = messages.scrollHeight;
    }}

    async function sendMessage() {{
        var text = input.value.trim();
        if (!text) return;
        input.value = '';
        addMessage('user', text);
        var loading = document.createElement('div');
        loading.className = 'ner-loading';
        loading.id = 'ner-loading';
        loading.textContent = 'Thinking...';
        messages.appendChild(loading);
        messages.scrollTop = messages.scrollHeight;

        try {{
            var resp = await fetch(apiBaseUrl + '/chat', {{
                method: 'POST',
                headers: {{ 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + apiKey }},
                body: JSON.stringify({{ message: text }})
            }});
            var data = await resp.json();
            var loadingEl = document.getElementById('ner-loading');
            if (loadingEl) loadingEl.remove();
            if (resp.ok) {{
                addMessage('assistant', data.reply || 'No response');
            }} else {{
                addMessage('assistant', 'Error: ' + (data.error?.message || 'Request failed'));
            }}
        }} catch(e) {{
            var loadingEl = document.getElementById('ner-loading');
            if (loadingEl) loadingEl.remove();
            addMessage('assistant', 'Connection error. Please try again.');
        }}
    }}

    sendBtn.onclick = sendMessage;
    input.onkeypress = function(e) {{ if (e.key === 'Enter') sendMessage(); }};

    addMessage('assistant', 'Hello! I can help you explore your extracted entities and document data. Ask me anything!');
}})();
"""
    return Response(content=js_code, media_type="application/javascript", headers={
        "Access-Control-Allow-Origin": "*",
        "Content-Type": "application/javascript",
    })


@router.options("/chat")
async def widget_chat_preflight():
    return Response(
        status_code=204,
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "Authorization, Content-Type",
            "Access-Control-Max-Age": "86400",
        },
    )


@router.post("/chat", response_model=WidgetChatResponse)
async def widget_chat(
    body: WidgetChatRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    tenant_id = getattr(request.state, "tenant_id", None)
    if not tenant_id:
        raise HTTPException(status_code=401, detail="Authentication required")

    allowed = rate_limiter.check(f"widget:{tenant_id}", WIDGET_RATE_LIMIT, WIDGET_WINDOW)
    if not allowed[0]:
        raise HTTPException(
            status_code=429,
            detail={"code": "RATE_LIMIT_EXCEEDED", "message": "Rate limit exceeded"},
            headers={"Retry-After": str(allowed[3])},
        )

    schema = _schema(tenant_id)
    reply, sources = await orchestrator.execute(body.message, session, schema, tenant_id)
    disclaimer = guardrails.inject_disclaimer()

    headers = rate_limiter.get_headers(f"widget:{tenant_id}", WIDGET_RATE_LIMIT, WIDGET_WINDOW)
    return JSONResponse(
        content=WidgetChatResponse(reply=reply, sources=sources, disclaimer=disclaimer).model_dump(),
        headers=headers,
    )
