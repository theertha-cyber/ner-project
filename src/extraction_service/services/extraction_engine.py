from fastapi import Request
import httpx
from src.shared.config import settings


def _infer_url() -> str:
    base = settings.model_serving_url.rstrip("/")
    return f"{base}/internal/v1/infer"


async def infer(tenant_id: str, tokens: list[str], request: Request) -> dict | None:
    url = _infer_url()
    auth_header = request.headers.get("Authorization")
    headers = {"Authorization": auth_header} if auth_header else {}
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, json={"tokens": tokens}, headers=headers)
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return resp.json()
    except httpx.RequestError:
        return None
