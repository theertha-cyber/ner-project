import httpx
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse, Response
from src.shared.config import settings

router = APIRouter(prefix="/api/v1", tags=["chat-proxy"])

CHAT_API_BASE = f"http://localhost:{settings.chat_api_port}"


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


@router.get("/chat/conversations")
async def proxy_list_conversations(request: Request):
    return await _proxy("GET", "/api/v1/chat/conversations", request)


@router.get("/chat/conversations/{conv_id}")
async def proxy_get_conversation(conv_id: str, request: Request):
    return await _proxy("GET", f"/api/v1/chat/conversations/{conv_id}", request)


@router.delete("/chat/conversations/{conv_id}")
async def proxy_delete_conversation(conv_id: str, request: Request):
    return await _proxy("DELETE", f"/api/v1/chat/conversations/{conv_id}", request)


@router.post("/widget-keys")
async def proxy_create_widget_key(request: Request):
    return await _proxy("POST", "/api/v1/widget-keys", request)


@router.get("/widget-keys")
async def proxy_list_widget_keys(request: Request):
    return await _proxy("GET", "/api/v1/widget-keys", request)


@router.delete("/widget-keys/{key_id}")
async def proxy_revoke_widget_key(key_id: str, request: Request):
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
