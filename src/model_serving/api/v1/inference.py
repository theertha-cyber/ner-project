from fastapi import APIRouter, Request, HTTPException
from src.model_serving.api.v1.schemas import InferRequest, InferResponse, TokenPrediction
from src.model_serving.services.inference_service import infer

router = APIRouter(prefix="/internal/v1/tenants/{tid}", tags=["inference"])


def get_tenant_id(request: Request) -> str:
    tid = getattr(request.state, "tenant_id", None)
    if tid is None:
        raise HTTPException(status_code=403, detail="Tenant context not available")
    return tid


@router.post("/infer", response_model=InferResponse)
async def inference_endpoint(
    tid: str,
    body: InferRequest,
    request: Request,
):
    tenant_id = get_tenant_id(request)
    if tid != tenant_id:
        raise HTTPException(status_code=403, detail="Tenant mismatch")

    result = infer(tenant_id, body.tokens)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail="No model available for this tenant",
        )

    predictions = [TokenPrediction(**r) for r in result]
    return InferResponse(predictions=predictions)
