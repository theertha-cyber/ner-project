import httpx
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
from src.shared.config import settings

router = APIRouter(prefix="/api/v1", tags=["extraction-proxy"])

EXTRACTION_BASE = settings.extraction_service_url


async def _proxy(method: str, path: str, request: Request, body: dict | None = None):
    url = f"{EXTRACTION_BASE}{path}"
    headers = dict(request.headers)
    headers.pop("host", None)
    headers.pop("content-length", None)

    async with httpx.AsyncClient(timeout=60) as client:
        if method == "GET":
            resp = await client.get(url, headers=headers, params=dict(request.query_params))
        elif method == "POST":
            resp = await client.post(url, headers=headers, json=body or {})
        elif method == "PATCH":
            resp = await client.patch(url, headers=headers, json=body or {})
        else:
            raise HTTPException(status_code=405, detail="Method not allowed")

        return JSONResponse(
            status_code=resp.status_code,
            content=resp.json() if resp.text else {},
        )


@router.post("/extract")
async def proxy_extract(request: Request):
    body = await request.json() if request.headers.get("content-type") == "application/json" else None
    return await _proxy("POST", "/api/v1/extract", request, body)


@router.post("/extract-batch")
async def proxy_batch(request: Request):
    body = await request.json() if request.headers.get("content-type") == "application/json" else None
    return await _proxy("POST", "/api/v1/extract-batch", request, body)


@router.get("/extract-batch/{run_id}")
async def proxy_batch_status(run_id: str, request: Request):
    return await _proxy("GET", f"/api/v1/extract-batch/{run_id}", request)


@router.get("/entities")
async def proxy_list_entities(request: Request):
    return await _proxy("GET", "/api/v1/entities", request)


@router.patch("/entities/{entity_id}")
async def proxy_patch_entity(entity_id: str, request: Request):
    body = await request.json()
    return await _proxy("PATCH", f"/api/v1/entities/{entity_id}", request, body)
