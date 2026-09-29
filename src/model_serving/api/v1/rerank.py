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
def rerank_endpoint(
    # Plain `def` on purpose: FastAPI runs it in its threadpool. As `async def` the
    # CPU-bound torch forward pass ran on the event loop and froze every other request
    # to this service (NER inference, /health) for the length of each rerank.
    body: RerankRequest,
    request: Request,
):
    get_tenant_id(request)

    results = rerank(body.query, body.documents, body.top_k)
    return RerankResponse(results=results)
