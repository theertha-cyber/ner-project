from fastapi import APIRouter, Request, HTTPException
from src.model_serving.api.v1.schemas import RerankRequest, RerankResponse
from src.model_serving.services.rerank_service import rerank

router = APIRouter(prefix="/internal/v1", tags=["rerank"])


def get_tenant_id(request: Request) -> str:
    tid = getattr(request.state, "tenant_id", None)
    if tid is None:
        raise HTTPException(status_code=403, detail="Tenant context not available")
    return tid


@router.post("/rerank", response_model=RerankResponse)
async def rerank_endpoint(
    body: RerankRequest,
    request: Request,
):
    get_tenant_id(request)

    results = rerank(body.query, body.documents, body.top_k)
    return RerankResponse(results=results)
