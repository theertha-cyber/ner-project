import logging
import httpx
from src.shared.config import settings

logger = logging.getLogger(__name__)


class NERClient:
    def __init__(self):
        self.base_url = settings.model_serving_url.rstrip("/")

    async def infer(self, text: str, tenant_id: str, jwt_token: str | None = None) -> list[dict] | None:
        headers = {}
        if jwt_token:
            headers["Authorization"] = f"Bearer {jwt_token}"

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(
                    f"{self.base_url}/internal/v1/infer",
                    headers=headers,
                    json={"text": text, "tenant_id": tenant_id},
                )
                if response.status_code == 404:
                    logger.info("No promoted model found, falling back to base model")
                    return await self._infer_base_model(text, tenant_id)
                response.raise_for_status()
                data = response.json()
                return data.get("entities", [])
            except httpx.RequestError as e:
                logger.error("NER inference request failed: %s", str(e))
                return None

    async def _infer_base_model(self, text: str, tenant_id: str) -> list[dict] | None:
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(
                    f"{self.base_url}/internal/v1/infer",
                    json={"text": text, "tenant_id": tenant_id, "model_version": 0},
                )
                response.raise_for_status()
                data = response.json()
                return data.get("entities", [])
            except httpx.RequestError as e:
                logger.error("Base model NER inference failed: %s", str(e))
                return None
