import httpx
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
from src.shared.config import settings

router = APIRouter(prefix="/api/v1", tags=["analytics-proxy"])

ANALYTICS_BASE = settings.analytics_service_url


async def _proxy(method: str, path: str, request: Request, body: dict | None = None):
    url = f"{ANALYTICS_BASE}{path}"
    headers = dict(request.headers)
    headers.pop("host", None)
    headers.pop("content-length", None)

    async with httpx.AsyncClient(timeout=60) as client:
        if method == "GET":
            resp = await client.get(url, headers=headers, params=dict(request.query_params))
        elif method == "POST":
            resp = await client.post(url, headers=headers, json=body or {})
        else:
            raise HTTPException(status_code=405, detail="Method not allowed")

        return JSONResponse(
            status_code=resp.status_code,
            content=resp.json() if resp.text else {},
        )


@router.post("/analytics/query")
async def proxy_analytics_query(request: Request):
    body = await request.json() if request.headers.get("content-type") == "application/json" else None
    return await _proxy("POST", "/api/v1/analytics/query", request, body)


@router.get("/analytics/dashboard")
async def proxy_analytics_dashboard(request: Request):
    return await _proxy("GET", "/api/v1/analytics/dashboard", request)


@router.post("/analytics/export")
async def proxy_analytics_export(request: Request):
    body = await request.json() if request.headers.get("content-type") == "application/json" else None
    return await _proxy("POST", "/api/v1/analytics/export", request, body)


@router.post("/analytics/refresh")
async def proxy_analytics_refresh(request: Request):
    return await _proxy("POST", "/api/v1/analytics/refresh", request)
