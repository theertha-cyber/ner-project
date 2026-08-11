import httpx
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse, Response, StreamingResponse
from src.shared.config import settings

router = APIRouter(prefix="/api/v1", tags=["chat-proxy"])

CHAT_API_BASE = settings.chat_api_url


async def _proxy(method: str, path: str, request: Request):
    url = f"{CHAT_API_BASE}{path}"
    headers = dict(request.headers)
    headers.pop("host", None)
    headers.pop("content-length", None)

    body = None
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        try:
            body = await request.json()
        except Exception:
            body = None

    async with httpx.AsyncClient(timeout=120) as client:
        if method == "GET":
            resp = await client.get(url, headers=headers, params=dict(request.query_params))
        elif method == "POST":
            resp = await client.post(url, headers=headers, json=body)
        elif method == "PATCH":
            resp = await client.patch(url, headers=headers, json=body)
        elif method == "DELETE":
            resp = await client.delete(url, headers=headers)
        elif method == "OPTIONS":
            resp = await client.options(url, headers=headers)
        else:
            raise HTTPException(status_code=405, detail="Method not allowed")

        content = resp.json() if resp.text else {}
        return JSONResponse(status_code=resp.status_code, content=content, headers=dict(resp.headers))


@router.post("/chat")
async def proxy_chat(request: Request):
    return await _proxy("POST", "/api/v1/chat", request)


@router.post("/chat/stream")
async def proxy_chat_stream(request: Request):
    """Pass-through streaming proxy for `/api/v1/chat/stream`. Unlike `_proxy`
    (`resp.json()` + `async with httpx.AsyncClient(...)`, both of which force the
    whole upstream body to be buffered before anything is returned), this opens the
    upstream request with `client.stream(...)` and forwards each chunk to the
    downstream client as it arrives. The `httpx.AsyncClient` is kept open — closed
    only once the response generator itself finishes — rather than being closed
    when this function returns, which is what would happen with `_proxy`'s
    `async with` pattern and would truncate the stream. See design.md Decision 6."""
    url = f"{CHAT_API_BASE}/api/v1/chat/stream"
    headers = dict(request.headers)
    headers.pop("host", None)
    headers.pop("content-length", None)
    body = await request.body()

    client = httpx.AsyncClient(timeout=None)
    req = client.build_request("POST", url, headers=headers, content=body)
    upstream = await client.send(req, stream=True)

    async def event_stream():
        try:
            async for chunk in upstream.aiter_raw():
                yield chunk
        finally:
            await upstream.aclose()
            await client.aclose()

    response_headers = dict(upstream.headers)
    response_headers.pop("content-length", None)
    response_headers["Cache-Control"] = "no-cache"
    response_headers["X-Accel-Buffering"] = "no"

    return StreamingResponse(
        event_stream(),
        status_code=upstream.status_code,
        media_type=upstream.headers.get("content-type", "text/event-stream"),
        headers=response_headers,
    )


@router.post("/chat/conversations")
async def proxy_create_conversation(request: Request):
    return await _proxy("POST", "/api/v1/chat/conversations", request)


@router.get("/chat/conversations")
async def proxy_list_conversations(request: Request):
    return await _proxy("GET", "/api/v1/chat/conversations", request)


@router.get("/chat/conversations/{conv_id}")
async def proxy_get_conversation(conv_id: str, request: Request):
    return await _proxy("GET", f"/api/v1/chat/conversations/{conv_id}", request)


@router.patch("/chat/conversations/{conv_id}")
async def proxy_rename_conversation(conv_id: str, request: Request):
    return await _proxy("PATCH", f"/api/v1/chat/conversations/{conv_id}", request)


@router.delete("/chat/conversations/{conv_id}")
async def proxy_delete_conversation(conv_id: str, request: Request):
    return await _proxy("DELETE", f"/api/v1/chat/conversations/{conv_id}", request)


@router.post("/chat/messages/{message_id}/feedback")
async def proxy_submit_message_feedback(message_id: str, request: Request):
    return await _proxy("POST", f"/api/v1/chat/messages/{message_id}/feedback", request)


@router.post("/tenants/{tenant_slug}/widget-keys")
async def proxy_create_widget_key(tenant_slug: str, request: Request):
    return await _proxy("POST", "/api/v1/widget-keys", request)


@router.get("/tenants/{tenant_slug}/widget-keys")
async def proxy_list_widget_keys(tenant_slug: str, request: Request):
    return await _proxy("GET", "/api/v1/widget-keys", request)


@router.delete("/tenants/{tenant_slug}/widget-keys/{key_id}")
async def proxy_revoke_widget_key(tenant_slug: str, key_id: str, request: Request):
    return await _proxy("DELETE", f"/api/v1/widget-keys/{key_id}", request)


@router.get("/public/widget.js")
async def proxy_widget_js(request: Request):
    url = f"{CHAT_API_BASE}/api/v1/public/widget.js?{request.query_params}"
    headers = dict(request.headers)
    headers.pop("host", None)
    headers.pop("content-length", None)
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url, headers=headers)
        return Response(content=resp.content, status_code=resp.status_code, headers=dict(resp.headers))


@router.post("/public/chat")
async def proxy_widget_chat(request: Request):
    return await _proxy("POST", "/api/v1/public/chat", request)


@router.options("/public/chat")
async def proxy_widget_chat_preflight(request: Request):
    return await _proxy("OPTIONS", "/api/v1/public/chat", request)
