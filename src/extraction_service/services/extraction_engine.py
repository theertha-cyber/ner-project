import httpx
from src.shared.config import settings


def _infer_url(tenant_id: str) -> str:
    base = settings.model_serving_url.rstrip("/")
    return f"{base}/internal/v1/tenants/{tenant_id}/infer"


async def infer(tenant_id: str, tokens: list[str]) -> dict | None:
    url = _infer_url(tenant_id)
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, json={"tokens": tokens})
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return resp.json()
    except httpx.RequestError:
        return None
